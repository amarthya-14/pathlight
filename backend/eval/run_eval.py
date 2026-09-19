"""
Gate 9 evaluation harness — docs/EVALUATION.md.

Calls the REAL Discovery/Eligibility/Skill-Gap agents (real Gemini LLM + real Gemini
embeddings, no fakes) against the hand-labeled benchmark sets in eval/data/, and reports
the metrics docs/EVALUATION.md's table calls for.

NOT part of the pytest suite or CI — this makes real, mildly costly Gemini API calls, so
it's meant to be run manually:

    cd backend && .venv/bin/python -m eval.run_eval

Uses the same mongomock_motor + init_db() pattern as tests/conftest.py so AgentExecution
rows can be written without a real MongoDB, but — unlike every existing test — does NOT
patch the LLM or embedder, so this is the first thing in this codebase that actually
exercises the real API end-to-end against known-correct answers, not just pipeline
plumbing.
"""
import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from beanie import PydanticObjectId
from mongomock_motor import AsyncMongoMockClient

from app.agents.eligibility import run_eligibility
from app.agents.discovery import run_discovery
from app.agents.schemas import EligibilityDecision
from app.agents.skill_gap import MATCH_THRESHOLD, WEAK_THRESHOLD, _skill_explicitly_negated
from app.core.config import settings
from app.core.db import init_db
from app.models.agent_execution import AgentExecution
from app.models.opportunity import OpportunityRequirements
from app.models.user import Profile
from app.retrieval.vector_store import index_resume_chunks, query_resume_chunks

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"

LLM_CALL_DELAY_SECONDS = 1.0  # gentle pacing against free-tier rate limits


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _norm_set(items: list[str] | None) -> set[str]:
    return {_norm(x) for x in (items or []) if _norm(x)}


def _parse_date(s: str | None) -> str | None:
    if not s:
        return None
    return s[:10]


def _datetime_to_date(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Discovery evaluation
# ---------------------------------------------------------------------------

async def eval_discovery(user_id: str) -> dict:
    items = json.loads((DATA_DIR / "discovery_benchmark.json").read_text())

    singular_fields = ["company_name", "role", "compensation", "min_cgpa", "deadline"]
    singular_correct = {f: 0 for f in singular_fields}
    raw_text_presence_correct = 0

    list_fields = ["required_skills", "preferred_skills", "allowed_branches"]
    list_tp = {f: 0 for f in list_fields}
    list_fp = {f: 0 for f in list_fields}
    list_fn = {f: 0 for f in list_fields}

    errors = []
    per_item = []

    for item in items:
        expected = item["expected"]
        try:
            result, execution = await run_discovery(item["raw_text"], item["source"], user_id)
        except Exception as e:
            errors.append({"id": item["id"], "error": str(e)})
            continue
        finally:
            await asyncio.sleep(LLM_CALL_DELAY_SECONDS)

        row = {"id": item["id"], "latency_ms": execution.latency_ms}

        if _norm(result.company_name) == _norm(expected["company_name"]):
            singular_correct["company_name"] += 1
        if _norm(result.role) == _norm(expected["role"]):
            singular_correct["role"] += 1
        if _norm(result.compensation) == _norm(expected["compensation"]):
            singular_correct["compensation"] += 1

        pred_cgpa, exp_cgpa = result.min_cgpa, expected["min_cgpa"]
        if (pred_cgpa is None and exp_cgpa is None) or (
            pred_cgpa is not None and exp_cgpa is not None and abs(pred_cgpa - exp_cgpa) < 0.05
        ):
            singular_correct["min_cgpa"] += 1

        if _datetime_to_date(result.deadline) == _parse_date(expected["deadline"]):
            singular_correct["deadline"] += 1

        pred_has_text = bool(result.raw_eligibility_text and result.raw_eligibility_text.strip())
        exp_has_text = bool(expected["raw_eligibility_text"])
        if pred_has_text == exp_has_text:
            raw_text_presence_correct += 1

        for field in list_fields:
            pred_set = _norm_set(getattr(result, field))
            exp_set = _norm_set(expected[field])
            list_tp[field] += len(pred_set & exp_set)
            list_fp[field] += len(pred_set - exp_set)
            list_fn[field] += len(exp_set - pred_set)

        row["output"] = result.model_dump(mode="json")
        per_item.append(row)

    n = len(per_item)

    def prf(tp, fp, fn):
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}

    return {
        "n_items": len(items),
        "n_succeeded": n,
        "n_errors": len(errors),
        "errors": errors,
        "singular_field_accuracy": {f: round(singular_correct[f] / n, 3) if n else None for f in singular_fields},
        "raw_eligibility_text_presence_accuracy": round(raw_text_presence_correct / n, 3) if n else None,
        "list_field_prf": {f: prf(list_tp[f], list_fp[f], list_fn[f]) for f in list_fields},
        "p95_latency_ms": _p95([r["latency_ms"] for r in per_item]),
        "per_item": per_item,
    }


# ---------------------------------------------------------------------------
# Eligibility evaluation
# ---------------------------------------------------------------------------

async def eval_eligibility(user_id: str) -> dict:
    items = json.loads((DATA_DIR / "eligibility_benchmark.json").read_text())

    decisions = [d.value for d in EligibilityDecision]
    confusion = {exp: {pred: 0 for pred in decisions} for exp in decisions}
    correct = 0
    method_mismatches = []
    errors = []
    per_item = []
    latencies = []

    for item in items:
        profile = Profile(
            user_id=PydanticObjectId(),
            cgpa=item["profile"]["cgpa"],
            branch=item["profile"]["branch"],
        )
        req = OpportunityRequirements(
            min_cgpa=item["requirements"]["min_cgpa"],
            allowed_branches=item["requirements"]["allowed_branches"],
            raw_eligibility_text=item["requirements"]["raw_eligibility_text"],
        )
        try:
            result, execution = await run_eligibility(req, profile, user_id, str(PydanticObjectId()))
        except Exception as e:
            errors.append({"id": item["id"], "error": str(e)})
            continue
        finally:
            if item["expect_llm_call"]:
                await asyncio.sleep(LLM_CALL_DELAY_SECONDS)

        latencies.append(execution.latency_ms)
        expected_decision = item["expected_decision"]
        predicted_decision = result.decision.value
        confusion[expected_decision][predicted_decision] += 1
        if predicted_decision == expected_decision:
            correct += 1

        expected_method = "llm" if item["expect_llm_call"] else "deterministic"
        if execution.method != expected_method:
            method_mismatches.append(
                {"id": item["id"], "expected_method": expected_method, "actual_method": execution.method}
            )

        per_item.append(
            {
                "id": item["id"],
                "expected": expected_decision,
                "predicted": predicted_decision,
                "method": execution.method,
                "reason": result.reason,
            }
        )

    n = len(per_item)
    fp = sum(
        confusion["not_eligible"][pred]
        for pred in ["eligible", "partially_eligible"]
    )
    n_not_eligible = sum(confusion["not_eligible"].values())
    fn = sum(
        confusion[exp]["not_eligible"]
        for exp in ["eligible", "partially_eligible"]
    )
    n_positive_expected = sum(confusion[exp][pred] for exp in ["eligible", "partially_eligible"] for pred in decisions)

    return {
        "n_items": len(items),
        "n_succeeded": n,
        "n_errors": len(errors),
        "errors": errors,
        "accuracy": round(correct / n, 3) if n else None,
        "false_positive_rate": round(fp / n_not_eligible, 3) if n_not_eligible else None,
        "false_negative_rate": round(fn / n_positive_expected, 3) if n_positive_expected else None,
        "confusion_matrix": confusion,
        "method_mismatches": method_mismatches,
        "p95_latency_ms": _p95(latencies),
        "per_item": per_item,
    }


# ---------------------------------------------------------------------------
# Skill-gap / retrieval evaluation
# ---------------------------------------------------------------------------

async def eval_skill_gap() -> dict:
    data = json.loads((DATA_DIR / "skill_gap_benchmark.json").read_text())

    labeled: list[dict] = []  # {skill, expected_label, distance, negated}
    errors = []

    for resume in data["resumes"]:
        user_id = str(PydanticObjectId())
        document_id = str(PydanticObjectId())
        try:
            await index_resume_chunks(user_id, document_id, resume["text"])
        except Exception as e:
            errors.append({"resume": resume["id"], "error": f"indexing failed: {e}"})
            continue

        for entry in resume["skills"]:
            skill = entry["skill"]
            try:
                hits = await query_resume_chunks(user_id, skill, n_results=1)
            except Exception as e:
                errors.append({"resume": resume["id"], "skill": skill, "error": str(e)})
                continue
            finally:
                await asyncio.sleep(0.3)

            if not hits:
                labeled.append({"skill": skill, "expected_label": entry["label"], "distance": None, "negated": False})
                continue
            chunk_text, distance = hits[0]
            negated = _skill_explicitly_negated(chunk_text, skill)
            labeled.append(
                {"skill": skill, "expected_label": entry["label"], "distance": distance, "negated": negated}
            )

    def classify(distance: float | None, negated: bool) -> str:
        if distance is None or negated:
            return "missing"
        if distance <= MATCH_THRESHOLD:
            return "matched"
        if distance <= WEAK_THRESHOLD:
            return "weak"
        return "missing"

    correct = 0
    for row in labeled:
        row["predicted_label"] = classify(row["distance"], row["negated"])
        if row["predicted_label"] == row["expected_label"]:
            correct += 1
    n = len(labeled)
    accuracy_at_current_thresholds = round(correct / n, 3) if n else None

    # Threshold sweep: binary "has evidence" (matched|weak) vs "missing", scored against
    # distance alone (ignoring the negation override, which is threshold-independent) —
    # this directly answers the open question in app/agents/skill_gap.py's comments.
    sweep = []
    candidates = [round(0.20 + 0.02 * i, 2) for i in range(16)]  # 0.20 .. 0.50
    scored = [row for row in labeled if row["distance"] is not None]
    for threshold in candidates:
        tp = fp = fn = tn = 0
        for row in scored:
            expected_has_evidence = row["expected_label"] in ("matched", "weak") and not row["negated"]
            predicted_has_evidence = row["distance"] <= threshold and not row["negated"]
            if predicted_has_evidence and expected_has_evidence:
                tp += 1
            elif predicted_has_evidence and not expected_has_evidence:
                fp += 1
            elif not predicted_has_evidence and expected_has_evidence:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        sweep.append({"threshold": threshold, "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)})

    best = max(sweep, key=lambda r: r["f1"]) if sweep else None

    return {
        "n_labeled_skills": n,
        "n_errors": len(errors),
        "errors": errors,
        "accuracy_at_current_thresholds": accuracy_at_current_thresholds,
        "current_match_threshold": MATCH_THRESHOLD,
        "current_weak_threshold": WEAK_THRESHOLD,
        "threshold_sweep": sweep,
        "best_single_threshold_by_f1": best,
        "per_skill": labeled,
    }


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = min(len(values) - 1, int(round(0.95 * (len(values) - 1))))
    return round(values[idx], 1)


# ---------------------------------------------------------------------------
# Agent-workflow rollup (from AgentExecution rows written during this run)
# ---------------------------------------------------------------------------

async def eval_agent_workflow() -> dict:
    rollup = {}
    for agent_name in ["discovery", "eligibility", "skill_gap"]:
        executions = await AgentExecution.find(AgentExecution.agent_name == agent_name).to_list()
        if not executions:
            continue
        n = len(executions)
        n_success = sum(1 for e in executions if e.status == "success")
        rollup[agent_name] = {
            "n_runs": n,
            "success_rate": round(n_success / n, 3),
            "p95_latency_ms": _p95([e.latency_ms for e in executions]),
        }
    return rollup


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _sample_review_sheet(discovery_result: dict) -> str:
    lines = [
        "## Sample review sheet (human eval, 1-5)",
        "",
        "Recommendation quality can't be scored automatically — score a few real Discovery",
        "extractions below by hand (1 = poor, 5 = excellent) for relevance/usefulness/factuality.",
        "",
        "| id | company_name | role | score (1-5) | notes |",
        "|---|---|---|---|---|",
    ]
    for row in discovery_result["per_item"][:5]:
        out = row["output"]
        lines.append(f"| {row['id']} | {out['company_name']} | {out['role']} | | |")
    return "\n".join(lines) + "\n"


def _render_report(discovery, eligibility, skill_gap, workflow, timestamp: str) -> str:
    lines = [f"# Gate 9 Evaluation Report", "", f"Run: {timestamp}", "", "## Discovery Agent (extraction)", ""]
    lines.append(f"- Items: {discovery['n_items']} (succeeded: {discovery['n_succeeded']}, errors: {discovery['n_errors']})")
    lines.append(f"- p95 latency: {discovery['p95_latency_ms']} ms")
    lines.append("")
    lines.append("| Field | Accuracy |")
    lines.append("|---|---|")
    for f, acc in discovery["singular_field_accuracy"].items():
        lines.append(f"| {f} | {acc} |")
    lines.append(f"| raw_eligibility_text (presence) | {discovery['raw_eligibility_text_presence_accuracy']} |")
    lines.append("")
    lines.append("| List field | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|")
    for f, m in discovery["list_field_prf"].items():
        lines.append(f"| {f} | {m['precision']} | {m['recall']} | {m['f1']} |")
    if discovery["errors"]:
        lines.append("")
        lines.append(f"**Errors:** {discovery['errors']}")

    lines += ["", "## Eligibility Agent", ""]
    lines.append(f"- Items: {eligibility['n_items']} (succeeded: {eligibility['n_succeeded']}, errors: {eligibility['n_errors']})")
    lines.append(f"- Accuracy: {eligibility['accuracy']}")
    lines.append(f"- False-positive rate (predicted eligible-ish when actually not_eligible): {eligibility['false_positive_rate']}")
    lines.append(f"- False-negative rate (predicted not_eligible when actually eligible-ish): {eligibility['false_negative_rate']}")
    lines.append(f"- p95 latency: {eligibility['p95_latency_ms']} ms")
    if eligibility["method_mismatches"]:
        lines.append(f"- **Method mismatches (deterministic/LLM routing bugs):** {eligibility['method_mismatches']}")
    else:
        lines.append("- Method routing (deterministic vs LLM): all items matched expectation.")
    if eligibility["errors"]:
        lines.append(f"- **Errors:** {eligibility['errors']}")

    lines += ["", "## Skill Gap Agent / Retrieval", ""]
    lines.append(f"- Labeled skills: {skill_gap['n_labeled_skills']} (errors: {skill_gap['n_errors']})")
    lines.append(
        f"- 3-way classification accuracy at current thresholds "
        f"(MATCH={skill_gap['current_match_threshold']}, WEAK={skill_gap['current_weak_threshold']}): "
        f"{skill_gap['accuracy_at_current_thresholds']}"
    )
    if skill_gap["best_single_threshold_by_f1"]:
        b = skill_gap["best_single_threshold_by_f1"]
        lines.append(
            f"- Best single binary threshold by F1 (has-evidence vs missing): {b['threshold']} "
            f"(precision={b['precision']}, recall={b['recall']}, f1={b['f1']})"
        )
    lines.append("")
    lines.append("| Threshold | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|")
    for row in skill_gap["threshold_sweep"]:
        lines.append(f"| {row['threshold']} | {row['precision']} | {row['recall']} | {row['f1']} |")
    if skill_gap["errors"]:
        lines.append("")
        lines.append(f"**Errors:** {skill_gap['errors']}")

    lines += ["", "## Agent workflow (from AgentExecution logs written by this run)", ""]
    lines.append("| Agent | Runs | Success rate | p95 latency (ms) |")
    lines.append("|---|---|---|---|")
    for name, m in workflow.items():
        lines.append(f"| {name} | {m['n_runs']} | {m['success_rate']} | {m['p95_latency_ms']} |")

    lines += ["", _sample_review_sheet(discovery)]

    return "\n".join(lines) + "\n"


async def main():
    tmp_dir = tempfile.mkdtemp(prefix="pathlight_eval_chroma_")
    settings.CHROMA_PERSIST_DIR = tmp_dir
    import app.retrieval.vector_store as vector_store_module
    vector_store_module._client = None

    mock_client = AsyncMongoMockClient()
    await init_db(client=mock_client)

    user_id = str(PydanticObjectId())

    print("Running Discovery Agent benchmark (real Gemini calls)...")
    discovery = await eval_discovery(user_id)
    print(f"  -> {discovery['n_succeeded']}/{discovery['n_items']} succeeded")

    print("Running Eligibility Agent benchmark (real Gemini calls for qualitative cases)...")
    eligibility = await eval_eligibility(user_id)
    print(f"  -> {eligibility['n_succeeded']}/{eligibility['n_items']} succeeded, accuracy={eligibility['accuracy']}")

    print("Running Skill Gap / retrieval benchmark (real Gemini embeddings)...")
    skill_gap = await eval_skill_gap()
    print(f"  -> {skill_gap['n_labeled_skills']} labeled skills, accuracy={skill_gap['accuracy_at_current_thresholds']}")

    workflow = await eval_agent_workflow()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    RESULTS_DIR.mkdir(exist_ok=True)
    raw = {
        "timestamp": timestamp,
        "discovery": discovery,
        "eligibility": eligibility,
        "skill_gap": skill_gap,
        "agent_workflow": workflow,
    }
    (RESULTS_DIR / f"{timestamp}.json").write_text(json.dumps(raw, indent=2, default=str))

    report = _render_report(discovery, eligibility, skill_gap, workflow, timestamp)
    (Path(__file__).parent / "report.md").write_text(report)

    print(f"\nWrote eval/results/{timestamp}.json and eval/report.md")


if __name__ == "__main__":
    asyncio.run(main())
