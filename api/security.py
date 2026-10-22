
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash


password_hasher = PasswordHash.recommended()

SESSION_DURATION = timedelta(days=7)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str
) -> bool:
    return password_hasher.verify(
        password,
        password_hash
    )


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def session_expiration() -> datetime:
    return datetime.now(timezone.utc) + SESSION_DURATION
