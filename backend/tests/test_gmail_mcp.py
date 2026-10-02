"""
Gate 10: Gmail MCP server/client (app/mcp/gmail_server.py, gmail_client.py), with Gmail's
REST API faked at the httpx level. Includes the structural guarantee that the send tool
is unreachable from anywhere except the human review route.
"""
import ast
import base64
import email
import email.policy
from pathlib import Path

import pytest

import app.mcp.gmail_client as gmail_client
from app.mcp.gmail_client import mcp_get_message, mcp_list_recent_messages, mcp_send_application_email
from app.mcp.gmail_server import extract_body_text
from tests.gmail_fakes import ACCESS_TOKEN, FakeGoogle, b64, configure_oauth, connect_gmail, gmail_message

APP_ROOT = Path(__file__).resolve().parent.parent / "app"


def _register(client, email_addr="gmail-mcp-user@example.com"):
    client.post("/api/auth/register", json={"email": email_addr, "password": "testpass123"})
    login = client.post("/api/auth/login", data={"username": email_addr, "password": "testpass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return client.get("/api/auth/me", headers=headers).json()["id"]


async def test_list_and_get_message(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle(
        [gmail_message("m1", "Backend Intern at Acme", "Acme is hiring. Apply: jobs@acme.dev")]
    ).install(monkeypatch)
    user_id = _register(client)
    await connect_gmail(user_id)

    listed = await mcp_list_recent_messages(user_id, "from:jobalerts-noreply@linkedin.com", 5)
    assert listed == [{"id": "m1", "thread_id": "t-m1"}]

    message = await mcp_get_message(user_id, "m1")
    assert message["subject"] == "Backend Intern at Acme"
    assert message["from"] == "jobalerts-noreply@linkedin.com"
    assert "jobs@acme.dev" in message["body_text"]

    # The token goes in the Authorization header — never in a tool argument.
    _m, _url, kw = google.requests[0]
    assert kw["headers"]["Authorization"] == f"Bearer {ACCESS_TOKEN}"


async def test_read_fails_cleanly_when_gmail_not_connected(client, monkeypatch):
    configure_oauth(monkeypatch)
    FakeGoogle().install(monkeypatch)
    monkeypatch.setattr(gmail_client, "RETRY_BACKOFF_SECONDS", 0)
    user_id = _register(client)

    with pytest.raises(RuntimeError, match="not connected"):
        await mcp_list_recent_messages(user_id, "anything", 5)


async def test_auth_failure_propagates(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    google.unauthorized = True
    monkeypatch.setattr(gmail_client, "RETRY_BACKOFF_SECONDS", 0)
    user_id = _register(client)
    await connect_gmail(user_id)

    with pytest.raises(RuntimeError):
        await mcp_list_recent_messages(user_id, "anything", 5)


async def test_send_builds_mime_with_resume_attachment(client, monkeypatch):
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    user_id = _register(client)
    await connect_gmail(user_id)

    sent = await mcp_send_application_email(
        user_id, "jobs@acme.dev", "Application for Backend Intern", "Dear Hiring Team, ...", "Resume.pdf", b"%PDF-1.4 fake"
    )
    assert sent["id"] == "sent-123"
    assert len(google.sent) == 1

    raw = base64.urlsafe_b64decode(google.sent[0]["raw"] + "==")
    parsed = email.message_from_bytes(raw, policy=email.policy.default)
    assert parsed["To"] == "jobs@acme.dev"
    assert parsed["From"] is None  # Gmail sets it to the authenticated account
    parts = list(parsed.iter_parts())
    assert "Dear Hiring Team" in parts[0].get_content()
    assert parts[1].get_filename() == "Resume.pdf"
    assert parts[1].get_content_type() == "application/pdf"
    assert parts[1].get_content() == b"%PDF-1.4 fake"


async def test_send_is_never_retried(client, monkeypatch):
    """A timed-out/failed send may have gone through — retrying risks a duplicate email."""
    configure_oauth(monkeypatch)
    google = FakeGoogle().install(monkeypatch)
    google.fail_send = True
    user_id = _register(client)
    await connect_gmail(user_id)

    with pytest.raises(Exception):
        await mcp_send_application_email(user_id, "jobs@acme.dev", "s", "b", "r.pdf", b"r")
    assert len(google.sent) == 1


def test_extract_body_prefers_plain_text_and_handles_nesting():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": b64("plain version")}},
                    {"mimeType": "text/html", "body": {"data": b64("<b>html version</b>")}},
                ],
            }
        ],
    }
    assert extract_body_text(payload) == "plain version"


def test_extract_body_html_fallback_keeps_link_targets():
    markup = '<p>SDE Intern</p><a href="https://www.linkedin.com/jobs/view/123">View job</a><style>x{}</style>'
    payload = {"mimeType": "text/html", "body": {"data": b64(markup)}}
    text = extract_body_text(payload)
    assert "SDE Intern" in text
    assert "https://www.linkedin.com/jobs/view/123" in text
    assert "x{}" not in text


def test_extract_body_tolerates_malformed_parts():
    payload = {"mimeType": "multipart/mixed", "parts": [{"mimeType": "text/plain", "body": {"data": "!!!not-base64"}}, {}]}
    assert isinstance(extract_body_text(payload), str)
    assert extract_body_text({}) == ""


def test_send_is_only_reachable_from_review_route():
    """Structural guarantee for docs/AUTONOMOUS_APPLICATIONS.md §5: the only module that
    may import the send function is the review route. If this fails, something other
    than an explicit human approval could send email on the user's behalf."""
    allowed = {APP_ROOT / "mcp" / "gmail_client.py", APP_ROOT / "api" / "routes" / "applications.py"}
    offenders = []
    for path in APP_ROOT.rglob("*.py"):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.Name):
                names = [node.id]
            elif isinstance(node, ast.Attribute):
                names = [node.attr]
            if "mcp_send_application_email" in names and path not in allowed:
                offenders.append(str(path))
        # The raw tool name, called through a session directly, would bypass the wrapper.
        if '"send_message"' in source and path.name not in {"gmail_client.py"}:
            offenders.append(f"{path} (raw send_message tool call)")
    assert offenders == []
