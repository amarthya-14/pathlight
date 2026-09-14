"""
Preparation Planner Agent tests (app/agents/planner.py). No LLM/embedding fakes needed
here — the agent is entirely deterministic (see its module docstring for why).

Every test still takes the `client` fixture even though generate_preparation_plan()
itself makes no DB call: constructing a PreparationPlan (a Beanie Document, not a plain
pydantic model) raises beanie.exceptions.CollectionWasNotInitialized unless Beanie has
been initialized first — verified empirically, not assumed, the same discipline this
codebase applies to every other MCP/ORM behavioral assumption.
"""
from datetime import datetime, timedelta, timezone

from app.agents.planner import (
    DEFAULT_SKILL_EFFORT_HOURS,
    WEAK_SKILL_EFFORT_MULTIPLIER,
    compute_available_hours,
    generate_preparation_plan,
)
from app.models.agent_execution import AgentExecution
from app.agents.planner import run_planner


async def test_prerequisite_ordering_respects_dependency_chain(client):
    # Spring Boot depends on Java, REST APIs depends on Spring Boot (per
    # SKILL_PREREQUISITES) — deliberately listed out of order here to prove the
    # topological sort, not just input-order pass-through.
    plan = generate_preparation_plan(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["REST APIs", "Java", "Spring Boot"],
        weak_skills=[],
        deadline=None,
        available_hours=None,
    )
    order = [t.skill for t in plan.tasks]
    assert order.index("Java") < order.index("Spring Boot") < order.index("REST APIs")

    tasks_by_skill = {t.skill: t for t in plan.tasks}
    assert tasks_by_skill["Java"].depends_on == []
    assert tasks_by_skill["Spring Boot"].depends_on == [tasks_by_skill["Java"].id]
    assert tasks_by_skill["REST APIs"].depends_on == [tasks_by_skill["Spring Boot"].id]


async def test_unknown_skill_gets_standalone_task_with_default_effort(client):
    plan = generate_preparation_plan(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["Some Totally Unheard Of Framework"],
        weak_skills=[],
        deadline=None,
        available_hours=None,
    )
    assert len(plan.tasks) == 1
    task = plan.tasks[0]
    assert task.depends_on == []
    assert task.estimated_hours == DEFAULT_SKILL_EFFORT_HOURS


async def test_weak_skill_gets_reduced_effort_vs_missing(client):
    plan = generate_preparation_plan(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["Docker"],
        weak_skills=["Git"],
        deadline=None,
        available_hours=None,
    )
    tasks_by_skill = {t.skill: t for t in plan.tasks}
    # Git and Docker have different base efforts, so compare each against its own base
    # rather than against each other directly.
    from app.agents.planner import SKILL_EFFORT_HOURS

    assert tasks_by_skill["Git"].estimated_hours == round(
        SKILL_EFFORT_HOURS["git"] * WEAK_SKILL_EFFORT_MULTIPLIER, 1
    )
    assert tasks_by_skill["Docker"].estimated_hours == SKILL_EFFORT_HOURS["docker"]


async def test_feasibility_flag_reflects_available_hours(client):
    infeasible = generate_preparation_plan(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["Java", "Kubernetes"],
        weak_skills=[],
        deadline=None,
        available_hours=1.0,
    )
    assert infeasible.feasible is False

    feasible = generate_preparation_plan(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["Git"],
        weak_skills=[],
        deadline=None,
        available_hours=100.0,
    )
    assert feasible.feasible is True

    unknown = generate_preparation_plan(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["Git"],
        weak_skills=[],
        deadline=None,
        available_hours=None,
    )
    assert unknown.feasible is None


def test_compute_available_hours_clamps_past_deadline_to_zero():
    past_deadline = datetime.now(timezone.utc) - timedelta(days=5)
    assert compute_available_hours(past_deadline, hours_per_day=2.0) == 0.0


def test_compute_available_hours_none_deadline_returns_none():
    assert compute_available_hours(None, hours_per_day=2.0) is None


async def test_run_planner_never_calls_an_llm_and_logs_agent_execution(client):
    # No FakeLLM monkeypatching anywhere in this test — if the Planner Agent called an
    # LLM at all, there'd be nothing faking it and this test would either fail (real
    # network egress blocked) or hang. Passing at all is itself proof of the "no LLM
    # call" design decision (see app/agents/planner.py's module docstring), the same
    # verification style Eligibility's never-calls-the-LLM tests use.
    plan, execution = await run_planner(
        user_id="507f1f77bcf86cd799439011",
        opportunity_id="507f1f77bcf86cd799439012",
        application_id="507f1f77bcf86cd799439013",
        missing_skills=["Python"],
        weak_skills=[],
        deadline=None,
        available_hours=None,
    )
    assert execution.agent_name == "planner"
    assert execution.method == "deterministic"
    assert execution.status == "success"

    logged = await AgentExecution.get(execution.id)
    assert logged is not None
    assert plan.tasks[0].skill == "Python"
