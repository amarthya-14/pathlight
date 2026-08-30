# Deployment Strategy

**Status:** Confirmed at Gate 1, updated post-Gate-2 for the MongoDB switch. Executed at
Gate 10.

- **Local/demo target:** Docker Compose (`infra/docker/docker-compose.yml`) — Next.js,
  single FastAPI backend, **MongoDB** (was PostgreSQL — see `ARCHITECTURE.md` §11), Redis,
  Chroma.
- **Stretch target:** free-tier cloud host for the backend (Render/Railway/AWS free tier)
  + **MongoDB Atlas free tier** for the database (easier than self-hosting Mongo in the
  cloud, and gives you auth out of the box — see the open item in `SECURITY.md` about the
  local dev container having no auth).
- **Explicitly out of scope:** Kubernetes — documented as the "how this scales" answer
  for the viva.
- **CI/CD:** GitHub Actions — lint + unit tests on PR (tests run against `mongomock-motor`,
  no real MongoDB needed in CI), build+push image on merge to `main`.
- **Demo reliability note:** the Gmail MCP connection should have a local-file/paste
  fallback path wired in from Gate 4 — don't let a live OAuth/API dependency become a
  single point of failure during the actual demo.
