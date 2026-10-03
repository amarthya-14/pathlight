"""
Auth routes: register + login (OAuth2 password flow, JWT bearer tokens), "Continue with
Google", password reset by email, and a brute-force lockout on login.
"""
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

from app.core.config import settings
from app.core.mailer import mail_configured, send_mail
from app.integrations.google_login import build_login_url, fetch_google_identity, login_configured, verify_login_state
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.errors import DuplicateKeyError

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest, Token, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate):
    existing = await User.find_one(User.email == payload.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=(payload.full_name or "").strip() or None,
    )
    try:
        await user.insert()
    except DuplicateKeyError:
        # Backstop against a race between the check above and the insert — the unique
        # index on User.email is the actual source of truth, not the find_one() check.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return user


# Lockout: at most MAX_FAILURES failed logins per email per window. In-memory (one
# process on the free tier); resets on restart, which is acceptable for its purpose —
# slowing password guessing, not perfect accounting.
MAX_FAILURES = 8
FAILURE_WINDOW_S = 15 * 60
_failures: dict[str, deque] = defaultdict(deque)


def _recent_failures(key: str) -> deque:
    q = _failures[key]
    cutoff = time.monotonic() - FAILURE_WINDOW_S
    while q and q[0] < cutoff:
        q.popleft()
    return q


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm uses `username` as the field name; we treat it as email.
    key = form_data.username.strip().lower()
    if len(_recent_failures(key)) >= MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Wait 15 minutes, or reset your password.",
        )
    user = await User.find_one(User.email == form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        _failures[key].append(time.monotonic())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _failures.pop(key, None)
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


# ── Continue with Google ─────────────────────────────────────────────────────────────

def _frontend(path: str, **params: str) -> RedirectResponse:
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{settings.FRONTEND_URL.rstrip('/')}{path}{query}", status_code=status.HTTP_302_FOUND)


@router.get("/google/start")
async def google_start():
    if not login_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in isn't configured on this server.")
    return {"auth_url": build_login_url()}


@router.get("/google/callback", include_in_schema=False)
async def google_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Signs in (or signs up) by verified Google email, then hands the browser a Pathlight
    token in the URL fragment — fragments never reach server logs or Referer headers."""
    if error or not code or not verify_login_state(state or ""):
        return _frontend("/login", google="error")
    try:
        identity = await fetch_google_identity(code)
    except Exception:
        return _frontend("/login", google="error")
    email = (identity.get("email") or "").lower()
    if not email or not identity.get("email_verified"):
        return _frontend("/login", google="unverified")

    user = await User.find_one(User.email == email)
    if user is None:
        # Random unusable password: Google-created accounts sign in with Google, or set a
        # password later through "Forgot password".
        user = User(email=email, hashed_password=hash_password(secrets.token_urlsafe(32)), full_name=identity.get("name"))
        try:
            await user.insert()
        except DuplicateKeyError:
            user = await User.find_one(User.email == email)
    elif not user.full_name and identity.get("name"):
        user.full_name = identity["name"]
        await user.save()
    token = create_access_token(subject=str(user.id))
    return RedirectResponse(
        f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback#token={token}", status_code=status.HTTP_302_FOUND
    )


# ── Password reset ───────────────────────────────────────────────────────────────────

RESET_PURPOSE = "password_reset"


def _reset_token(user: User) -> str:
    # `pw` ties the token to the current password hash: once the password changes, every
    # earlier reset link stops working (one-time use without storing anything).
    return jwt.encode(
        {"sub": str(user.id), "purpose": RESET_PURPOSE, "pw": user.hashed_password[-12:],
         "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: ForgotPasswordRequest, background: BackgroundTasks):
    """Same answer whether or not the email has an account, so this can't be used to
    discover who uses Pathlight."""
    if not mail_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset by email isn't set up yet — use “Continue with Google” with the same email.",
        )
    user = await User.find_one(User.email == payload.email.lower())
    if user is not None:
        link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password#token={_reset_token(user)}"
        background.add_task(
            send_mail,
            user.email,
            "Reset your Pathlight password",
            f"Hi {(user.full_name or '').split(' ')[0] or 'there'},\n\nReset your Pathlight password here (valid for 30 minutes):\n{link}\n\n"
            "If you didn't ask for this, ignore this email — your password stays the same.\n\n— Pathlight",
        )
    return {"detail": "If that email has an account, a reset link is on its way."}


@router.post("/reset-password", response_model=Token)
async def reset_password(payload: ResetPasswordRequest):
    invalid = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or has expired.")
    try:
        data = jwt.decode(payload.token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise invalid
    if data.get("purpose") != RESET_PURPOSE:
        raise invalid
    try:
        user = await User.get(data["sub"])
    except Exception:
        user = None
    if user is None or user.hashed_password[-12:] != data.get("pw"):
        raise invalid
    user.hashed_password = hash_password(payload.password)
    await user.save()
    _failures.pop(user.email.lower(), None)
    return Token(access_token=create_access_token(subject=str(user.id)))


def _user_out(user: User) -> UserOut:
    from app.api.routes.admin import is_admin

    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_admin=is_admin(user),
        ai_keys=[k.model_dump(exclude={"encrypted_key"}) for k in user.ai_keys],
    )


@router.get("/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)


@router.patch("/me", response_model=UserOut)
async def update_current_user(payload: UserUpdate, current_user: User = Depends(get_current_user)):
    # The name is what Pathlight greets you with and signs cover notes with — users who
    # signed up before the name field existed set it during onboarding.
    current_user.full_name = payload.full_name.strip()
    await current_user.save()
    return _user_out(current_user)
