# AI Design

**Status:** Architecture locked at Gate 1, Rev 2 (see `ARCHITECTURE.md` §5, §7).
Implementation starts Gate 4.

## Model routing (confirmed principle, unchanged)
| Task | Method |
|---|---|
| Deadline math, CGPA cutoffs | Deterministic code — no LLM |
| Opportunity field extraction | Small/cheap LLM, structured-output prompting |
| Ambiguous eligibility interpretation | Stronger LLM, constrained to evidence + confidence output |
| Resume↔JD similarity | Embeddings + cosine similarity (Chroma) |
| Skill taxonomy matching | Embeddings first, LLM only for ambiguous ties |

## MCP tool access (new — central from Gate 4)
Agents don't call Gmail/GitHub/Calendar APIs directly. They call MCP tools through
`app/mcp/`, which handles auth, permission scoping, retries, and timeouts uniformly. See
`ARCHITECTURE.md` §5 for the tool table and failure-handling rule. Every agent result
includes evidence flags noting whether an expected MCP source was actually available.

## Non-negotiable rule
Every agent decision returns `{decision, reason, evidence[], confidence, source, timestamp}`.
No bare LLM verdict is ever surfaced to the user or written as a trusted DB value without
schema validation. An unavailable MCP tool lowers `confidence`, never silently proceeds.

Agent prompts, schemas, MCP tool configs, and eval harness land here progressively
starting Gate 4.
