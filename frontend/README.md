# Pathlight Frontend (Next.js)

**Status:** Gate 8 done — Home, Opportunities, Applications, and Preparation Plan
screens all implemented and manually verified end-to-end against the real backend, real
MongoDB, and real Gemini API. See `docs/ARCHITECTURE.md` §16 for the full writeup.

## Stack

Next.js 16 (App Router) + React 19 + TypeScript 7 + Tailwind CSS 4. No OpenAPI codegen —
a hand-written typed fetch client (`src/lib/api.ts`, `src/lib/types.ts`) instead, kept in
sync with `backend/app/schemas/*.py` by hand (no build-time check ties the two
together yet — a real, stated gap, not hidden).

## Responsibilities

- Dashboard: Home, Opportunities, Applications, Preparation Plan, Profile
- Typed REST client for reads/writes against the FastAPI backend
- Rendering AI decisions with their evidence/confidence — never hiding uncertainty,
  including prominently surfacing `skill_gap_note` when a resume-less Skill Gap result
  would otherwise look like real evidence (see `EligibilityCard`/`SkillGapCard`)

## Explicitly NOT this app's job

- Business rules, ranking logic, AI calls, MCP tool access — all server-side

## Local run

```bash
npm install
cp .env.local.example .env.local   # or just: echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Requires the backend running at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
with `CORS_ORIGINS` including this app's origin (default `http://localhost:3000` — see
`backend/app/core/config.py`). Without matching CORS config, every request fails at the
browser's preflight step with no obvious error in the Network tab unless you know to
check for it — this is a real bug that was found and fixed during Gate 8 (see
`docs/ARCHITECTURE.md` §16), not a hypothetical.

## Testing

No automated frontend test suite yet — `npx tsc --noEmit` and `npm run build` are
verified clean, and the critical path (register → profile → resume → ingest → view
Eligibility/Skill Gap/Preparation Plan/Applications) was manually verified in a real
browser against the real backend. An automated E2E test (Playwright/Cypress) is
explicitly Gate 9 scope, not done here.

## Structure

```
src/app/            # Next.js app router pages (one folder per route)
src/components/      # Sidebar, Shell, EligibilityCard, SkillGapCard, StatusTimeline,
                       # ui.tsx (shared primitives: Button, Field, StatCard, EmptyState, …)
src/lib/              # api.ts (typed fetch client), types.ts, auth-context.tsx
```
