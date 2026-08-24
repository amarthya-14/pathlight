# Pathlight Frontend (Next.js)

**Status:** Scaffolded, no code yet — starts at Gate 8.

## Responsibilities
- Dashboard: Home, Opportunities, Preparation, Applications, AI Insights
- Typed REST client (generated from the FastAPI OpenAPI schema) for reads/writes
- Rendering AI decisions with their evidence/confidence — never hiding uncertainty,
  including flagging when an MCP-sourced evidence field was unavailable

## Explicitly NOT this app's job
- Business rules, ranking logic, AI calls, MCP tool access — all server-side

## Local run (once implemented)
```bash
npm install
npm run dev
```

## Structure
```
src/app/           # Next.js app router pages
src/components/     # UI components
src/lib/            # typed API client, helpers, types
```
