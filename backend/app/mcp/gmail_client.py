"""
In-process client for the Gmail MCP server (gmail_server.py). Mirrors github_client.py's
session / BaseExceptionGroup-unwrapping pattern (docs/ARCHITECTURE.md §12).

Retry policy differs deliberately between reads and the send:
- Reads (list/get): timeout + one retry, same as GitHub MCP — safe, idempotent.
- Send: timeout, NO retry. A send that timed out may still have gone through on Google's
  side; retrying could email the same recruiter twice. A failed send is reported to the
  user, who can choose to approve again.
"""
import asyncio
import json
from contextlib import asynccontextmanager

from mcp.shared.memory import create_connected_server_and_client_session

from app.mcp.gmail_server import mcp as gmail_mcp

READ_TIMEOUT_SECONDS = 15.0
SEND_TIMEOUT_SECONDS = 20.0
RETRY_BACKOFF_SECONDS = 1.0


@asynccontextmanager
async def gmail_session():
    async with create_connected_server_and_client_session(gmail_mcp) as session:
        yield session


def _raise_if_error(result, tool_name: str) -> None:
    if result.isError:
        message = result.content[0].text if result.content else f"{tool_name} failed"
        raise RuntimeError(message)


def _unwrap_exception_group(exc: BaseException) -> BaseException:
    if isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        return _unwrap_exception_group(exc.exceptions[0])
    return exc


def _payload(result):
    # list returns arrive in structuredContent["result"] (see github_client.py); dict
    # returns arrive as JSON text (see calendar_client.py). Handle both explicitly.
    if result.structuredContent and "result" in result.structuredContent:
        return result.structuredContent["result"]
    return json.loads(result.content[0].text)


async def _call(tool_name: str, arguments: dict, timeout: float):
    try:
        async with gmail_session() as session:
            result = await asyncio.wait_for(session.call_tool(tool_name, arguments), timeout=timeout)
            _raise_if_error(result, tool_name)
            return _payload(result)
    except BaseExceptionGroup as eg:
        raise _unwrap_exception_group(eg) from eg


async def _call_with_retry(tool_name: str, arguments: dict):
    try:
        return await _call(tool_name, arguments, READ_TIMEOUT_SECONDS)
    except Exception:
        await asyncio.sleep(RETRY_BACKOFF_SECONDS)
        return await _call(tool_name, arguments, READ_TIMEOUT_SECONDS)


async def mcp_list_recent_messages(user_id: str, query: str, max_results: int = 10) -> list[dict]:
    return await _call_with_retry(
        "list_recent_messages", {"user_id": user_id, "query": query, "max_results": max_results}
    )


async def mcp_get_message(user_id: str, message_id: str) -> dict:
    return await _call_with_retry("get_message", {"user_id": user_id, "message_id": message_id})


async def mcp_send_application_email(
    user_id: str, to: str, subject: str, body_text: str, attachment_filename: str, attachment_text: str
) -> dict:
    """Sends an application email. Only the human review route may call this."""
    return await _call(
        "send_message",
        {
            "user_id": user_id,
            "to": to,
            "subject": subject,
            "body_text": body_text,
            "attachment_filename": attachment_filename,
            "attachment_text": attachment_text,
        },
        SEND_TIMEOUT_SECONDS,
    )
