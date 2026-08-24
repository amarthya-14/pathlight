# Infra

**Status:** Scaffolded — docker-compose skeleton only, filled in progressively per gate.

Local Docker Compose setup (4 services once complete: Postgres, Redis, backend, frontend
— reduced from the original 5-service team plan after the backend collapsed to one
service, see `docs/ARCHITECTURE.md` Rev 2) and, later, CI/CD workflow files and free-tier
cloud deployment config. Kubernetes is explicitly out of scope — see `docs/DEPLOYMENT.md`.
