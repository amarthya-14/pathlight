# Autonomous Application Pipeline — Part 1 (Off-Campus)

**Status:** Implemented (email-apply phase) — see §12 for what was built, where it
differs from this design, and the real-Gmail smoke test still owed. This is **Gate 10**, inserted ahead of
Cloud Deployment / Security+Observability / Final Demonstration — see §11 for the
resulting gate-table renumbering (10→11, 11→12, 12→13) this doc proposes in
`docs/ARCHITECTURE.md`.

**Scope, stated plainly:** off-campus opportunities only. On-campus placement-cell /
NEO PAT platform integration is a deliberately separate effort ("Part 2") and is out of
scope for this gate — nothing here assumes or blocks it.

## 1. What "autonomous" means here, precisely

Three separate capabilities, each with a different trust boundary — conflating them
would be exactly the kind of silent-irreversible-action mistake `ARCHITECTURE.md` §7
already warned against:

1. **Sourcing** — new opportunities appear in Pathlight without the user manually
   pasting a JD.
2. **Tailoring** — for each sourced opportunity, a resume tailored to that JD is
   generated automatically, as a new stage of the existing pipeline.
3. **Applying** — sending the application happens **only** after the user reviews the
   tailored resume and explicitly approves it. The system never sends an application
   unattended. This isn't a hedge added late — it's `ARCHITECTURE.md` §7's own plan
   finally being executed: *"No irreversible actions in the MVP graph, so no
   human-approval gate yet — added when a future action (auto-apply, sending email via
   MCP) is introduced."* That future action is this gate.

## 2. Decisions locked for this gate (with reasoning)

| Decision | Choice | Why |
|---|---|---|
| LinkedIn/Naukri sourcing | Parse job-alert emails via Gmail MCP — **not** direct site login/scraping | Neither platform exposes a public job-search API for individual users, and both prohibit automated login/scraping in their ToS. Scraping risks account bans for what is supposed to be the user's own professional account. Both platforms already offer opt-in email digests for saved searches — reading those via a read-only, user-consented Gmail scope carries none of that risk and reuses infrastructure this project already planned (`GMAIL_MCP_CLIENT_ID`/`SECRET` have been stubbed in `.env.example` since Gate 0). |
| Gmail scope | `gmail.readonly` (sourcing) + `gmail.send` (applying) only — never full mailbox access | Matches the least-privilege principle `ARCHITECTURE.md` §5 already states for Gmail MCP ("read-only, scoped to a labeled folder if the provider supports it"). |
| Apply mechanism | **Email-first**: send the tailored resume + a generated cover note to an email address extracted from the JD. Browser form-fill (LinkedIn Easy Apply, Naukri's native apply, ATS portals) is a **planned second phase of this same gate**, always gated behind the identical human-approval step, never triggered unattended. | Email-apply reuses the same Gmail OAuth already being built for sourcing, carries no bot-detection/anti-automation risk, and genuinely covers a share of off-campus postings that list a direct contact email. Form-fill is higher-coverage but higher-risk (breaks on UI changes, is exactly what anti-automation systems are built to catch) — sequenced second, not skipped. |
| Human review gate | Mandatory, blocking, per application | Matches `AI_DESIGN.md`'s non-negotiable transparency rule and `ARCHITECTURE.md` §7's explicit plan for when auto-apply arrives. |
| OAuth token storage | Real encryption at rest for Gmail tokens, brought forward from the deferred Gate 11 (now 12) scope | `SECURITY.md` already states GitHub/Calendar MCP deliberately shipped **without** real OAuth specifically to avoid holding plaintext per-user tokens ahead of the encryption work. Gmail sourcing/applying needs a real per-user OAuth token — that can no longer be deferred, so it's built now, minimally (§5), not skipped. |

## 3. New pipeline stage

Current (`app/graphs/opportunity_pipeline.py`):
```
discovery → persist_opportunity → eligibility → skill_gap → planner → END
```

New:
```
discovery → persist_opportunity → eligibility → skill_gap → planner → resume_tailor → END
```
`resume_tailor` runs whenever `eligibility.decision != NOT_ELIGIBLE` (no point tailoring
a resume for something the user can't apply to) and appends a `READY_TO_APPLY` status
event — an existing `ApplicationStage` value nothing has set yet, which turns out to
describe exactly this state: tailored resume ready, awaiting the user's review.

Applying itself is **not** a graph node — it's a separate, user-triggered action outside
the pipeline (§7), consistent with "no irreversible actions in the graph" from §1.

**Sourcing does not need a new graph node either.** `app/workers/gmail_poll.py` (§5) is a
new *caller* of the existing `run_opportunity_pipeline(raw_text, source, user_id)` entry
point — `Opportunity.source` already accepts `"gmail_mcp"` in its docstring-documented
enum-by-convention (`app/models/opportunity.py`: `# manual | gmail_mcp | ...`), it has
simply never been set by anything real yet.

## 4. New/changed models

- **`OpportunityRequirements`** (`app/models/opportunity.py`) / **`ExtractedOpportunity`**
  (`app/agents/schemas.py`): add `apply_email: str | None` and `application_url: str |
  None`. Extracted by the existing Discovery Agent LLM call — one more optional field in
  the same structured-output schema, not a new agent, matching the "leave unset rather
  than invent" discipline the rest of that schema already follows.
- **`TailoredResume`** (new, `app/models/tailored_resume.py`) — a top-level Document, one
  per `application_id` (unique index), following the same pattern as `PreparationPlan`
  (not embedded in `Application`, since it's independently regenerated and fetched via
  its own route):
  ```python
  class TailoredResume(Document):
      application_id: Indexed(PydanticObjectId, unique=True)
      base_document_id: PydanticObjectId
      tailored_text: str
      changes_summary: list[str]
      skills_emphasized: list[str]
      confidence: float
      warnings: list[str] = Field(default_factory=list)
      generated_at: datetime
  ```
  No server-side diff is stored — the frontend diffs `tailored_text` against the base
  `Document.extracted_text` at render time, the same "recompute at read time, don't
  freeze a derived value" reasoning already applied to `skill_gap_note`
  (`ARCHITECTURE.md` §16).
- **`Integration`** (new, `app/models/integration.py`) — `DATABASE.md` already lists this
  as "Planned (Gate 4+)"; this gate is what finally needs it:
  ```python
  class Integration(Document):
      user_id: Indexed(PydanticObjectId)
      provider: str  # "gmail" for now
      status: str  # connected | disconnected | error
      scopes: list[str]
      encrypted_access_token: str
      encrypted_refresh_token: str
      token_expiry: datetime | None
      last_polled_at: datetime | None
      connected_at: datetime
  ```
  Compound unique index on `(user_id, provider)`. Tokens are never returned by any API
  response — `status`/`scopes`/`connected_at` are the only fields a client ever sees.
- **`ApplicationStage`** (`app/models/application.py`): two new values —
  `MANUAL_APPLY_REQUIRED` (no `apply_email`/`application_url` could be extracted; the
  user is shown the posting and applies outside Pathlight) and `SKIPPED_BY_USER` (the
  user reviewed the tailored resume and chose not to apply). `READY_TO_APPLY` and
  `APPLIED` already exist and are reused as-is (§3) — deliberately not renamed or
  duplicated.

## 5. New MCP tool: Gmail MCP (built for real, replacing "planned")

`app/mcp/gmail_server.py` (FastMCP), mirroring the Filesystem/GitHub/Calendar MCP
pattern already established:
- `list_recent_messages(query, max_results)` — read-only, Gmail search syntax (e.g.
  `from:jobalerts-noreply@linkedin.com OR from:noreply@naukri.com newer_than:1d`).
- `get_message(message_id)` — full subject/body/snippet.
- `send_message(to, subject, body_text, attachment)` — **write**, callable only from the
  apply flow (§7), never from the sourcing poll. A dedicated regression test asserts this
  is unreachable from any other code path, mirroring the Eligibility Agent's
  never-calls-the-LLM test style already in this project.

`app/mcp/gmail_client.py` — in-process client wrapper, reusing the
`BaseExceptionGroup`-unwrapping fix documented in `ARCHITECTURE.md` §12 (Gate 3), since
it's an SDK-transport-level behavior, not specific to the Filesystem server.

**OAuth (new):** real per-user Google OAuth2, minimal surface:
- `GET /api/integrations/gmail/connect` → returns the Google consent URL.
- `GET /api/integrations/gmail/callback` → exchanges the code, encrypts both tokens
  (`app/core/crypto.py`, Fernet, key from a new `TOKEN_ENCRYPTION_KEY` env var — generated
  once, never committed, same secrets discipline `.env`/`JWT_SECRET` already follow),
  stores/updates the user's `Integration` row.
- `DELETE /api/integrations/gmail` → revokes the token with Google and deletes the stored
  `Integration` row.

**Poll worker:** `app/workers/gmail_poll.py`, an in-process background task — the same
"background worker task inside the same service, not a separate deployable" pattern
`ARCHITECTURE.md` §4 already uses for the outbox. Runs every
`GMAIL_POLL_INTERVAL_SECONDS` (default 900) per connected `Integration`: searches a small,
explicit sender allowlist (`GMAIL_ALERT_SENDERS`), and for each new matching message calls
`run_opportunity_pipeline(raw_text=<subject+body>, source="gmail_mcp", user_id=...)` — the
existing pipeline entry point, unchanged. Tracks `last_polled_at` per `Integration` to
avoid reprocessing the same message twice.

## 6. New agent: Resume Tailor

`app/agents/resume_tailor.py` — uses the strong LLM via structured output
(`app/agents/llm_client.py::get_strong_llm`, the existing single point of LLM-provider
contact), same discipline as every other agent in this project. Input: the user's most
recent `DocumentType.RESUME` text, the opportunity's `OpportunityRequirements`, and the
`SkillGapResult` already computed earlier in the same pipeline run.

```python
class TailoredResumeResult(BaseModel):
    tailored_text: str
    changes_summary: list[str]
    skills_emphasized: list[str]
    confidence: float
    warnings: list[str] = Field(default_factory=list)
```

**Non-negotiable rule, carried forward from Discovery's own extraction prompt:** reword,
reorder, and re-emphasize only — never fabricate experience or skills the user doesn't
have. A required skill the resume genuinely lacks is surfaced as a `warning`, never
silently added to `tailored_text`. This needs the same kind of regression test Skill
Gap's negation guard got in Gate 6: a fake resume with an explicitly-absent skill must
never appear as present in tailored output.

If no resume is on file, the node no-ops with a note in `warnings` — the same
"not an error, nothing to do" pattern `skill_gap`/`planner` already use for their own
missing-precondition cases.

## 7. New API routes

- `GET /api/applications/{id}/tailored-resume` — fetch `TailoredResume` + the base
  resume's `extracted_text` (frontend diffs client-side, per §4).
- `POST /api/applications/{id}/review` — body `{"approve": bool}`.
  - `approve=true`: if `Opportunity.requirements.apply_email` is set, sends the tailored
    resume + a generated cover note via Gmail MCP `send_message`, then appends an
    `APPLIED` status event. If no `apply_email`/`application_url` was extracted, appends
    `MANUAL_APPLY_REQUIRED` instead and surfaces the posting details so the user can
    apply outside Pathlight — never silently fails.
  - `approve=false`: appends `SKIPPED_BY_USER`. No Gmail call is made.
  - 404 (not 403) if the application doesn't exist or isn't owned by the caller — same
    anti-enumeration pattern as `GET /api/documents/{id}`.
- `GET /api/integrations/gmail/connect`, `GET /api/integrations/gmail/callback`,
  `DELETE /api/integrations/gmail` (§5).
- `GET /api/integrations` — list the caller's connected integrations (status/scopes only,
  never tokens).

## 8. Frontend additions

- **Integrations/Settings page** — "Connect Gmail" button driving the OAuth flow above,
  showing connection status and a disconnect action.
- **Application detail page** — new "Review & Apply" section, shown once
  `status == READY_TO_APPLY`: renders `tailored_text` against the base resume (a simple
  paragraph-level diff), the `changes_summary`/`warnings` list, and **Approve**/**Skip**
  buttons wired to `POST /review`. Never auto-advances past this screen — the same
  "AI-derived value always shows its evidence, never a flattened verdict" rule
  `AI_DESIGN.md` already commits to applies here to the apply *action* itself, not just
  to displayed data.

## 9. Testing plan (mirroring this project's existing discipline)

- Gmail MCP: mocked HTTP (same style as `test_github_mcp.py`) — list/get/send,
  auth-failure, malformed-message handling, and a **never-sends-without-the-review-route**
  regression test.
- Resume Tailor: `FakeLLM`-based — never fabricates an absent skill (regression test,
  same spirit as Skill Gap's negation guard), correct no-op when no resume exists.
- `Integration`/crypto: encrypt/decrypt round-trip, and a test asserting a stored
  `Integration` document never contains a plaintext token substring.
- Pipeline: `resume_tailor` node integration test extending
  `tests/test_opportunity_pipeline.py`.
- API: `/review` route tests — approve/skip/manual-required paths, ownership (404 not
  403), and an explicit assertion that skip never triggers a Gmail send.
- **Manual smoke test required before demo-ready** (same discipline as Gate 6/8's real-API
  verification): a real Gmail account, a real LinkedIn/Naukri alert email ingested
  end-to-end, through to a real sent application email. Flagged explicitly here so it
  isn't skipped the way Gate 4's real-Gemini caveat almost was.

## 10. Explicitly deferred (stated plainly, not hidden)

- Browser form-fill auto-apply (Easy Apply, ATS portals with no email contact) — planned
  phase 2 of this gate, per §2's reasoning; not started here.
- The `GMAIL_ALERT_SENDERS` allowlist (exact LinkedIn/Naukri sender addresses and digest
  formats) starts as an inspection-based guess, not a validated list — same honesty
  pattern as this project's threshold-calibration notes elsewhere.
- Resume attachment rendering (plain text vs. a real PDF) — format decided at
  implementation time.
- Gmail refresh-token rotation/revocation edge cases beyond the basic connect/disconnect
  flow above.
- Part 2 (on-campus / NEO PAT platform integration) — a separate effort, out of scope here
  by design, not an oversight.

## 11. Gate-table renumbering this doc proposes

| Old | New | Gate |
|---|---|---|
| 10 | 11 | Cloud deployment |
| 11 | 12 | Security + observability |
| 12 | 13 | Final demonstration |
| — | **10** | **Autonomous Application Pipeline — Part 1 (this doc)** |

`docs/SECURITY.md`'s two "(Gate 10)" / "(Gate 11)" references (MongoDB auth before cloud
deployment; OAuth token encryption) should be updated to "(Gate 11)" / "(Gate 12)" to
match, once this renumbering is agreed and applied to `ARCHITECTURE.md`'s gate table.

## 12. Implementation notes (as built)

Everything in §3–§9 is built and tested (backend: 139 tests, 46 of them new for this gate;
frontend: 52 tests, 9 new; `next build` clean). Where the build differs from or goes
beyond the design above, stated plainly:

**Additions beyond the design**
- **Cover note is LLM-generated, and reviewed.** `TailoredResumeResult` gained a
  `cover_note` field, produced in the same strong-LLM call as the tailored resume, under
  the same no-fabrication rules. It's shown on the review screen — the user approves the
  exact email body that will be sent, not a template they never saw.
- **Fabrication is enforced in code, not just the prompt.**
  `resume_tailor.py::find_fabricated_skills` checks every opportunity skill (required,
  preferred, Skill Gap missing/weak) that's absent from the base resume; if the tailored
  text, cover note, or `skills_emphasized` claims one, that attempt is rejected and retried
  (max 2), and if every attempt fabricates, the node fails and the application never
  reaches `READY_TO_APPLY`. Mutation-tested: removing the guard makes
  `test_fabricating_llm_is_rejected_and_application_not_ready` fail.
- **Exactly-once send.** `Application.reviewed_at` is claimed with a single
  `find_one_and_update({_id, reviewed_at: null})`; a double-clicked Approve or a second
  tab gets 409, never a second email (mutation-tested the same way). A failed send releases
  the claim; sends are never auto-retried (a timed-out send may already have gone out).
- **Re-ingestion can't reopen review.** Once an application is `APPLIED` /
  `MANUAL_APPLY_REQUIRED` / `SKIPPED_BY_USER`, the tailor node skips it — the same posting
  reappearing in tomorrow's alert digest can't produce a second application.
- **`POST /api/integrations/gmail/sync`** — runs the poll on demand (demo, and right
  after connecting) instead of waiting up to 15 minutes.
- **Two-step approve in the UI.** "Approve & send" opens a confirm naming the recipient;
  only "Yes, send it" calls the API.

**Decisions §10 left open, now made**
- Resume attachment format: **plain text** (`<name>_Resume_<role>.txt`). Honest about
  what the tailor produces (text); a rendered PDF remains future work.
- Poller dedupe: processed Gmail message IDs per integration (capped at 500) +
  a 2–3 day `newer_than:` window. A message Discovery gives up on is marked processed
  (won't parse next poll either); a Gmail/DB failure is not (retried next poll).
- No-resume / not-eligible: the tailor node no-ops (with `resume_tailor_note` in pipeline
  state for the no-resume case) — no tailored resume, no `READY_TO_APPLY`.

**Verified for real (not just with fakes), 2026-10-03**
- Server boot + all new routes against a real local MongoDB; the `integrations` /
  `tailored_resumes` collections and `uq_integration_user_provider` index are created.
- The Resume Tailor prompt against real Gemini (`LLM_MODEL_STRONG`) on a synthetic resume:
  no fabricated skills, both missing skills surfaced as warnings. This run found three
  issues FakeLLM never could, all fixed: the model flattened the resume into one
  `|`-separated line (would make the diff useless — prompt now requires line structure),
  the cover note inflated claims ("production-ready", "deployed" — prompt now forbids
  unsupported embellishment), and its own warning wording differed from the deterministic
  one, producing duplicate warnings (dedupe now matches by skill name; regression test added).

**After the first live Gmail sync (2026-10-03)**
- Real alerts arrived before the user had a resume on file, so tailoring silently no-op'd
  and no Apply action appeared. Fixed: `POST /api/applications/{id}/tailor` regenerates on
  demand, the detail page shows a "Get ready to apply" card explaining why, and Profile
  now takes the resume as a **file upload** (PDF/TXT; scanned PDFs are flagged).
- Real LinkedIn alerts carry only a posting link, never an apply email — so for most
  real postings, email-apply can't fire. Decision (user's): **assisted apply**, not a
  LinkedIn bot (automation is against LinkedIn's User Agreement and risks the user's
  account). One click on "Apply on LinkedIn" opens the posting, copies the cover note,
  downloads the tailored resume as a **PDF** (`GET /tailored-resume.pdf`, rendered by
  `app/core/resume_pdf.py` with vendored DejaVu Sans for Unicode), and records the
  approval; the user presses Submit on the site and confirms via
  `POST /api/applications/{id}/mark-applied` → `APPLIED`. Email applications now attach
  the same PDF instead of a `.txt`.
- Inbox check against real mail: `jobalerts-noreply@linkedin.com` (30) and
  `jobs-noreply@linkedin.com` (2) confirmed as the real alert senders; LinkedIn's other
  senders (messages, invitations, security) correctly excluded. Naukri senders still
  unconfirmed (no Naukri mail in that inbox).

**Still owed before calling this demo-ready (per §9)**
- A real end-to-end Gmail run: Google Cloud OAuth client (Web application, Gmail API
  enabled, `GMAIL_OAUTH_REDIRECT_URI` registered, your account added as a test user while
  the app is in "Testing" mode), a `TOKEN_ENCRYPTION_KEY` in `.env`, a real LinkedIn/Naukri
  alert ingested, and a real application email sent (to an address you control first).
- `GMAIL_ALERT_SENDERS` is still the inspection-based guess from §10 — confirm the actual
  sender addresses on real alert emails in your inbox.
- Known limitation: one alert email → one opportunity. LinkedIn/Naukri digests often list
  several jobs; Discovery extracts the primary one. Splitting digests into per-job
  postings is the obvious next improvement.
- Phase 2 (browser form-fill for Easy Apply / ATS portals) remains unstarted, as planned.
