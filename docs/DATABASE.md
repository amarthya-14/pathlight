# Database Design

**Status:** Gate 2 subset implemented and tested (MongoDB, switched from the originally
planned PostgreSQL — see `ARCHITECTURE.md` §11 for the honest reasoning and trade-offs).

ORM: **Beanie** (async ODM on Motor + Pydantic). Collections/indexes are created/ensured
the first time `init_db()` runs — no separate migration step the way Alembic would
require, though a real migration strategy should be revisited if the schema needs
versioned upgrades later.

## Entities

| Entity | Status | Notes |
|---|---|---|
| User | ✅ Implemented | unique index on email, bcrypt hash |
| Profile | ✅ Implemented | unique index on `user_id` (1:1 with User) — cgpa/branch only so far |
| Company | ✅ Implemented | unique index on name |
| Opportunity | ✅ Implemented | **compound unique index** on `(company_id, role_hash)` — verified to reject duplicate inserts at the DB level, not just via application check |
| Skill / ProfileSkill | Not built — superseded | See note below |
| ResumeVersion | Planned (Gate 3) | needed for document ingestion |
| OpportunityRequirement | ✅ Implemented — **as an embedded sub-document**, not a separate collection (see ARCHITECTURE.md §13) | `Opportunity.requirements` |
| Application | ✅ Implemented | one per `(user_id, opportunity_id)`, compound unique index |
| ApplicationStatus | ✅ Implemented — embedded array (`Application.status_history`), append-only via `$push` | plan from §11 held up in practice |
| Deadline | Planned | likely folds into `Opportunity.deadline` rather than a separate document |
| PreparationPlan / PreparationTask | Planned (Gate 5+) | dependency graph — self-referencing IDs (array of ObjectIds) instead of a self-join |
| CalendarEvent | Planned (Gate 6+) | tied to Calendar MCP |
| Notification | Planned | |
| AgentExecution | ✅ Implemented | logs every Discovery/Eligibility run, success or failure |
| Document | ✅ Implemented | uploaded resumes/JDs/emails; `storage_filename` is what the Filesystem MCP tool uses to locate the file, not a raw path |
| Integration | Planned (Gate 4+) | tracks MCP tool connection state per user |

## Key decisions
- Dedupe (`Opportunity`) and the 1:1 `User`↔`Profile` relationship are both enforced by
  **MongoDB unique indexes**, not just application-level checks — this was specifically
  verified (see `ARCHITECTURE.md` §11), not assumed.
- No foreign-key integrity in MongoDB — cascading deletes and referential checks must be
  handled in application code once delete endpoints exist (not yet built).
- `ApplicationStatus` history moves to an embedded array (Gate 4+) instead of a separate
  table+join, since MongoDB documents naturally fit "one Application, many status
  events" better than a relational join would.

Full schema documented here as each entity is actually built — not written speculatively
ahead of the code that needs it.

## Vector store (Chroma, not MongoDB — Gate 5)

The originally planned `Skill`/`ProfileSkill` structured entities were superseded once
the Skill Gap Agent was actually built: skill matching turned out to be a pure semantic-
similarity problem better served by embedding the resume's free text directly, rather
than first extracting a structured skill taxonomy and matching against it. A `resume_chunks`
collection lives in Chroma (not MongoDB), scoped per-user via metadata:

| Field | Purpose |
|---|---|
| `id` | `{document_id}:{chunk_index}` |
| `embedding` | `gemini-embedding-001` vector |
| `document` (text) | the chunk's raw text |
| `metadata.user_id` | scopes queries to one user |
| `metadata.document_id` | lets re-indexing delete-and-replace a document's old chunks |
| `metadata.chunk_index` | chunk position within the source document |

See `docs/AI_DESIGN.md`'s RAG pipeline section and `app/retrieval/vector_store.py`.
