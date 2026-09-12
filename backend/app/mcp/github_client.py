"""
In-process client for the GitHub MCP server (github_server.py). Mirrors
filesystem_client.py's session/exception-unwrapping pattern.

Wraps the call with a timeout and a single retry — per docs/ARCHITECTURE.md §5, every
MCP call gets retry + timeout + a structured failure that degrades gracefully rather
than blocking the caller. One retry (not more): GitHub API failures here are almost
always either a genuine 404 (retrying won't help) or a rate limit (a single retry after
a short backoff is enough for this project's evidence-lookup use case, which isn't
latency-critical) — Skill Gap should proceed without evidence quickly, not stall the
whole pipeline chasing a flaky third-party API.
"""
import asyncio
from contextlib import asynccontextmanager

from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp.github_server import mcp as github_mcp

TOOL_TIMEOUT_SECONDS = 10.0
RETRY_BACKOFF_SECONDS = 1.0


@asynccontextmanager
async def github_session():
    async with create_connected_server_and_client_session(github_mcp) as session:
        yield session


def _raise_if_error(result, tool_name: str) -> None:
    if result.isError:
        message = result.content[0].text if result.content else f"{tool_name} failed"
        raise RuntimeError(message)


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    if isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        return _unwrap_exception_group(exc.exceptions[0])
    return exc


async def _call_search_repos_for_skill(username: str, skill: str) -> list[dict]:
    async with github_session() as session:
        result = await asyncio.wait_for(
            session.call_tool("search_repos_for_skill", {"username": username, "skill": skill}),
            timeout=TOOL_TIMEOUT_SECONDS,
        )
        _raise_if_error(result, "search_repos_for_skill")
        # Verified empirically (see calendar_client.py's docstring for the same lesson
        # with a dict return): a list[dict] FastMCP tool return DOES populate
        # structuredContent, wrapped under a "result" key — matching filesystem_client's
        # mcp_list_documents finding for list[str], not calendar_client's dict finding.
        return result.structuredContent["result"]


async def mcp_search_github_evidence(username: str, skill: str) -> list[dict]:
    """Searches a GitHub user's public repos for evidence of `skill`. Raises after one
    retry on failure — callers (Skill Gap Agent) must catch this and proceed without
    GitHub evidence rather than block, per the MCP failure-handling principle."""
    try:
        try:
            return await _call_search_repos_for_skill(username, skill)
        except BaseExceptionGroup as eg:
            raise _unwrap_exception_group(eg) from eg
    except Exception:
        await asyncio.sleep(RETRY_BACKOFF_SECONDS)
        try:
            return await _call_search_repos_for_skill(username, skill)
        except BaseExceptionGroup as eg:
            raise _unwrap_exception_group(eg) from eg
