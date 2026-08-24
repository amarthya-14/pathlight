# Deployment Strategy

**Status:** Confirmed at Gate 1. Executed at Gate 10.

- **Local/demo target:** Docker Compose (`infra/docker/docker-compose.yml`) — Next.js,
  single FastAPI backend, PostgreSQL, Redis, Chroma. (Reduced from a 5-service compose
  file to 4 after the backend collapse in Rev 2.)
- **Stretch target:** free-tier cloud host (Render/Railway/AWS free tier), same containers.
- **Explicitly out of scope:** Kubernetes — documented as the "how this scales" answer
  for the viva.
- **CI/CD:** GitHub Actions — lint + unit tests on PR, build+push image on merge to `main`.
- **Demo reliability note:** the Gmail MCP connection should have a local-file/paste
  fallback path wired in from Gate 4 — don't let a live OAuth/API dependency become a
  single point of failure during the actual demo.
