"""
Tests for the GitHub MCP server/client (app/mcp/github_server.py,
app/mcp/github_client.py). HTTP calls to the real GitHub API are mocked (via
monkeypatching httpx.AsyncClient.get) — this test suite is hermetic, no real network
access required, same discipline as every other test in this project.
"""
import httpx
import pytest

from app.mcp.github_client import mcp_search_github_evidence

_SAMPLE_REPOS = [
    {
        "name": "django-blog",
        "description": "A blog built with Django",
        "html_url": "https://github.com/octocat/django-blog",
        "language": "Python",
        "topics": ["django", "python"],
    },
    {
        "name": "swift-todo",
        "description": "iOS todo app",
        "html_url": "https://github.com/octocat/swift-todo",
        "language": "Swift",
        "topics": [],
    },
]


def _mock_repos_response(monkeypatch, repos=_SAMPLE_REPOS, status_code=200):
    async def _fake_get(self, url, params=None, headers=None):
        request = httpx.Request("GET", url)
        return httpx.Response(status_code, json=repos, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)


async def test_search_repos_for_skill_matches_by_topic_and_language(client, monkeypatch):
    _mock_repos_response(monkeypatch)

    matches = await mcp_search_github_evidence("octocat", "Django")

    assert len(matches) == 1
    assert matches[0]["name"] == "django-blog"
    assert matches[0]["language"] == "Python"


async def test_search_repos_for_skill_no_match_returns_empty_list(client, monkeypatch):
    _mock_repos_response(monkeypatch)

    matches = await mcp_search_github_evidence("octocat", "Kubernetes")

    assert matches == []


async def test_search_repos_for_skill_propagates_failure_after_retry(client, monkeypatch):
    async def _fake_get_404(self, url, params=None, headers=None):
        request = httpx.Request("GET", url)
        return httpx.Response(404, json={"message": "Not Found"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get_404)

    with pytest.raises(RuntimeError):
        await mcp_search_github_evidence("no-such-user-xyz", "Python")
