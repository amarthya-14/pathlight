"""
Password hashing and JWT creation/verification.
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


ACCESS_TYPE = "access"


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "typ": ACCESS_TYPE}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the subject (user id as str) if `token` is a valid ACCESS token, else None.
    Other tokens signed with the same secret (OAuth state, password reset) carry a
    `purpose` claim and are rejected here — an OAuth state travels through Google's
    redirect URL, and must never work as a login. Tokens issued before `typ` existed
    (no typ, no purpose) are still accepted until they expire."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("purpose") is not None or payload.get("typ", ACCESS_TYPE) != ACCESS_TYPE:
        return None
    return payload.get("sub")
