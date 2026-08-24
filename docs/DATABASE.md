# Database Design

**Status:** Conceptual model locked at Gate 0/1. Full DDL is a Gate 2 deliverable.
ORM: SQLAlchemy/SQLModel (Python) — replaces the originally planned JPA/Hibernate since
the backend is now a single Python service.

## Core entities (confirmed)
User, Profile, Skill (+ProfileSkill join), ResumeVersion, Company, Opportunity,
OpportunityRequirement, Application, ApplicationStatus (append-only history),
Deadline, PreparationPlan, PreparationTask (self-referencing for dependencies),
CalendarEvent, Notification, AgentExecution, Document, Integration (now also tracks
MCP tool connection state per user, e.g. Gmail MCP OAuth status).

## Key decisions
- `ApplicationStatus` is append-only — audit trail + timeline UI depend on this.
- `Opportunity` is global (one row per real posting); `Application` is per-user.
  Dedupe happens at the `Opportunity` level (company + role_hash).
- `PreparationTask` self-join gives the dependency graph without a separate graph DB.
- `Integration` rows track which MCP tools are connected and their permission scope,
  so the MCP client layer can check connection state before an agent attempts a call.

Full ERD + DDL to be added here at Gate 2.
