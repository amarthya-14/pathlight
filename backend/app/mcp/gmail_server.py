"""
Gmail MCP server — Gate 10 (docs/AUTONOMOUS_APPLICATIONS.md §5). Same in-process FastMCP
pattern as the Filesystem/GitHub/Calendar servers.

Tools take a `user_id`, never a token: the server resolves and (if needed) refreshes the
user's own encrypted OAuth token itself (app/integrations/google_oauth.py), so plaintext
tokens never travel through tool arguments, logs, or AgentExecution records.

Two read tools for sourcing, one write tool for applying:
- list_recent_messages / get_message — gmail.readonly.
- send_message — gmail.send. Reachable ONLY via app/mcp/gmail_client.py's
  mcp_send_application_email, which is imported ONLY by the review route; enforced by
  tests/test_gmail_mcp.py::test_send_is_only_reachable_from_review_route, not by convention.

Failure handling: any HTTP error raises — callers decide how to degrade (the poller skips
the message and moves on; the review route reports the failure and leaves the
application in READY_TO_APPLY).
"""
import base64
import html
import re
from email.message import EmailMessage

import httpx
from mcp.server.fastmcp import FastMCP

from app.integrations.google_oauth import get_valid_access_token

mcp = FastMCP("pathlight-gmail")

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_LIST_RESULTS = 25
MAX_BODY_CHARS = 20_000  # Discovery only needs the posting text; caps runaway HTML digests


def _b64url_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="replace")


def _html_to_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", markup)
    # Keep link targets — job-alert digests put the posting URL only in an href, and
    # Discovery needs it for application_url.
    markup = re.sub(r'(?is)<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"\2 (\1)", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def extract_body_text(payload: dict) -> str:
    """Walks a Gmail message payload (possibly nested multipart) and returns its body as
    plain text — text/plain preferred, text/html converted as a fallback. Malformed or
    empty parts are skipped rather than raising, so one odd email can't break a poll."""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if data:
            try:
                decoded = _b64url_decode(data)
            except Exception:
                decoded = ""
            if mime == "text/plain":
                plain_parts.append(decoded)
            elif mime == "text/html":
                html_parts.append(decoded)
        for child in part.get("parts") or []:
            walk(child)

    walk(payload or {})
    if plain_parts:
        text = "\n".join(plain_parts)
    elif html_parts:
        text = _html_to_text("\n".join(html_parts))
    else:
        text = ""
    return text[:MAX_BODY_CHARS]


def _header(headers: list[dict], name: str) -> str | None:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


async def _authed_headers(user_id: str) -> dict:
    token = await get_valid_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


@mcp.tool()
async def list_recent_messages(user_id: str, query: str, max_results: int = 10) -> list[dict]:
    """Lists message IDs matching a Gmail search query (e.g.
    `from:(jobalerts-noreply@linkedin.com OR noreply@naukri.com) newer_than:2d`).
    Read-only. Returns [{"id", "thread_id"}]."""
    max_results = max(1, min(max_results, MAX_LIST_RESULTS))
    headers = await _authed_headers(user_id)
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        response = await http_client.get(
            f"{GMAIL_API_BASE}/messages",
            params={"q": query, "maxResults": max_results},
            headers=headers,
        )
    response.raise_for_status()
    return [
        {"id": m["id"], "thread_id": m.get("threadId")}
        for m in response.json().get("messages", [])
        if m.get("id")
    ]


@mcp.tool()
async def get_message(user_id: str, message_id: str) -> dict:
    """Fetches one message's sender/subject/date and plain-text body. Read-only."""
    headers = await _authed_headers(user_id)
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        response = await http_client.get(
            f"{GMAIL_API_BASE}/messages/{message_id}",
            params={"format": "full"},
            headers=headers,
        )
    response.raise_for_status()
    message = response.json()
    payload = message.get("payload") or {}
    msg_headers = payload.get("headers") or []
    return {
        "id": message.get("id", message_id),
        "from": _header(msg_headers, "From"),
        "subject": _header(msg_headers, "Subject") or "",
        "date": _header(msg_headers, "Date"),
        "snippet": html.unescape(message.get("snippet", "")),
        "body_text": extract_body_text(payload),
    }


def build_raw_message(
    to: str, subject: str, body_text: str, attachment_filename: str | None, attachment_text: str | None
) -> str:
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    # No From header: Gmail sets it to the authenticated account, which is exactly right
    # and avoids any chance of spoofing a different sender.
    msg.set_content(body_text)
    if attachment_filename and attachment_text is not None:
        msg.add_attachment(
            attachment_text.encode("utf-8"),
            maintype="text",
            subtype="plain",
            filename=attachment_filename,
        )
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


@mcp.tool()
async def send_message(
    user_id: str,
    to: str,
    subject: str,
    body_text: str,
    attachment_filename: str | None = None,
    attachment_text: str | None = None,
) -> dict:
    """SENDS AN EMAIL from the user's Gmail account. Irreversible. Only ever invoked by
    the human-approved review route — see module docstring."""
    headers = await _authed_headers(user_id)
    raw = build_raw_message(to, subject, body_text, attachment_filename, attachment_text)
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        response = await http_client.post(
            f"{GMAIL_API_BASE}/messages/send", json={"raw": raw}, headers=headers
        )
    response.raise_for_status()
    sent = response.json()
    return {"id": sent.get("id"), "thread_id": sent.get("threadId")}
