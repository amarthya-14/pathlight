"""
Tests for the Filesystem MCP server/client (app/mcp/filesystem_server.py,
app/mcp/filesystem_client.py) — verifying the standardized MCP tool-calling interface
actually works end-to-end, and that it can't be used to escape the sandbox, independent
of any agent (no agent exists yet — that's Gate 4).
"""
import pytest

from app.mcp.filesystem_client import mcp_list_documents, mcp_read_document


def _auth_headers(client, email="mcp-user@example.com", password="testpass123"):
    client.post("/api/auth/register", json={"email": email, "password": password})
    login_resp = client.post("/api/auth/login", data={"username": email, "password": password})
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _current_user_id(client, headers) -> str:
    resp = client.get("/api/auth/me", headers=headers)
    return resp.json()["id"]


async def test_mcp_read_document_matches_upload(client):
    headers = _auth_headers(client)
    user_id = _current_user_id(client, headers)

    create_resp = client.post(
        "/api/documents/paste",
        json={"doc_type": "resume", "title": "MCP Test Doc", "text": "Content read via MCP, not REST."},
        headers=headers,
    )
    storage_filename = create_resp.json()["storage_filename"]

    content = await mcp_read_document(user_id, storage_filename)
    assert content == "Content read via MCP, not REST."


async def test_mcp_list_documents_returns_uploaded_files(client):
    headers = _auth_headers(client)
    user_id = _current_user_id(client, headers)

    client.post(
        "/api/documents/paste",
        json={"doc_type": "resume", "title": "Doc One", "text": "one"},
        headers=headers,
    )
    client.post(
        "/api/documents/paste",
        json={"doc_type": "resume", "title": "Doc Two", "text": "two"},
        headers=headers,
    )

    filenames = await mcp_list_documents(user_id)
    assert len(filenames) == 2


async def test_mcp_read_document_rejects_path_traversal(client):
    headers = _auth_headers(client)
    user_id = _current_user_id(client, headers)

    # No document upload needed — the traversal attempt should be rejected before any
    # file lookup happens, based purely on the requested filename shape.
    with pytest.raises(RuntimeError, match="Path traversal attempt blocked"):
        await mcp_read_document(user_id, "../../etc/passwd")


async def test_mcp_read_document_missing_file_raises(client):
    headers = _auth_headers(client)
    user_id = _current_user_id(client, headers)

    with pytest.raises(RuntimeError, match="No such document"):
        await mcp_read_document(user_id, "does-not-exist.txt")
