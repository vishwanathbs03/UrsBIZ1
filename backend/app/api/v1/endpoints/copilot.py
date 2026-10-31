"""AI Business Copilot endpoint.

  * POST /business/copilot/chat  — orchestrate
    the existing engines to answer a free-text
    business question.

The endpoint is a thin wrapper around
:class:`~app.services.copilot.CopilotService`.
The service is responsible for every derivation
rule; the endpoint does:

  1. Authenticate the request (JWT / cookie).
  2. Validate the request body.
  3. Construct the service with the
     request-scoped :class:`BusinessRepository`.
  4. Call ``service.chat(owner_id, message)``.
  5. Translate the service's exceptions into
     HTTP status codes:
       * :class:`BusinessNotFound` → 404
       * :class:`CopilotServiceError` → 500
  6. Validate the resulting dict against the
     response schema so an unhandled code path
     fails loudly at the API boundary, not
     silently in the UI.

Authentication: required. The owner is resolved
from the JWT subject; clients cannot pick an
owner_id.

Database writes: never. The Copilot does not
mutate the business profile or any upstream
service.

What the endpoint does NOT do
-----------------------------

  * call out to OpenAI, Claude, Gemini, Ollama,
    or any LLM
  * store conversation history
  * stream responses
  * use a websocket
  * maintain a chat memory
  * maintain a vector database or embeddings
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.middleware.auth_deps import get_current_user
from app.models.user import User
from app.repositories.business_repository import (
    BusinessNotFound,
    BusinessRepository,
)
from app.schemas.copilot import (
    CopilotRequest,
    CopilotResponse as CopilotResponseSchema,
)
from app.services.copilot import CopilotService, CopilotServiceError
from app.utils.database import get_db


router = APIRouter(prefix="/business", tags=["business-copilot"])


def _service(db: Session = Depends(get_db)) -> CopilotService:
    return CopilotService(BusinessRepository(db))


@router.post(
    "/copilot/chat",
    response_model=CopilotResponseSchema,
    status_code=status.HTTP_200_OK,
    summary=(
        "Chat with the UrsBiz Copilot. The Copilot is a "
        "deterministic orchestrator over the existing engines "
        "(intelligence, scores, DNA, rules, recommendations, "
        "roadmap, knowledge) — it does NOT call a real LLM, "
        "does NOT mutate state, and does NOT store "
        "conversation history."
    ),
)
def post_copilot_chat(
    payload: CopilotRequest,
    current_user: User = Depends(get_current_user),
    service: CopilotService = Depends(_service),
) -> CopilotResponseSchema:
    try:
        result = service.chat(
            owner_id=current_user.id,
            message=payload.message,
        )
    except BusinessNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No business profile for this user yet. "
                "Create a business profile before chatting "
                "with the Copilot."
            ),
        ) from exc
    except CopilotServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    # Validate against the schema so an
    # unhandled code path fails loudly here, not
    # at the client. Pydantic's extra="forbid"
    # surfaces any leaked field.
    return CopilotResponseSchema.model_validate(result)
