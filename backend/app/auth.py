import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from argon2 import PasswordHasher
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import ApiToken, User


password_hasher = PasswordHasher()
serializer = URLSafeTimedSerializer(settings.secret_key, salt="filaflow-session-v1")
SESSION_MAX_AGE = 60 * 60 * 24 * 14


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except Exception:
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_api_token() -> str:
    return f"ff_{secrets.token_urlsafe(32)}"


def set_session(response: Response, user: User) -> str:
    csrf = secrets.token_urlsafe(24)
    signed = serializer.dumps({"uid": str(user.id), "csrf": csrf})
    response.set_cookie("filaflow_session", signed, max_age=SESSION_MAX_AGE, httponly=True, secure=settings.cookie_secure, samesite="lax")
    response.set_cookie("filaflow_csrf", csrf, max_age=SESSION_MAX_AGE, httponly=False, secure=settings.cookie_secure, samesite="lax")
    return csrf


def clear_session(response: Response) -> None:
    response.delete_cookie("filaflow_session")
    response.delete_cookie("filaflow_csrf")


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    filaflow_session: str | None = Cookie(default=None),
) -> User:
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1]
        api_token = db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(raw), ApiToken.revoked_at.is_(None)))
        if not api_token:
            raise HTTPException(401, "Invalid API token")
        api_token.last_used_at = datetime.now(timezone.utc)
        db.commit()
        user = db.get(User, api_token.created_by_id)
        if user and user.active:
            request.state.api_token = api_token
            return user
    if not filaflow_session:
        raise HTTPException(401, "Sign in required")
    try:
        payload = serializer.loads(filaflow_session, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Session expired")
    user = db.get(User, uuid.UUID(payload["uid"]))
    if not user or not user.active:
        raise HTTPException(401, "User is not active")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_header = request.headers.get("x-csrf-token")
        csrf_cookie = request.cookies.get("filaflow_csrf")
        if not csrf_header or csrf_header != csrf_cookie or csrf_header != payload.get("csrf"):
            raise HTTPException(403, "CSRF validation failed")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return user
