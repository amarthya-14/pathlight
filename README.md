# Pathlight

**Autonomous Career & Opportunity Intelligence Platform** — solo capstone project.

Pathlight continuously monitors a student's professional ecosystem — resumes, placement
emails, skills, deadlines — and proactively surfaces ranked opportunities, skill gaps,
preparation plans, and application tracking. It is not a chatbot or a resume grader; it
is an event-driven, agentic system with MCP-based tool access at its core.

> Formerly prototyped under the working name "OIE." Renamed to **Pathlight** at Gate 1.
> Originally scoped for a 4-person team with a Spring Boot + FastAPI split; now built
> solo as a single FastAPI + LangGraph + MCP service. See `docs/ARCHITECTURE.md` Rev 2.

## Status

Gate 1 complete (architecture finalized, repo scaffolded). No feature implementation yet.

## Repository Structure

```
pathlight/
├── backend/          # FastAPI + LangGraph + MCP — single service: API, agents, tools, DB
├── frontend/          # Next.js — dashboard
├── infra/              # Docker Compose, deployment config
└── docs/                # Architecture, API, database, AI design, security, evaluation, deployment
```

## Quick Start (once components exist)

```bash
cp .env.example .env      # fill in required values
docker compose -f infra/docker/docker-compose.yml up
```

Functional starting Gate 2. Right now these are stubs.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full system architecture (Rev 2: solo + MCP-central) |
| [docs/API.md](docs/API.md) | REST API design |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema, entities, relationships |
| [docs/AI_DESIGN.md](docs/AI_DESIGN.md) | Agent architecture, LangGraph state graph, MCP tool plan, model routing |
| [docs/SECURITY.md](docs/SECURITY.md) | Auth, secrets, privacy model |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Benchmark datasets, metrics |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Local + cloud deployment |

## Development Gates

Gated development process (Gate 0 → Gate 12) — see `docs/ARCHITECTURE.md` §8. Gates are
strictly sequential now (solo project, no parallel team lanes) — don't start a gate while
the previous one is unstable.

## License

TBD — add before any public release.
