"""
GitHub MCP server — Gate 6. Read-only, public-repo evidence lookup for the Skill Gap
Agent (docs/ARCHITECTURE.md §5's tool table).

Scope decision, stated plainly: the architecture table describes GitHub MCP as
"public repos + explicitly connected private repos." Private-repo access needs a real
per-user GitHub OAuth flow, and per docs/SECURITY.md no MCP tool in this project has a
real OAuth flow yet — building one just for this, without the token-encryption
infrastructure Gate 11 is supposed to add, would mean either plaintext token storage or
ad hoc encryption bolted on outside its intended gate. Deferred, same reasoning as
Calendar MCP's scope note (app/models/calendar_event.py). This gate builds public-repo
read access only, using GitHub's unauthenticated REST API (optionally with a shared
GITHUB_MCP_TOKEN app-level PAT purely for higher rate limits, NOT per-user OAuth).

Failure handling: any HTTP error (user not found, rate limited, network failure) raises
— the caller (Skill Gap Agent) is responsible for catching this and proceeding without
GitHub evidence rather than blocking, per §5's MCP failure principle.
"""
import httpx
from mcp.server.fastmcp import FastMCP

from app.core.config import settings

mcp = FastMCP("pathlight-github")

GITHUB_API_BASE = "https://api.github.com"


@mcp.tool()
async def search_repos_for_skill(username: str, skill: str) -> list[dict]:
    """
    Lists a GitHub user's public repos whose name, description, primary language, or
    topics mention `skill` (case-insensitive substring match — deterministic, no LLM).
    Raises on any HTTP/network failure rather than returning an empty list, so the
    caller can distinguish "checked, found nothing" from "couldn't check".
    """
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_MCP_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_MCP_TOKEN}"

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        response = await http_client.get(
            f"{GITHUB_API_BASE}/users/{username}/repos",
            params={"per_page": 100, "type": "owner"},
            headers=headers,
        )
    response.raise_for_status()
    repos = response.json()

    skill_lower = skill.strip().lower()
    matches = []
    for repo in repos:
        haystack = " ".join(
            filter(
                None,
                [
                    repo.get("name", ""),
                    repo.get("description") or "",
                    repo.get("language") or "",
                    " ".join(repo.get("topics", []) or []),
                ],
            )
        ).lower()
        if skill_lower in haystack:
            matches.append(
                {
                    "name": repo.get("name"),
                    "url": repo.get("html_url"),
                    "language": repo.get("language"),
                    "description": repo.get("description"),
                }
            )

    return matches[:3]  # a handful of corroborating examples, not an exhaustive dump
