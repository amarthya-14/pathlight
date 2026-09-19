"""decode_access_token (app/core/security.py) failure branches — added at Gate 9."""
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings
from app.core.security import decode_access_token


def test_decode_rejects_garbage_token():
    assert decode_access_token("not-a-real-jwt") is None


def test_decode_rejects_expired_token():
    expired = jwt.encode(
        {"sub": "someone", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(expired) is None
