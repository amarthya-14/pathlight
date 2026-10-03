"""
Shared FastAPI dependency: resolves the current user from a JWT bearer token.

No DB-session dependency is needed anymore — Beanie documents query against the
globally initialized Motor client directly (see app/core/db.py), unlike SQLAlchemy's
per-request Session pattern.
"""
from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.agents.llm_client import set_user_keys
from app.core.ai_providers import decrypt_keys
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_exception

    try:
        user = await User.get(PydanticObjectId(subject))
    except Exception:
        raise credentials_exception
    if user is None:
        raise credentials_exception
    # Every AI call made while serving this request (and its background tasks) tries the
    # student's own provider keys first, if they added any — see app/agents/llm_client.py.
    set_user_keys(decrypt_keys(user))
    return user
