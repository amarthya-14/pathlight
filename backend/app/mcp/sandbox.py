"""
Shared sandboxing helpers for anything touching the uploads directory — used by both the
REST upload endpoint (app/api/routes/documents.py) and the Filesystem MCP server
(app/mcp/filesystem_server.py), so there is exactly one implementation of "never escape
the sandbox" rather than two that could drift out of sync.
"""
import re
import uuid
from pathlib import Path

from app.core.config import settings

UPLOADS_ROOT = Path(settings.UPLOADS_ROOT).resolve()
UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def user_dir(user_id: str) -> Path:
    """Sandboxed per-user directory. user_id is normally a MongoDB ObjectId string
    (24 hex chars) and already safe, but we don't trust that blindly — normalize
    before using it as a path component regardless of where it came from."""
    safe_user_id = _SAFE_CHARS.sub("_", str(user_id))
    d = UPLOADS_ROOT / safe_user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_filename(original_filename: str) -> str:
    """Strips any directory components and unsafe characters, and prefixes a UUID so
    concurrent uploads with the same name never collide or overwrite each other."""
    base = Path(original_filename).name  # drops any directory path (defeats ../ tricks)
    base = _SAFE_CHARS.sub("_", base) or "file"
    return f"{uuid.uuid4().hex}_{base}"


def resolve_safe_path(user_id: str, filename: str) -> Path:
    """
    Resolves `filename` inside the given user's sandboxed directory, raising ValueError
    if the resolved path would escape that directory (a path traversal attempt). This is
    the single check both the REST layer and the MCP tool rely on — see the regression
    test in tests/test_mcp_filesystem.py.
    """
    base = user_dir(user_id)
    candidate = (base / filename).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError(f"Path traversal attempt blocked: {filename!r} escapes the sandbox")
    return candidate
