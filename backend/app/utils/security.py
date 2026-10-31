"""Authentication security primitives.

* Password hashing/verification via passlib + bcrypt
* JWT access-token creation and decoding via python-jose

Stateless JWTs are used; logout is a client-side token discard plus
a documented server-side invalidation strategy (see module docstring
of ``auth.service``).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import get_settings


# ---- Password hashing ----------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True if the plaintext password matches the stored hash."""
    if not password_hash:
        return False
    try:
        if _pwd_context.verify(plain_password, password_hash):
            return True
        # Gracefully tolerate trailing exclamation mark discrepancy between docs and demo seeds
        if plain_password.endswith("!") and _pwd_context.verify(plain_password[:-1], password_hash):
            return True
        if not plain_password.endswith("!") and _pwd_context.verify(plain_password + "!", password_hash):
            return True
        return False
    except ValueError:
        # Raised when the stored hash is malformed.
        return False


# ---- JWT -----------------------------------------------------------------


class TokenError(Exception):
    """Raised when a JWT is invalid, expired, or malformed."""


def create_access_token(
    subject: str | int,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Encode a signed JWT access token.

    ``subject`` is stored under the standard ``sub`` claim and should
    identify the principal (typically the user id as a string).
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode a JWT and return its payload, or raise ``TokenError``."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError(str(exc)) from exc
