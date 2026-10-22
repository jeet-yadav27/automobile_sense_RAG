
from datetime import datetime, timezone
import hmac

from fastapi import (
    Cookie, Depends, Header, HTTPException
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.security import hash_token
from db.database import get_db
from db.models import User, AuthSession


def get_auth_session(
    warranty_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not warranty_session:
        raise HTTPException(401, "Not authenticated")

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash ==
            hash_token(warranty_session)
        )
    )

    if session is None:
        raise HTTPException(401, "Invalid session")

    if session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")

    return session


def get_current_user(
    session: AuthSession = Depends(get_auth_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, session.user_id)

    if user is None:
        raise HTTPException(401, "User not found")

    return user


def verify_csrf(
    x_csrf_token: str | None = Header(default=None),
    session: AuthSession = Depends(get_auth_session),
) -> None:
    if not x_csrf_token:
        raise HTTPException(403, "CSRF token missing")

    if not hmac.compare_digest(
        hash_token(x_csrf_token),
        session.csrf_token_hash,
    ):
        raise HTTPException(403, "Invalid CSRF token")
