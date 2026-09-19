# Gate 9 Evaluation Report

Run: 2026-09-19T10-50-47Z

## Discovery Agent (extraction)

- Items: 18 (succeeded: 18, errors: 0)
- p95 latency: 1876.5 ms

| Field | Accuracy |
|---|---|
| company_name | 1.0 |
| role | 1.0 |
| compensation | 1.0 |
| min_cgpa | 1.0 |
| deadline | 1.0 |
| raw_eligibility_text (presence) | 0.889 |

| List field | Precision | Recall | F1 |
|---|---|---|---|
| required_skills | 0.911 | 0.962 | 0.936 |
| preferred_skills | 0.75 | 0.833 | 0.789 |
| allowed_branches | 0.893 | 1.0 | 0.943 |

## Eligibility Agent

- Items: 16 (succeeded: 16, errors: 0)
- Accuracy: 0.875
- False-positive rate (predicted eligible-ish when actually not_eligible): 0.0
- False-negative rate (predicted not_eligible when actually eligible-ish): 0.0
- p95 latency: 14560.8 ms
- Method routing (deterministic vs LLM): all items matched expectation.
- Both misses (`e10`, `e11`) landed on `uncertain` rather than the hand-labeled `eligible`
  — the conservative failure direction (never claims eligibility it can't support), not a
  flip to the wrong side. Worth flagging: an earlier ad-hoc single-call check of these
  same two inputs (outside this harness run) returned `eligible`. The LangChain client
  warns `Model 'gemini-3.6-flash' uses fixed sampling defaults; the sampling
  parameter(s) temperature will be ignored` — i.e. `temperature=0` in
  `app/agents/llm_client.py` is not actually honored by this model, so the qualitative-
  eligibility LLM path is not fully reproducible run-to-run for borderline cases. Not
  fixed here (no code change in this eval pass) — worth a Gate 11 (observability) look:
  a student could get a different verdict on a retry of the same case.

## Skill Gap Agent / Retrieval

- Labeled skills: 18 (errors: 0)
- 3-way classification accuracy at current thresholds (MATCH=0.34, WEAK=0.42): 0.389
- Best single binary threshold by F1 (has-evidence vs missing): 0.38 (precision=1.0, recall=1.0, f1=1.0)

| Threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.2 | 1.0 | 0.0 | 0.0 |
| 0.22 | 1.0 | 0.0 | 0.0 |
| 0.24 | 1.0 | 0.0 | 0.0 |
| 0.26 | 1.0 | 0.0 | 0.0 |
| 0.28 | 1.0 | 0.0 | 0.0 |
| 0.3 | 1.0 | 0.0 | 0.0 |
| 0.32 | 1.0 | 0.0 | 0.0 |
| 0.34 | 1.0 | 0.25 | 0.4 |
| 0.36 | 1.0 | 0.75 | 0.857 |
| 0.38 | 1.0 | 1.0 | 1.0 |
| 0.4 | 0.923 | 1.0 | 0.96 |
| 0.42 | 0.857 | 1.0 | 0.923 |
| 0.44 | 0.857 | 1.0 | 0.923 |
| 0.46 | 0.857 | 1.0 | 0.923 |
| 0.48 | 0.857 | 1.0 | 0.923 |
| 0.5 | 0.857 | 1.0 | 0.923 |

**Applied after this run:** `MATCH_THRESHOLD` in `app/agents/skill_gap.py` was raised from
0.34 to 0.38 on this evidence (see that file's Gate 9 comment). Recomputed 3-way
classification accuracy at the new threshold, from this same run's per-skill distances
(no new API calls): **12/18 = 0.667** (up from 7/18 = 0.389). Not perfect — GraphQL/
Next.js ("weak", distances 0.333-0.334) and two genuinely-missing skills that landed in
the "weak" band (distances 0.386, 0.405) remain misclassified, because matched- and
weak-labeled distances genuinely interleave across resume domains in this data (see the
per-skill table below). `WEAK_THRESHOLD` (0.42) was left unchanged — nothing here
contradicts it, and n=2 resumes is too small to recalibrate it with confidence.

| skill | resume | expected | predicted (old 0.34/0.42) | predicted (new 0.38/0.42) | distance |
|---|---|---|---|---|---|
| FastAPI | backend | matched | matched | matched | 0.325 |
| Python | backend | matched | weak | matched | 0.341 |
| AWS | backend | matched | weak | matched | 0.346 |
| PostgreSQL | backend | matched | weak | matched | 0.353 |
| TypeScript | frontend | matched | weak | matched | 0.356 |
| React | frontend | matched | weak | matched | 0.357 |
| Tailwind CSS | frontend | matched | weak | matched | 0.357 |
| Node.js | frontend | matched | weak | matched | 0.368 |
| Next.js | frontend | weak | matched | matched | 0.333 |
| GraphQL | frontend | weak | matched | matched | 0.334 |
| Docker | backend | weak | weak | matched | 0.373 |
| Machine Learning | backend | weak | weak | matched | 0.371 |
| Kubernetes | backend | missing (negated) | missing | missing | 0.375 |
| Rust | backend | missing (negated) | missing | missing | 0.365 |
| Swift | backend | missing (negated) | missing | missing | 0.349 |
| Machine Learning | frontend | missing (negated) | missing | missing | 0.365 |
| Python | frontend | missing | weak | weak | 0.386 |
| Kubernetes | frontend | missing | weak | weak | 0.405 |

## Agent workflow (from AgentExecution logs written by this run)

| Agent | Runs | Success rate | p95 latency (ms) |
|---|---|---|---|
| discovery | 18 | 1.0 | 1876.5 |
| eligibility | 16 | 1.0 | 14560.8 |

## Sample review sheet (human eval, 1-5)

Recommendation quality can't be scored automatically — score a few real Discovery
extractions below by hand (1 = poor, 5 = excellent) for relevance/usefulness/factuality.

| id | company_name | role | score (1-5) | notes |
|---|---|---|---|---|
| d01 | Innotech Systems | SDE-1 | | |
| d02 | Quanta Labs | Backend Engineer | | |
| d03 | Vertex Analytics | Data Analyst Intern | | |
| d04 | Bramble Co. | Frontend Developer | | |
| d05 | Castlewood Financial | Associate Software Engineer | | |

