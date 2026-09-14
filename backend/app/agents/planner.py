"""
Preparation Planner Agent — Gate 6. Given Skill Gap's missing/weak skills, a deadline,
and available prep time, produces an ordered PreparationPlan with a dependency graph
(e.g. Spring Boot depends on Java) and a total-hours/feasibility estimate.

Deliberate design decision, stated plainly rather than defaulted to an LLM: this agent
is entirely DETERMINISTIC, no LLM call at all — the same discipline already applied to
Eligibility's hard checks and to Skill Gap's embedding-threshold classification (see
docs/AI_DESIGN.md's model routing table). Reasoning:
- "What does skill X require as a prerequisite" is common-knowledge, slow-changing
  domain knowledge for the tech skills this project's opportunities realistically
  involve (see SKILL_PREREQUISITES below) — a static lookup table plus a topological
  sort is a complete, correct answer for any skill in the table, not an approximation
  an LLM would do better. An LLM call here would be slower, cost money per plan
  generation, and — worse — could hallucinate a prerequisite relationship with no way
  for the user to tell it apart from a real one.
- For a skill NOT in the table, there's no reliable evidence (from this codebase, at
  this gate) to infer a prerequisite relationship even with an LLM — guessing one
  either way would be worse than honestly listing it as a standalone task. This mirrors
  Eligibility's UNCERTAIN-not-guess principle.
If this table's coverage turns out to be the limiting factor in practice (real
opportunities asking for skills far outside it), the honest fix is growing the table,
not reaching for an LLM to paper over missing domain data.
"""
import time
from collections import deque
from datetime import datetime, timezone

from beanie import PydanticObjectId

from app.models.agent_execution import AgentExecution
from app.models.preparation import PreparationPlan, PreparationTask

# A curated, deliberately small set of common tech-skill prerequisite relationships —
# NOT exhaustive, and not claimed to be. Keys/values are lowercase for case-insensitive
# matching against Skill Gap's missing/weak skill strings (which come from free-text
# LLM extraction and vary in casing). Only edges between skills that are BOTH already in
# a given plan's skill set are used (see _dependency_order) — a prerequisite not itself
# flagged as missing/weak by Skill Gap is out of scope for this plan, not silently added
# as an extra task the user never asked about.
SKILL_PREREQUISITES: dict[str, list[str]] = {
    "spring boot": ["java"],
    "spring": ["java"],
    "hibernate": ["java", "sql"],
    "rest apis": ["spring boot", "django", "flask", "express"],
    "django": ["python"],
    "flask": ["python"],
    "fastapi": ["python"],
    "machine learning": ["python", "statistics"],
    "deep learning": ["machine learning"],
    "tensorflow": ["python", "machine learning"],
    "pytorch": ["python", "machine learning"],
    "react": ["javascript"],
    "redux": ["react"],
    "next.js": ["react"],
    "node.js": ["javascript"],
    "express": ["node.js"],
    "typescript": ["javascript"],
    "postgresql": ["sql"],
    "mysql": ["sql"],
    "kubernetes": ["docker"],
    "ci/cd": ["git", "docker"],
    "microservices": ["rest apis", "docker"],
    "graphql": ["rest apis"],
}

# Rough hours-to-learn-the-basics estimates for a student who already has adjacent
# fundamentals — inspection-based, like Skill Gap's original thresholds, not calibrated
# against real study-time data. Unknown skills fall back to DEFAULT_SKILL_EFFORT_HOURS.
SKILL_EFFORT_HOURS: dict[str, float] = {
    "java": 20.0, "python": 15.0, "javascript": 12.0, "typescript": 6.0,
    "sql": 10.0, "postgresql": 6.0, "mysql": 5.0, "mongodb": 8.0,
    "spring boot": 15.0, "spring": 12.0, "hibernate": 8.0, "rest apis": 8.0,
    "django": 12.0, "flask": 8.0, "fastapi": 8.0, "express": 6.0, "node.js": 10.0,
    "react": 15.0, "redux": 6.0, "next.js": 8.0,
    "docker": 8.0, "kubernetes": 14.0, "ci/cd": 8.0, "git": 4.0,
    "aws": 15.0, "gcp": 15.0, "azure": 15.0,
    "machine learning": 25.0, "deep learning": 20.0, "tensorflow": 12.0, "pytorch": 12.0,
    "statistics": 12.0, "microservices": 10.0, "graphql": 6.0,
}
DEFAULT_SKILL_EFFORT_HOURS = 10.0

# A skill marked "weak" (some resume evidence, per Skill Gap) needs less time to close
# the gap than one marked "missing" (no evidence at all) — a plain multiplier, not a
# calibrated figure; revisit once real usage data exists.
WEAK_SKILL_EFFORT_MULTIPLIER = 0.4

# Used only by the LangGraph pipeline's auto-generated first-pass plan (see
# app/graphs/opportunity_pipeline.py), when no user-supplied hours/day is available yet.
# A real value should come from the user via the API and regenerate the plan.
DEFAULT_HOURS_PER_DAY = 2.0


def _normalize(skill: str) -> str:
    return skill.strip().lower()


def compute_available_hours(deadline: datetime | None, hours_per_day: float) -> float | None:
    """
    Converts a deadline + a days/day budget into a total available-hours figure, clamped
    to 0 for a deadline already in the past (still a valid, informative "0 hours left"
    answer, not an error). Shared by the pipeline's first-pass auto-plan (using
    DEFAULT_HOURS_PER_DAY) and the preparation-plan API route (using a real user-supplied
    hours_per_day) so this calculation exists in exactly one place.
    """
    if deadline is None:
        return None
    deadline_aware = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days_remaining = max((deadline_aware - now).total_seconds() / 86400, 0)
    return round(days_remaining * hours_per_day, 1)


def _dependency_order(skills: list[str]) -> list[str]:
    """
    Topologically sorts `skills` (original casing preserved in output) using
    SKILL_PREREQUISITES, restricted to edges where both skills are in the input set.
    Falls back to the original input order if a cycle is detected — SKILL_PREREQUISITES
    is a small curated table assumed acyclic, but a bug there should degrade to "no
    ordering opinion," not crash plan generation.
    """
    normalized_to_original: dict[str, str] = {}
    for skill in skills:
        normalized_to_original.setdefault(_normalize(skill), skill)
    present = set(normalized_to_original.keys())

    # edges[a] = prerequisites of a that are also present in this plan
    edges: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {norm: 0 for norm in present}
    for norm in present:
        prereqs = [p for p in SKILL_PREREQUISITES.get(norm, []) if p in present]
        edges[norm] = prereqs
        in_degree[norm] += len(prereqs)

    # Kahn's algorithm, seeded in input order so ties keep a stable, predictable order.
    queue = deque(norm for norm in normalized_to_original if in_degree[norm] == 0)
    # dependents[a] = skills that list a as a prerequisite
    dependents: dict[str, list[str]] = {norm: [] for norm in present}
    for norm, prereqs in edges.items():
        for p in prereqs:
            dependents[p].append(norm)

    ordered: list[str] = []
    while queue:
        norm = queue.popleft()
        ordered.append(norm)
        for dependent in dependents[norm]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) != len(present):
        # Cycle detected (or a bug in the table) — degrade gracefully to input order.
        ordered = list(normalized_to_original.keys())

    return [normalized_to_original[norm] for norm in ordered], edges, normalized_to_original


def generate_preparation_plan(
    user_id: str,
    opportunity_id: str,
    application_id: str,
    missing_skills: list[str],
    weak_skills: list[str],
    deadline: datetime | None,
    available_hours: float | None,
) -> PreparationPlan:
    """Pure computation (no DB writes) — the caller persists the returned PreparationPlan.
    Mirrors app/agents/skill_gap.py's split: the agent computes and logs its own
    AgentExecution audit record; the pipeline/route layer owns actually saving the
    domain document. See run_planner below for the AgentExecution-logging wrapper."""
    all_skills = list(dict.fromkeys(list(missing_skills) + list(weak_skills)))  # de-duped, order preserved
    weak_set = {_normalize(s) for s in weak_skills}

    ordered_skills, edges, normalized_to_original = _dependency_order(all_skills)

    id_by_normalized: dict[str, PydanticObjectId] = {norm: PydanticObjectId() for norm in normalized_to_original}

    tasks: list[PreparationTask] = []
    for index, skill in enumerate(ordered_skills):
        norm = _normalize(skill)
        base_hours = SKILL_EFFORT_HOURS.get(norm, DEFAULT_SKILL_EFFORT_HOURS)
        estimated_hours = base_hours * WEAK_SKILL_EFFORT_MULTIPLIER if norm in weak_set else base_hours
        depends_on = [id_by_normalized[p] for p in edges.get(norm, [])]

        tasks.append(
            PreparationTask(
                id=id_by_normalized[norm],
                skill=skill,
                title=f"Learn {skill}",
                description=(
                    f"{'Reinforce' if norm in weak_set else 'Build'} {skill} skills"
                    f"{' (some resume evidence found, but weak)' if norm in weak_set else ' (no resume evidence found)'}."
                ),
                depends_on=depends_on,
                estimated_hours=round(estimated_hours, 1),
                order_index=index,
            )
        )

    total_estimated_hours = round(sum(t.estimated_hours for t in tasks), 1)
    feasible = None if available_hours is None else total_estimated_hours <= available_hours

    return PreparationPlan(
        user_id=PydanticObjectId(user_id),
        opportunity_id=PydanticObjectId(opportunity_id),
        application_id=PydanticObjectId(application_id),
        deadline=deadline,
        available_hours=available_hours,
        total_estimated_hours=total_estimated_hours,
        feasible=feasible,
        tasks=tasks,
    )


async def run_planner(
    user_id: str,
    opportunity_id: str,
    application_id: str,
    missing_skills: list[str],
    weak_skills: list[str],
    deadline: datetime | None,
    available_hours: float | None,
) -> tuple[PreparationPlan, AgentExecution]:
    start = time.monotonic()

    plan = generate_preparation_plan(
        user_id, opportunity_id, application_id, missing_skills, weak_skills, deadline, available_hours
    )

    latency_ms = (time.monotonic() - start) * 1000
    execution = AgentExecution(
        user_id=PydanticObjectId(user_id),
        agent_name="planner",
        method="deterministic",  # never calls an LLM — see module docstring for why
        input_summary=(
            f"missing={missing_skills}, weak={weak_skills}, deadline={deadline}, "
            f"available_hours={available_hours}"
        ),
        output={
            "task_count": len(plan.tasks),
            "total_estimated_hours": plan.total_estimated_hours,
            "feasible": plan.feasible,
        },
        status="success",
        latency_ms=latency_ms,
        opportunity_id=PydanticObjectId(opportunity_id),
    )
    await execution.insert()

    return plan, execution
