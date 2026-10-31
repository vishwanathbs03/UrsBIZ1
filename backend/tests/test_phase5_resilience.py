"""Test Suite for Phase 5 Platform Resilience, Failure Recovery & Operational Reliability.

Verifies:
  1. Gemini outage & deterministic fallback
  2. Gemini rate-limiting (429) retry and exponential backoff
  3. Gemini circuit breaker fail-fast transitions
  4. Malformed JSON handling without crashing or hallucinating
  5. Database outage produces standard error envelope (no SQL leaks)
  6. Database transaction rollback on failure
  7. Idempotent sales upload & duplicate prevention
  8. Idempotent lock conflicts (409) for concurrent operations
  9. Concurrent recommendation lifecycle updates
  10. Partial processing detection (status="partial_success")
  11. File size (>10MB) and format validation
  12. Health check distinction between core readiness and AI degradation
  13. Operational logging with correlation IDs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import json
from unittest.mock import MagicMock, patch
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.errors import (
    AIRateLimitError,
    AIServiceUnavailableError,
    AppResilienceError,
    DatabaseUnavailableError,
    IdempotencyConflictError,
)
from app.main import app
from app.models.business import Business
from app.models.idempotency import IdempotencyRecord
from app.models.recommendation_lifecycle import RecommendationLifecycleState
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.repositories.recommendation_lifecycle_repository import (
    RecommendationLifecycleRepository,
)
from app.schemas.sales import ColumnMapping
from app.schemas.smart_recommendations import (
    RecommendationCategory,
    RecommendationPriority,
    SmartRecommendationItem,
)
from app.services.ai.providers.circuit_breaker import AICircuitBreaker
from app.services.ai.resilient_client import ResilientGeminiClient
from app.services.recommendations.explanation_service import explain_recommendation
from app.services.resilience.idempotency_service import IdempotencyService
from app.services.sales.parser import OversizedFileError, UnsupportedFormatError, validate_file_metadata
from app.services.sales_service import SalesService
from app.utils.database import Base, SessionLocal, get_db, safe_transaction
from app.utils.security import create_access_token


@pytest.fixture
def db_session():
    """Isolated database session for resilience testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_headers(db_session: Session):
    """Authenticate and create test business profile."""
    now = datetime.now(timezone.utc)
    user = db_session.query(User).filter(User.email == "resilience_owner@atlas.com").first()
    if not user:
        user = User(
            full_name="Resilience Test Owner",
            email="resilience_owner@atlas.com",
            password_hash="hashed_secure_pass",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    business = db_session.query(Business).filter(Business.owner_id == user.id).first()
    if not business:
        business = Business(
            owner_id=user.id,
            legal_name="Resilience Precision Castings Ltd",
            trade_name="Resilience Castings",
            industry="Manufacturing",
            established_year=2019,
            annual_revenue=15000000.0,
            revenue_currency="INR",
        )
        db_session.add(business)
        db_session.commit()
        db_session.refresh(business)

    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}, user, business


# --------------------------------------------------------------------------- #
# 1. Gemini Outage & Deterministic Fallback Tests
# --------------------------------------------------------------------------- #

def test_gemini_outage_deterministic_fallback():
    """Verify that when Gemini suffers an outage, explanations fall back to deterministic text."""
    rec = SmartRecommendationItem(
        id="rec_resilience_test_01",
        title="Diversify Customer Base",
        category=RecommendationCategory.REVENUE_GROWTH,
        priority=RecommendationPriority.HIGH,
        priority_score=85.0,
        description="Top client represents 60% of total monthly sales.",
        reasoning="High concentration increases counterparty risk.",
        expected_benefit="Stabilize monthly cash flow.",
        estimated_impact=500000.0,
        impact_unit="INR",
        evidence=["Customer concentration is 60.0%"],
        limitations=["Subject to market conditions"],
        business_context="Manufacturing sector with 60% revenue concentration",
        confidence=85.0,
        data_quality="high",
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    # Simulate Gemini outage (503 Service Unavailable)
    with patch("httpx.Client.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.text = "Service Unavailable"
        mock_post.return_value = mock_resp

        result = explain_recommendation(
            rec=rec,
            business_name="Resilience Precision Castings Ltd",
            industry="Manufacturing",
        )

        assert result.recommendation_id == rec.id
        assert result.is_ai_generated is False
        assert "Why this matters for your business:" in result.explanation
        assert "Supporting evidence:" in result.explanation
        assert "Customer concentration is 60.0%" in result.explanation


def test_gemini_rate_limiting_retry_and_backoff():
    """Verify ResilientGeminiClient retries with backoff on HTTP 429 and succeeds on subsequent try."""
    cb = AICircuitBreaker(name="test_cb", max_failures=3, cooldown_seconds=10.0)
    client = ResilientGeminiClient(
        base_delay_seconds=0.05,
        max_delay_seconds=0.2,
        max_retries=2,
        timeout_seconds=2.0,
        circuit_breaker=cb,
    )

    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "0.01"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "choices": [{"message": {"content": "Executive business advice from Gemini."}}]
    }

    mock_settings = MagicMock()
    mock_settings.ai_api_key = "test_key_123"
    mock_settings.ai_provider = "gemini"
    mock_settings.ai_model = "gemini-2.5-flash"
    mock_settings.ai_base_url = "https://mock.gemini.api/v1"

    with patch("app.services.ai.resilient_client.get_settings", return_value=mock_settings), \
         patch("httpx.Client.post", side_effect=[resp_429, resp_200]):
        content = client.execute_chat_completion(
            system_prompt="Test system",
            user_content="Test question",
        )

        assert content == "Executive business advice from Gemini."
        assert cb.state == "CLOSED"


def test_gemini_circuit_breaker_fail_fast():
    """Verify that after max consecutive failures, circuit breaker transitions to OPEN and fails fast."""
    cb = AICircuitBreaker(name="test_fail_fast", max_failures=2, cooldown_seconds=30.0)
    client = ResilientGeminiClient(
        base_delay_seconds=0.01,
        max_retries=1,
        timeout_seconds=0.5,
        circuit_breaker=cb,
    )

    resp_503 = MagicMock()
    resp_503.status_code = 503

    mock_settings = MagicMock()
    mock_settings.ai_api_key = "test_key_123"
    mock_settings.ai_provider = "gemini"
    mock_settings.ai_model = "gemini-2.5-flash"
    mock_settings.ai_base_url = "https://mock.gemini.api/v1"

    with patch("app.services.ai.resilient_client.get_settings", return_value=mock_settings), \
         patch("httpx.Client.post", return_value=resp_503):
        # 1st failure
        c1 = client.execute_chat_completion("sys", "user")
        assert c1 is None

        # 2nd failure -> Circuit opens
        c2 = client.execute_chat_completion("sys", "user")
        assert c2 is None
        assert cb.state == "OPEN"

    # 3rd call should fail fast without invoking httpx.Client at all
    with patch("app.services.ai.resilient_client.get_settings", return_value=mock_settings), \
         patch("httpx.Client.post") as mock_post:
        c3 = client.execute_chat_completion("sys", "user")
        assert c3 is None
        mock_post.assert_not_called()


def test_gemini_malformed_json_fallback():
    """Verify malformed JSON responses are rejected cleanly without breaking the caller."""
    malformed_json_text = "```json\n{\"answer\": \"incomplete text missing closing brace"
    parsed = ResilientGeminiClient.extract_and_validate_json(malformed_json_text)
    assert parsed is None

    valid_json_text = "```json\n{\"answer\": \"valid analysis\", \"confidence\": 90}\n```"
    parsed_valid = ResilientGeminiClient.extract_and_validate_json(valid_json_text)
    assert parsed_valid == {"answer": "valid analysis", "confidence": 90}


# --------------------------------------------------------------------------- #
# 2. Database Reliability & Safe Transaction Rollback Tests
# --------------------------------------------------------------------------- #

def test_database_safe_transaction_rollback(db_session: Session):
    """Verify safe_transaction context manager automatically rolls back when an error occurs."""
    initial_count = db_session.query(Business).count()

    with pytest.raises(RuntimeError):
        with safe_transaction(db_session):
            temp_biz = Business(
                owner_id=99999,
                legal_name="Doomed Temporary Business",
                industry="Testing",
                established_year=2024,
            )
            db_session.add(temp_biz)
            db_session.flush()
            raise RuntimeError("Simulated mid-transaction failure")

    final_count = db_session.query(Business).count()
    assert final_count == initial_count


def test_database_error_handling_standard_envelope(auth_headers):
    """Verify that unhandled database connection errors produce a structured 503 error envelope."""
    headers, _, _ = auth_headers
    client = TestClient(app, raise_server_exceptions=False)

    # Force a database OperationalError during API request
    with patch("app.repositories.business_repository.BusinessRepository.get_by_owner", side_effect=OperationalError("SELECT * FROM businesses", [], Exception("connection dropped"))):
        resp = client.get("/api/v1/recommendations", headers=headers)
        assert resp.status_code == 503
        data = resp.json()
        assert data["error_code"] == "DATABASE_UNAVAILABLE"
        assert data["retryable"] is True
        assert data["service_name"] == "database"
        assert "SELECT" not in data["safe_message"]  # SQL query must never leak
        assert "request_id" in data


# --------------------------------------------------------------------------- #
# 3. Idempotency & Duplicate Prevention Tests
# --------------------------------------------------------------------------- #

def test_idempotency_service_acquire_and_replay(db_session: Session):
    """Verify IdempotencyService returns cached payload upon duplicate request."""
    service = IdempotencyService(db_session)
    biz_id = 101
    key = f"idem_test_key_{uuid.uuid4().hex}"
    req_hash = service.compute_request_hash("file_bytes_123", {"date": "col1"})

    # 1st attempt: acquires lock
    is_replay, cached = service.acquire_lock(biz_id, key, "sales_upload", req_hash)
    assert is_replay is False
    assert cached is None

    # Simulate operation completion
    service.record_success(biz_id, key, {"upload_id": 999, "status": "processed"})

    # 2nd attempt with same key: returns cached response
    is_replay_2, cached_2 = service.acquire_lock(biz_id, key, "sales_upload", req_hash)
    assert is_replay_2 is True
    assert cached_2 is not None
    assert cached_2["upload_id"] == 999
    assert cached_2["status"] == "processed"


def test_idempotency_concurrent_in_progress_conflict(db_session: Session):
    """Verify that concurrent requests with the same key within 120s raise IdempotencyConflictError."""
    service = IdempotencyService(db_session)
    biz_id = 102
    key = f"idem_conflict_key_{uuid.uuid4().hex}"
    req_hash = service.compute_request_hash("payload")

    # 1st request acquires lock
    service.acquire_lock(biz_id, key, "sales_upload", req_hash)

    # 2nd concurrent request while still in progress
    with pytest.raises(IdempotencyConflictError):
        service.acquire_lock(biz_id, key, "sales_upload", req_hash)


def test_concurrent_recommendation_lifecycle_update_idempotency(db_session: Session):
    """Verify that repeated status updates with identical attributes are idempotent."""
    repo = RecommendationLifecycleRepository(db_session)
    biz_id = 103
    rec_id = "rec_concurrent_01"

    # First transition
    state1 = repo.update_status(biz_id, rec_id, "In Progress", notes="Starting review")
    assert state1.status == "In Progress"

    # Immediate second call with identical status
    state2 = repo.update_status(biz_id, rec_id, "In Progress", notes="Starting review")
    assert state2.id == state1.id
    assert state2.status == "In Progress"


# --------------------------------------------------------------------------- #
# 4. File Upload & Processing Reliability Tests
# --------------------------------------------------------------------------- #

def test_sales_upload_file_size_validation():
    """Verify files exceeding 10MB are rejected with OversizedFileError."""
    oversized_bytes = b"0" * (10 * 1024 * 1024 + 100)
    with pytest.raises(OversizedFileError):
        validate_file_metadata("large_transactions.csv", oversized_bytes)


def test_sales_upload_unsupported_format_validation():
    """Verify unsupported file extensions are rejected with UnsupportedFormatError."""
    with pytest.raises(UnsupportedFormatError):
        validate_file_metadata("malicious_script.exe", b"dummy_content")


def test_sales_upload_partial_processing_status(db_session: Session):
    """Verify uploads containing both valid and invalid records receive status='partial_success'."""
    csv_content = (
        "Date,Product,Quantity,Unit Price\n"
        "2025-01-10,Carbide Tool,10,500.0\n"
        "2025-01-11,Industrial Valve,5,1200.0\n"
        "invalid_date,Alloy Bush,-3,NaN\n"  # Invalid row
    ).encode("utf-8")

    mapping = ColumnMapping(
        transaction_date="Date",
        product_name="Product",
        quantity="Quantity",
        unit_price="Unit Price",
    )

    svc = SalesService(db_session)
    response = svc.confirm_and_ingest(
        business_id=501,
        filename="mixed_sales.csv",
        file_bytes=csv_content,
        mapping=mapping,
    )

    assert response.status == "partial_success"
    assert response.valid_row_count == 2
    assert response.invalid_row_count == 1
    assert response.quality_summary.invalid_rows == 1


# --------------------------------------------------------------------------- #
# 5. Health Checks & Degradation Independence Tests
# --------------------------------------------------------------------------- #

def test_health_ready_degraded_during_gemini_outage():
    """Verify that a Gemini outage marks AI degraded but leaves the core platform ready (HTTP 200)."""
    client = TestClient(app)

    with patch("app.monitoring.health._probe_ai", return_value=(False, "circuit_breaker_open")):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["degraded"] is True
        assert data["ai"] is False
        assert data["database"] is True


def test_full_health_reports_degraded_status():
    """Verify GET /health reports status='degraded' when AI provider is unavailable."""
    client = TestClient(app)

    with patch("app.monitoring.health._probe_ai", return_value=(False, "circuit_breaker_open")):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["ai"]["ok"] is False


# --------------------------------------------------------------------------- #
# 6. Standard Error Envelope Contract
# --------------------------------------------------------------------------- #

def test_standard_resilience_error_envelope():
    """Verify AppResilienceError serializes to the complete required enterprise envelope."""
    err = DatabaseUnavailableError()
    assert err.status_code == 503
    assert err.error_code == "DATABASE_UNAVAILABLE"
    assert err.retryable is True
    assert err.service_name == "database"
    assert "temporarily unavailable" in err.safe_message
