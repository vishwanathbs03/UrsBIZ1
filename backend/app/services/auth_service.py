"""Authentication service.

Handles business logic for registration and login. Token issuance is
done here so the same rules apply regardless of the calling endpoint.

Logout strategy
---------------
Access tokens are stateless JWTs with a 60-minute expiry. There is no
server-side token store by default. ``logout`` therefore issues an
opaque response telling the client to discard its token. Production
deployments that need server-side invalidation can add a Redis-backed
denylist keyed by token ``jti``; the shape of ``create_access_token``
already supports adding a ``jti`` claim when that is introduced.

Sprint 23 — the service also owns ``set_active_business`` so the
``PATCH /auth/me`` route can validate ownership before writing the
FK.
"""

from fastapi import status
from fastapi.exceptions import HTTPException

from app.config.settings import get_settings
from app.models.user import User
from app.repositories.business_repository import BusinessRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.utils.security import create_access_token, hash_password, verify_password


class AuthError(HTTPException):
    """HTTP error with a consistent shape for the auth surface."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(status_code=status_code, detail=detail)


class AuthService:
    """Stateless façade around the user repository for auth flows."""

    def __init__(
        self,
        user_repo: UserRepository,
        business_repo: BusinessRepository | None = None,
    ) -> None:
        """Sprint 23 — the constructor takes both repositories.

        ``user_repo`` is required (every auth flow needs it).
        ``business_repo`` is optional; ``set_active_business`` will
        raise ``AuthError`` if it is called without a business repo.
        Endpoints that never flip the active id (login, register,
        logout) keep the old ``AuthService(UserRepository(db))``
        call site by passing ``business_repo=None``.
        """
        self._repo = user_repo
        self._business_repo = business_repo

    # ---- Registration --------------------------------------------------

    def register(self, payload: RegisterRequest) -> TokenResponse:
        if self._repo.get_by_email(payload.email) is not None:
            raise AuthError("An account with this email already exists.", status.HTTP_409_CONFLICT)

        user = self._repo.create(
            full_name=payload.full_name,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        return self._issue_token(user)

    # ---- Login ---------------------------------------------------------

    def login(self, payload: LoginRequest) -> TokenResponse:
        user = self._repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            # Single message so attackers can't enumerate accounts.
            raise AuthError("Invalid email or password.", status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            raise AuthError("This account is disabled.", status.HTTP_403_FORBIDDEN)
        return self._issue_token(user)

    # ---- Sprint 23 — active business ------------------------------------

    def set_active_business(
        self, user: User, business_id: int | None
    ) -> UserPublic:
        """Stamp ``user.active_business_id`` after validating ownership.

        * ``business_id IS NULL`` — clear the active id, no
          ownership check (deleting the only business clears it
          by the same code path).
        * ``business_id`` matches a business the user owns —
          set it.
        * ``business_id`` matches a row owned by another user —
          ``AuthError(403)`` so we don't leak existence.
        * ``business_id`` does not match any row at all —
          ``AuthError(404)``.
        """
        if self._business_repo is None:
            raise AuthError(
                "Active-business updates require a BusinessRepository.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if business_id is not None:
            owned = self._business_repo.get_by_id_for_owner(
                business_id=business_id, owner_id=user.id
            )
            if owned is None:
                # Disambiguate "doesn't exist" (404) from "owned by
                # someone else" (403). The boolean existence probe
                # tells us which one we're in without leaking any
                # other user's data.
                if not self._business_repo.exists_any_owner(business_id):
                    raise AuthError(
                        f"No business with id={business_id}.",
                        status.HTTP_404_NOT_FOUND,
                    )
                raise AuthError(
                    f"Business id={business_id} is not owned by this user.",
                    status.HTTP_403_FORBIDDEN,
                )

        self._repo.set_active_business(user, business_id)
        self._repo._db.commit()
        self._repo._db.refresh(user)
        return UserPublic.model_validate(user)

    # ---- Internals -----------------------------------------------------

    def _issue_token(self, user: User) -> TokenResponse:
        settings = get_settings()
        token = create_access_token(subject=user.id)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=UserPublic.model_validate(user),
        )
