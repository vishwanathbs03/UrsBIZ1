"""Authentication endpoints.

* POST /auth/register  — create account, issue token
* POST /auth/login     — verify credentials, issue token
* POST /auth/logout    — clear the auth cookie
* GET  /auth/me        — return the current user (protected)
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserActiveBusinessUpdate,
    UserPublic,
)
from app.services.auth_service import AuthService
from app.utils.database import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


# ---- Helpers -------------------------------------------------------------


def _set_auth_cookie(response: Response, token: str, max_age: int) -> None:
    """Attach the JWT as an HTTP-only, SameSite cookie.

    Sprint 8 Part 3 — the cookie hardening knobs (HttpOnly,
    Secure, SameSite, path) all read from settings so a
    misconfigured environment is fixable without touching the
    auth code path. The defaults are the OWASP recommendations.
    """
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=max_age,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=settings.cookie_path,
    )


def _clear_auth_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.cookie_name,
        path=settings.cookie_path,
        samesite=settings.cookie_samesite,
    )


def _service(db: Session = Depends(get_db)) -> AuthService:
    # Sprint 23 — the auth service now also needs to look up
    # businesses (so the active-business validator on PATCH /auth/me
    # can confirm the target business belongs to the caller). The
    # BusinessRepository is constructed against the same session so
    # both repositories participate in the same transaction.
    return AuthService(
        user_repo=UserRepository(db),
        business_repo=BusinessRepository(db),
    )


# ---- Routes --------------------------------------------------------------


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    service: AuthService = Depends(_service),
) -> TokenResponse:
    """Create a new user account and return an access token."""
    result = service.register(payload)
    _set_auth_cookie(response, result.access_token, result.expires_in)
    return result


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(_service),
) -> TokenResponse:
    """Verify credentials and return an access token."""
    result = service.login(payload)
    _set_auth_cookie(response, result.access_token, result.expires_in)
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    """Clear the auth cookie.

    Tokens are stateless JWTs. To invalidate server-side, add a
    denylist keyed by ``jti`` and check it in ``get_current_user``.
    See ``app.services.auth_service`` for the documented strategy.
    """
    _clear_auth_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """Return the currently authenticated user."""
    return UserPublic.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserPublic,
    summary="Update fields on the authenticated user (Sprint 23: active_business_id).",
)
def update_me(
    payload: UserActiveBusinessUpdate,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_service),
) -> UserPublic:
    """Sprint 23 — set the user's ``active_business_id``.

    The service validates that the target business belongs to the
    caller (else 403); a missing business id returns 404; ``None``
    is accepted and clears the active id.
    """
    return service.set_active_business(
        user=current_user,
        business_id=payload.active_business_id,
    )
