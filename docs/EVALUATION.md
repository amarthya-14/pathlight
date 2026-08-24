# Evaluation Strategy

**Status:** Framework confirmed at Gate 1 (see blueprint §16). Benchmark dataset is a Gate 5 deliverable.

| Layer | Metric |
|---|---|
| Extraction (Discovery Agent) | Precision / Recall / F1 on fields |
| Eligibility Agent | Accuracy, false-positive rate, false-negative rate |
| Retrieval (Chroma) | Recall@K, Precision@K |
| Agent workflow | Task success rate, retry rate, p95 latency |
| Recommendations | Human eval: relevance / usefulness / factuality (1–5) |

A ~30–50 item hand-labeled benchmark set (synthetic + anonymized real emails) is required
before Gate 5 is considered complete — not optional polish.
