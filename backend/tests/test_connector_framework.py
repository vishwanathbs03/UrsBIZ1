"""Comprehensive test suite for Integration Readiness and Connector Framework (Phase 6.27).

Covers:
  - 1. Connector contract & registry lookup
  - 2. Configuration & credential validation
  - 3. Authenticated encryption & credential vault security
  - 4. Secret masking & redaction (zero plain-text secrets in responses/audits)
  - 5. Tenant isolation & cross-tenant attack defense
  - 6. RBAC permission matrix enforcement (Viewer/Analyst/Manager/Admin/Owner)
  - 7. Connection lifecycle state transitions
  - 8. End-to-end synchronization & data normalization
  - 9. Deduplication & idempotency protection
  - 10. Fault simulation (timeout, rate limiting, bad data, partial sync)
  - 11. Concurrent sync execution blocking (409 Conflict)
  - 12. Data provenance lineage registration
  - 13. Append-only immutability & audit retention (RESTRICT foreign key)
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.business import Business
from app.models.collaboration import BusinessMember, BusinessRole, MemberStatus
from app.models.data_provenance import BusinessDataProvenance
from app.models.integration import (
    ConnectionStatus,
    ErrorCategory,
    IntegrationAudit,
    IntegrationConnection,
    IntegrationSyncExecution,
    SyncExecutionStatus,
)
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.services.connectors.base import (
    ConnectorCapability,
    OperationalStatus,
    SyncDirection,
)
from app.services.connectors.registry import ConnectorRegistry
from app.services.connectors.vault import ConnectorCredentialVault
from app.services.integration_service import IntegrationService
from app.utils.database import Base, get_db
from app.utils.security import create_access_token


# ==============================================================================
# FIXTURES & TEST HELPERS
# ==============================================================================

@pytest.fixture
def db_session():
    """Isolated in-memory SQLite session with StaticPool and active foreign key enforcement."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionTesting()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session):
    """FastAPI TestClient with overridden database session dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def _create_user(db: Session, email: str, full_name: str = "Test User") -> User:
    u = User(
        email=email.strip().lower(),
        full_name=full_name,
        password_hash="hashed_pw_for_tests",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _create_business(db: Session, owner: User, name: str = "Kirana Store BLR") -> Business:
    b = Business(
        owner_id=owner.id,
        legal_name=name,
        trade_name=name,
        industry="Retail",
        established_year=2022,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    owner.active_business_id = b.id
    db.commit()
    return b


def _add_member(db: Session, business: Business, user: User, role: BusinessRole) -> BusinessMember:
    m = BusinessMember(
        business_id=business.id,
        user_id=user.id,
        role=role.value,
        status=MemberStatus.ACTIVE.value,
    )
    db.add(m)
    user.active_business_id = business.id
    db.commit()
    db.refresh(m)
    return m


def _auth_header(user: User) -> dict[str, str]:
    tok = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {tok}"}


# ==============================================================================
# 1. CONNECTOR CONTRACT & REGISTRY LOOKUP
# ==============================================================================

def test_connector_registry_and_catalogue():
    """Verify built-in connectors are registered and return structured capability metadata."""
    connectors = ConnectorRegistry.list()
    assert len(connectors) >= 4

    ids = [c.connector_id for c in connectors]
    assert "test_harness" in ids
    assert "tally_prime" in ids
    assert "zoho_books" in ids
    assert "csv_feed" in ids

    # Check test_harness contract
    th = ConnectorRegistry.get("test_harness")
    assert th.name == "UrsBiz Test Harness Simulator"
    assert th.operational_status == OperationalStatus.OPERATIONAL
    assert ConnectorCapability.FETCH_TRANSACTIONS in th.capabilities
    assert th.sync_direction == SyncDirection.INBOUND_ONLY
    assert len(th.get_config_fields()) >= 5

    # Check unsupported connector raises KeyError
    with pytest.raises(KeyError, match="Connector 'sap_hana' is not registered"):
        ConnectorRegistry.get("sap_hana")


# ==============================================================================
# 2. CREDENTIAL VAULT & ENCRYPTION SECURITY
# ==============================================================================

def test_credential_vault_encryption_masking_redaction():
    """Verify AES-256 authenticated encryption, tenant validation, masking, and redaction."""
    vault = ConnectorCredentialVault()
    biz_id = 42

    creds = {
        "api_key": "sec-prod-token-9876543210",
        "client_secret": "super_secret_password_xyz",
        "plain_note": "public_note",
    }

    # 1. Encrypt & Decrypt
    ciphertext = vault.encrypt_credentials(biz_id, creds)
    assert ciphertext != ""
    assert "sec-prod-token" not in ciphertext
    assert "super_secret" not in ciphertext

    decrypted = vault.decrypt_credentials(biz_id, ciphertext)
    assert decrypted == creds

    # 2. Cross-tenant decryption attempt must fail with PermissionError
    with pytest.raises(PermissionError, match="Tenant isolation breach detected"):
        vault.decrypt_credentials(999, ciphertext)

    # 3. Masking for UI display
    masked = vault.mask_credentials(creds)
    assert masked["api_key"] == "••••••••3210"
    assert masked["client_secret"] == "••••••••_xyz"
    assert masked["plain_note"] == "••••••••note"

    # 4. Redaction for logging / audit
    payload_to_log = {
        "user_id": 1,
        "connector_id": "test_harness",
        "nested": {
            "api_key": "sec-prod-token-9876543210",
            "safe_field": "public_info",
        },
    }
    redacted = vault.redact_secrets_from_dict(payload_to_log)
    assert redacted["nested"]["api_key"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == "public_info"

    # 5. Dedicated CONNECTOR_ENCRYPTION_KEY and decoupling from jwt_secret_key
    from app.config.settings import get_settings
    settings = get_settings()
    original_jwt_key = settings.jwt_secret_key

    # A custom master_key operates independently
    custom_vault = ConnectorCredentialVault(master_key="dedicated-isolated-vault-secret-key-2026")
    custom_cipher = custom_vault.encrypt_credentials(biz_id, creds)
    assert custom_vault.decrypt_credentials(biz_id, custom_cipher) == creds

    # Modifying jwt_secret_key does not alter vault encryption/decryption
    try:
        settings.jwt_secret_key = "completely-different-jwt-key"
        fresh_vault = ConnectorCredentialVault()
        fresh_cipher = fresh_vault.encrypt_credentials(biz_id, creds)
        assert fresh_vault.decrypt_credentials(biz_id, fresh_cipher) == creds
    finally:
        settings.jwt_secret_key = original_jwt_key


# ==============================================================================
# 3. CATALOGUE & CONNECTION CREATION API
# ==============================================================================

def test_catalogue_api_endpoint(client: TestClient, db_session: Session):
    """Verify GET /api/v1/integrations/catalogue returns all connectors with fields."""
    owner = _create_user(db_session, "cat_owner@test.com")
    biz = _create_business(db_session, owner)

    res = client.get("/api/v1/integrations/catalogue", headers=_auth_header(owner))
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 4

    harness = next(c for c in data if c["connector_id"] == "test_harness")
    assert harness["operational_status"] == "OPERATIONAL"
    assert any(f["key"] == "api_key" and f["is_secret"] is True for f in harness["config_fields"])


def test_connection_create_lifecycle_and_masking(client: TestClient, db_session: Session):
    """Verify creating a connection stores encrypted credentials and returns masked values."""
    owner = _create_user(db_session, "conn_owner@test.com")
    biz = _create_business(db_session, owner)

    payload = {
        "connector_id": "test_harness",
        "name": "Main Store Simulator",
        "configuration": {
            "store_identifier": "STORE-01",
            "batch_size": 10,
        },
        "credentials": {
            "api_key": "valid-secret-token-xyz123",
        },
    }

    res = client.post("/api/v1/integrations/connections", json=payload, headers=_auth_header(owner))
    assert res.status_code == 201
    conn = res.json()
    assert conn["name"] == "Main Store Simulator"
    assert conn["status"] == ConnectionStatus.CONFIGURED.value
    assert conn["has_credentials"] is True
    # Secret must be masked, not plain text
    assert conn["masked_credentials"]["api_key"] == "••••••••z123"
    assert "valid-secret-token" not in res.text

    # Verify duplicate name conflict within business
    dup_res = client.post("/api/v1/integrations/connections", json=payload, headers=_auth_header(owner))
    assert dup_res.status_code == 409
    assert "already exists" in dup_res.text


# ==============================================================================
# 4. RBAC PERMISSION MATRIX ENFORCEMENT
# ==============================================================================

def test_rbac_restrictions_on_integrations(client: TestClient, db_session: Session):
    """Verify that Viewers and Analysts cannot mutate connections or trigger syncs,
    while Managers can configure & sync, and only Owners/Admins can delete.
    """
    owner = _create_user(db_session, "rbac_owner@test.com")
    biz = _create_business(db_session, owner)

    manager = _create_user(db_session, "rbac_mgr@test.com")
    _add_member(db_session, biz, manager, BusinessRole.MANAGER)

    analyst = _create_user(db_session, "rbac_analyst@test.com")
    _add_member(db_session, biz, analyst, BusinessRole.ANALYST)

    viewer = _create_user(db_session, "rbac_viewer@test.com")
    _add_member(db_session, biz, viewer, BusinessRole.VIEWER)

    # 1. Viewer can view catalogue and connections
    v_cat = client.get("/api/v1/integrations/catalogue", headers=_auth_header(viewer))
    assert v_cat.status_code == 200
    v_list = client.get("/api/v1/integrations/connections", headers=_auth_header(viewer))
    assert v_list.status_code == 200

    # 2. Viewer blocked from creating connection (DATA_WRITE required)
    v_create = client.post(
        "/api/v1/integrations/connections",
        json={"connector_id": "test_harness", "name": "V Conn", "configuration": {"store_identifier": "V1"}, "credentials": {"api_key": "k"}},
        headers=_auth_header(viewer),
    )
    assert v_create.status_code == 403

    # 3. Analyst blocked from creating connection (DATA_WRITE required)
    a_create = client.post(
        "/api/v1/integrations/connections",
        json={"connector_id": "test_harness", "name": "A Conn", "configuration": {"store_identifier": "A1"}, "credentials": {"api_key": "k"}},
        headers=_auth_header(analyst),
    )
    assert a_create.status_code == 403

    # 4. Manager can create connection
    m_create = client.post(
        "/api/v1/integrations/connections",
        json={"connector_id": "test_harness", "name": "M Conn", "configuration": {"store_identifier": "M1"}, "credentials": {"api_key": "valid-key"}},
        headers=_auth_header(manager),
    )
    assert m_create.status_code == 201
    conn_id = m_create.json()["id"]

    # 5. Viewer and Analyst blocked from testing, connecting, and syncing
    assert client.post(f"/api/v1/integrations/connections/{conn_id}/test", headers=_auth_header(viewer)).status_code == 403
    assert client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(analyst)).status_code == 403
    assert client.post(f"/api/v1/integrations/connections/{conn_id}/sync", json={}, headers=_auth_header(viewer)).status_code == 403

    # 6. Manager can test and connect
    assert client.post(f"/api/v1/integrations/connections/{conn_id}/test", headers=_auth_header(manager)).status_code == 200
    assert client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(manager)).status_code == 200

    # 7. Manager blocked from deleting connection (DATA_DELETE required)
    assert client.delete(f"/api/v1/integrations/connections/{conn_id}", headers=_auth_header(manager)).status_code == 403

    # 8. Owner allowed to delete connection
    assert client.delete(f"/api/v1/integrations/connections/{conn_id}", headers=_auth_header(owner)).status_code == 204


# ==============================================================================
# 5. CROSS-TENANT ISOLATION
# ==============================================================================

def test_cross_tenant_isolation_on_connections(client: TestClient, db_session: Session):
    """Verify that Tenant A cannot access, mutate, or trigger sync on Tenant B's connection."""
    owner_a = _create_user(db_session, "tenant_a@test.com")
    biz_a = _create_business(db_session, owner_a, "Business Alpha")

    owner_b = _create_user(db_session, "tenant_b@test.com")
    biz_b = _create_business(db_session, owner_b, "Business Beta")

    # Create connection in Business Alpha
    create_res = client.post(
        "/api/v1/integrations/connections",
        json={"connector_id": "test_harness", "name": "Alpha Simulator", "configuration": {"store_identifier": "A"}, "credentials": {"api_key": "key-alpha"}},
        headers=_auth_header(owner_a),
    )
    assert create_res.status_code == 201
    conn_a_id = create_res.json()["id"]

    # Tenant B tries to get connection A -> 404
    assert client.get(f"/api/v1/integrations/connections/{conn_a_id}", headers=_auth_header(owner_b)).status_code == 404

    # Tenant B tries to update config on connection A -> 404
    assert client.patch(
        f"/api/v1/integrations/connections/{conn_a_id}/config",
        json={"configuration": {"store_identifier": "HACKED"}},
        headers=_auth_header(owner_b),
    ).status_code == 404

    # Tenant B tries to rotate credentials on connection A -> 404
    assert client.put(
        f"/api/v1/integrations/connections/{conn_a_id}/credentials",
        json={"credentials": {"api_key": "stolen_key"}},
        headers=_auth_header(owner_b),
    ).status_code == 404

    # Tenant B tries to connect, test, or sync connection A -> 404
    assert client.post(f"/api/v1/integrations/connections/{conn_a_id}/test", headers=_auth_header(owner_b)).status_code == 404
    assert client.post(f"/api/v1/integrations/connections/{conn_a_id}/connect", headers=_auth_header(owner_b)).status_code == 404
    assert client.post(f"/api/v1/integrations/connections/{conn_a_id}/sync", json={}, headers=_auth_header(owner_b)).status_code == 404
    assert client.delete(f"/api/v1/integrations/connections/{conn_a_id}", headers=_auth_header(owner_b)).status_code == 404


# ==============================================================================
# 6. CONNECTION LIFECYCLE & AUTHENTICATION STATES
# ==============================================================================

def test_connection_lifecycle_states(client: TestClient, db_session: Session):
    """Verify NOT_CONFIGURED -> CONFIGURED -> CONNECTING -> CONNECTED,
    and handling of invalid vs expired credentials.
    """
    owner = _create_user(db_session, "lifecycle_owner@test.com")
    biz = _create_business(db_session, owner)

    # 1. Create with invalid API key
    conn_res = client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Fault Simulator",
            "configuration": {"store_identifier": "F-01"},
            "credentials": {"api_key": "invalid_key"},
        },
        headers=_auth_header(owner),
    )
    conn_id = conn_res.json()["id"]

    # 2. Try to connect with invalid key -> transitions to ERROR
    connect_fail = client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(owner))
    assert connect_fail.status_code == 200
    assert connect_fail.json()["status"] == ConnectionStatus.ERROR.value
    assert connect_fail.json()["last_error_category"] == ErrorCategory.AUTHENTICATION_FAILURE.value

    # Cannot sync while in ERROR status -> 400
    sync_attempt = client.post(f"/api/v1/integrations/connections/{conn_id}/sync", json={}, headers=_auth_header(owner))
    assert sync_attempt.status_code == 400
    assert "must be in 'CONNECTED' status" in sync_attempt.text

    # 3. Rotate credentials with expired key -> transitions to REAUTH_REQUIRED on connect
    client.put(
        f"/api/v1/integrations/connections/{conn_id}/credentials",
        json={"credentials": {"api_key": "expired_key"}},
        headers=_auth_header(owner),
    )
    reauth_res = client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(owner))
    assert reauth_res.json()["status"] == ConnectionStatus.REAUTH_REQUIRED.value

    # 4. Rotate credentials with valid key -> transitions to CONNECTED on connect
    client.put(
        f"/api/v1/integrations/connections/{conn_id}/credentials",
        json={"credentials": {"api_key": "valid-test-key"}},
        headers=_auth_header(owner),
    )
    conn_success = client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(owner))
    assert conn_success.json()["status"] == ConnectionStatus.CONNECTED.value
    assert conn_success.json()["last_error_message"] is None

    # 5. Disconnect -> DISCONNECTED
    disc_res = client.post(f"/api/v1/integrations/connections/{conn_id}/disconnect", headers=_auth_header(owner))
    assert disc_res.json()["status"] == ConnectionStatus.DISCONNECTED.value


# ==============================================================================
# 7. SYNCHRONIZATION, NORMALIZATION & DEDUPLICATION
# ==============================================================================

def test_sync_execution_and_sales_deduplication(client: TestClient, db_session: Session):
    """Verify data is fetched, normalized to SalesTransaction, deduplicated on replay,
    and provenance is recorded.
    """
    owner = _create_user(db_session, "sync_owner@test.com")
    biz = _create_business(db_session, owner)

    # 1. Create and connect
    c_res = client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Harness Sync",
            "configuration": {"store_identifier": "BLR-01", "batch_size": 5},
            "credentials": {"api_key": "valid-test-key"},
        },
        headers=_auth_header(owner),
    )
    conn_id = c_res.json()["id"]
    client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(owner))

    # 2. Trigger first sync batch
    sync1 = client.post(
        f"/api/v1/integrations/connections/{conn_id}/sync",
        json={"trigger_type": "MANUAL", "batch_limit": 5},
        headers=_auth_header(owner),
    )
    assert sync1.status_code == 202
    data1 = sync1.json()
    assert data1["status"] == SyncExecutionStatus.SUCCEEDED.value
    assert data1["records_discovered"] == 5
    assert data1["records_imported"] == 5
    assert data1["duplicate_count"] == 0
    assert data1["sync_cursor_after"] == "5"

    # Verify SalesTransaction records landed in DB
    txns = db_session.query(SalesTransaction).filter_by(business_id=biz.id).all()
    assert len(txns) == 5
    assert any("Karnataka Spices" in t.product_name for t in txns)

    # Verify BusinessDataProvenance record was created
    prov = db_session.query(BusinessDataProvenance).filter_by(
        business_id=biz.id, metric_name="sales_transactions"
    ).first()
    assert prov is not None
    assert prov.source_module == "connector:test_harness"
    assert prov.data_quality_status == "VERIFIED"

    # 3. Trigger second sync batch (records 6-10)
    sync2 = client.post(
        f"/api/v1/integrations/connections/{conn_id}/sync",
        json={"trigger_type": "MANUAL", "batch_limit": 5},
        headers=_auth_header(owner),
    )
    data2 = sync2.json()
    assert data2["status"] == SyncExecutionStatus.SUCCEEDED.value
    assert data2["records_discovered"] == 5
    assert data2["records_imported"] == 5
    assert data2["sync_cursor_after"] == "10"

    txns_total = db_session.query(SalesTransaction).filter_by(business_id=biz.id).all()
    assert len(txns_total) == 10

    # 4. Deduplication test: Reset sync_cursor to 0 and re-sync
    # All 5 re-fetched transactions must be recognized as duplicates and NOT duplicated in DB
    conn_entity = db_session.query(IntegrationConnection).filter_by(id=conn_id).first()
    conn_entity.sync_cursor = "0"
    db_session.commit()

    sync_dup = client.post(
        f"/api/v1/integrations/connections/{conn_id}/sync",
        json={"trigger_type": "MANUAL", "batch_limit": 5},
        headers=_auth_header(owner),
    )
    dup_data = sync_dup.json()
    assert dup_data["status"] == SyncExecutionStatus.SUCCEEDED.value
    assert dup_data["records_discovered"] == 5
    assert dup_data["records_imported"] == 0
    assert dup_data["duplicate_count"] == 5

    # Total database transactions must STILL be 10 (zero duplicate inflation)
    txns_after = db_session.query(SalesTransaction).filter_by(business_id=biz.id).all()
    assert len(txns_after) == 10

    # 5. Legitimate upstream invoice amendment test:
    # Upstream system amends INV-TH-0001 (quantity increases from original to 10.0, total from original to 2500.0)
    # The sync engine must update the existing record in-place without creating a duplicate row in DB.
    first_tx = db_session.query(SalesTransaction).filter_by(business_id=biz.id, invoice_id="INV-TH-0001").first()
    assert first_tx is not None
    original_qty = first_tx.quantity
    original_total = first_tx.total_amount

    from unittest.mock import patch
    from app.services.connectors.base import FetchResult
    from app.services.connectors.implementations.test_harness import TestHarnessConnector

    amended_raw_record = {
        "raw_id": "th-raw-1-amended",
        "invoice_no": "INV-TH-0001",
        "tx_date": first_tx.transaction_date.isoformat(),
        "customer_id": first_tx.customer_id,
        "customer_name": first_tx.customer_name,
        "product_id": first_tx.product_id,
        "product": first_tx.product_name,
        "qty": 10.0,
        "unit_price": 250.0,
        "amount": 2500.0,
    }

    with patch.object(
        TestHarnessConnector,
        "fetch_records",
        return_value=FetchResult(
            records=[amended_raw_record],
            next_cursor="1",
            has_more=False,
            total_discovered=1,
        ),
    ):
        amend_res = client.post(
            f"/api/v1/integrations/connections/{conn_id}/sync",
            json={"trigger_type": "MANUAL", "batch_limit": 1},
            headers=_auth_header(owner),
        )
        assert amend_res.status_code == 202
        amend_data = amend_res.json()
        assert amend_data["status"] == SyncExecutionStatus.SUCCEEDED.value
        assert amend_data["duplicate_count"] == 0
        assert amend_data["summary"]["records_updated"] == 1

        # Total count in DB MUST remain 10 (no new row inserted)
        assert db_session.query(SalesTransaction).filter_by(business_id=biz.id).count() == 10

        # The existing transaction record must have updated values in-place
        db_session.refresh(first_tx)
        assert first_tx.quantity == 10.0
        assert first_tx.total_amount == 2500.0


# ==============================================================================
# 8. FAULT SIMULATION & PARTIAL FAILURE HANDLING
# ==============================================================================

def test_fault_simulation_and_partial_sync(client: TestClient, db_session: Session):
    """Verify handling of rate-limiting, timeout, and bad data formatting."""
    owner = _create_user(db_session, "fault_owner@test.com")
    biz = _create_business(db_session, owner)

    # --- 1. Rate Limit Simulation ---
    rl_conn = client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Rate Limited Simulator",
            "configuration": {"store_identifier": "RL-1", "simulate_rate_limit": "true"},
            "credentials": {"api_key": "valid-key"},
        },
        headers=_auth_header(owner),
    ).json()
    client.post(f"/api/v1/integrations/connections/{rl_conn['id']}/connect", headers=_auth_header(owner))

    rl_sync = client.post(f"/api/v1/integrations/connections/{rl_conn['id']}/sync", json={}, headers=_auth_header(owner))
    assert rl_sync.status_code == 202
    assert rl_sync.json()["status"] == SyncExecutionStatus.FAILED.value
    assert rl_sync.json()["error_category"] == ErrorCategory.RATE_LIMITED.value

    # --- 2. Timeout Simulation ---
    to_conn = client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Timeout Simulator",
            "configuration": {"store_identifier": "TO-1", "simulate_timeout": "true"},
            "credentials": {"api_key": "valid-key"},
        },
        headers=_auth_header(owner),
    ).json()
    client.post(f"/api/v1/integrations/connections/{to_conn['id']}/connect", headers=_auth_header(owner))

    to_sync = client.post(f"/api/v1/integrations/connections/{to_conn['id']}/sync", json={}, headers=_auth_header(owner))
    assert to_sync.status_code == 202
    assert to_sync.json()["status"] == SyncExecutionStatus.FAILED.value
    assert to_sync.json()["error_category"] == ErrorCategory.TIMEOUT.value

    # --- 3. Partial Failure (Bad Data Row) Simulation ---
    bad_conn = client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Bad Data Simulator",
            "configuration": {"store_identifier": "BD-1", "simulate_bad_data": "true", "batch_size": 5},
            "credentials": {"api_key": "valid-key"},
        },
        headers=_auth_header(owner),
    ).json()
    client.post(f"/api/v1/integrations/connections/{bad_conn['id']}/connect", headers=_auth_header(owner))

    bad_sync = client.post(f"/api/v1/integrations/connections/{bad_conn['id']}/sync", json={}, headers=_auth_header(owner))
    assert bad_sync.status_code == 202
    bad_data = bad_sync.json()
    assert bad_data["status"] == SyncExecutionStatus.PARTIAL.value
    assert bad_data["records_discovered"] == 5
    assert bad_data["validation_failure_count"] == 1
    assert bad_data["records_imported"] == 4


# ==============================================================================
# 9. CONCURRENT SYNC PROTECTION
# ==============================================================================

def test_concurrent_sync_blocking(client: TestClient, db_session: Session):
    """Verify that attempting to trigger a sync while another is RUNNING raises 409 Conflict."""
    owner = _create_user(db_session, "concur_owner@test.com")
    biz = _create_business(db_session, owner)

    c_res = client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Concurrent Check",
            "configuration": {"store_identifier": "CC-1"},
            "credentials": {"api_key": "valid-key"},
        },
        headers=_auth_header(owner),
    ).json()
    conn_id = c_res["id"]
    client.post(f"/api/v1/integrations/connections/{conn_id}/connect", headers=_auth_header(owner))

    # Manually inject a RUNNING sync execution
    running_exec = IntegrationSyncExecution(
        business_id=biz.id,
        connection_id=conn_id,
        connector_id="test_harness",
        execution_id="sync-active-mock-1234",
        status=SyncExecutionStatus.RUNNING.value,
    )
    db_session.add(running_exec)
    db_session.commit()

    # Attempt to trigger a second concurrent sync -> 409 Conflict
    conflict_res = client.post(
        f"/api/v1/integrations/connections/{conn_id}/sync",
        json={},
        headers=_auth_header(owner),
    )
    assert conflict_res.status_code == 409
    assert "already RUNNING" in conflict_res.text


# ==============================================================================
# 10. AUDIT TRAIL IMMUTABILITY & RETENTION
# ==============================================================================

def test_integration_audit_immutability_and_retention(client: TestClient, db_session: Session):
    """Verify that integration audits are append-only and cannot be updated or deleted."""
    owner = _create_user(db_session, "audit_owner@test.com")
    biz = _create_business(db_session, owner)

    # 1. Trigger an event that writes an audit
    client.post(
        "/api/v1/integrations/connections",
        json={
            "connector_id": "test_harness",
            "name": "Audit Tracked",
            "configuration": {"store_identifier": "AT-1"},
            "credentials": {"api_key": "valid-key"},
        },
        headers=_auth_header(owner),
    )

    # 2. Query audits via API
    audits_res = client.get("/api/v1/integrations/audits", headers=_auth_header(owner))
    assert audits_res.status_code == 200
    audits = audits_res.json()["items"]
    assert len(audits) >= 1
    assert audits[0]["event_type"] == "connection_created"

    audit_entity = db_session.query(IntegrationAudit).filter_by(business_id=biz.id).first()
    assert audit_entity is not None

    # 3. Direct ORM UPDATE must raise ValueError
    audit_entity.event_type = "tampered_event"
    with pytest.raises(ValueError, match="strictly append-only and immutable"):
        db_session.commit()

    db_session.rollback()

    # 4. Direct ORM DELETE must raise ValueError
    audit_entity = db_session.query(IntegrationAudit).filter_by(business_id=biz.id).first()
    db_session.delete(audit_entity)
    with pytest.raises(ValueError, match="strictly append-only and immutable"):
        db_session.commit()

    db_session.rollback()


# ==============================================================================
# 11. TALLY & ZOHO CONNECTOR SCHEMA MAPPINGS
# ==============================================================================

def test_tally_connector_validation_and_mapping():
    """Verify Tally Prime XML schema mapping and configuration validation."""
    tally = ConnectorRegistry.get("tally_prime")
    assert tally.auth_method == "BASIC_AUTH"
    assert tally.operational_status == OperationalStatus.READY_FOR_CREDENTIALS

    # Missing gateway url
    ok, err = tally.validate_configuration({"company_name": "Test Co"}, {})
    assert not ok
    assert "gateway_url" in err

    # Valid config
    ok, err = tally.validate_configuration(
        {"gateway_url": "http://localhost:9000", "company_name": "Mysore Silks Ltd"},
        {"gateway_auth_token": "token123"},
    )
    assert ok

    # Map raw Tally XML voucher dictionary
    raw_voucher = {
        "DATE": "20261105",
        "VOUCHERNUMBER": "TALLY-VCH-8821",
        "PARTYLEDGERNAME": "Bengaluru Retailers",
        "STOCKITEMNAME": "Mysore Sandalwood Soap 100g",
        "BILLEDQTY": 25.0,
        "RATE": 60.0,
        "AMOUNT": 1500.0,
    }
    mapped = tally.map_record(raw_voucher)
    assert mapped.invoice_id == "TALLY-VCH-8821"
    assert mapped.customer_name == "Bengaluru Retailers"
    assert mapped.product_name == "Mysore Sandalwood Soap 100g"
    assert mapped.quantity == 25.0
    assert mapped.unit_price == 60.0
    assert mapped.total_amount == 1500.0


def test_zoho_books_connector_validation_and_mapping():
    """Verify Zoho Books REST API v3 schema mapping and validation."""
    zoho = ConnectorRegistry.get("zoho_books")
    assert zoho.auth_method == "OAUTH2"
    assert zoho.operational_status == OperationalStatus.READY_FOR_CREDENTIALS

    # Non-numeric organization_id must fail validation
    ok, err = zoho.validate_configuration(
        {"organization_id": "non_numeric_id"},
        {"auth_token": "valid_token"},
    )
    assert not ok
    assert "expected numeric string" in err

    # Valid configuration
    ok, err = zoho.validate_configuration(
        {"organization_id": "60012345678", "data_center": "in (India - zoho.in)"},
        {"auth_token": "valid_zoho_oauth_token"},
    )
    assert ok

    # Map raw Zoho Books invoice
    raw_inv = {
        "invoice_id": "zb-inv-99001",
        "invoice_number": "INV-ZB-2026-004",
        "date": "2026-11-04",
        "customer_id": "cust-zb-55",
        "customer_name": "Hubli Wholesalers",
        "total": 3500.0,
        "line_items": [
            {
                "name": "Coorg Filter Coffee 500g",
                "quantity": 10.0,
                "rate": 350.0,
            }
        ],
    }
    mapped = zoho.map_record(raw_inv)
    assert mapped.invoice_id == "INV-ZB-2026-004"
    assert mapped.customer_name == "Hubli Wholesalers"
    assert mapped.product_name == "Coorg Filter Coffee 500g"
    assert mapped.quantity == 10.0
    assert mapped.unit_price == 350.0
    assert mapped.total_amount == 3500.0


def test_csv_feed_connector_validation_and_mapping():
    """Verify CSV Feed connector validation and record mapping."""
    feed = ConnectorRegistry.get("csv_feed")
    assert feed.auth_method == "BEARER_TOKEN"
    assert feed.operational_status == OperationalStatus.OPERATIONAL

    # Invalid scheme
    ok, err = feed.validate_configuration({"feed_url": "ftp://bad-url.com"}, {})
    assert not ok
    assert "scheme" in err

    # Valid scheme
    ok, err = feed.validate_configuration({"feed_url": "https://secure-feed.example.com/sales.csv"}, {})
    assert ok

    # Map record
    raw = {
        "date": "2026-11-02",
        "invoice_id": "POS-FEED-102",
        "customer_name": "Walk-in Customer",
        "product_name": "Udupi Ghee 1L",
        "quantity": 2.0,
        "unit_price": 650.0,
        "total_amount": 1300.0,
    }
    mapped = feed.map_record(raw)
    assert mapped.invoice_id == "POS-FEED-102"
    assert mapped.product_name == "Udupi Ghee 1L"
    assert mapped.total_amount == 1300.0


def test_audit_retention_blocks_business_deletion(client: TestClient, db_session: Session):
    """Verify that deleting a business is blocked by foreign key constraint when audits exist."""
    owner = _create_user(db_session, "restrict_owner@test.com")
    biz = _create_business(db_session, owner, "Protected Business")

    # Write an audit record with FK RESTRICT to businesses.id
    audit = IntegrationAudit(
        business_id=biz.id,
        event_type="business_protection_check",
        details={"audit": "permanent_lineage"},
    )
    db_session.add(audit)
    db_session.commit()

    # Attempt direct business deletion
    from sqlalchemy.exc import IntegrityError
    db_session.delete(biz)
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        db_session.commit()

    db_session.rollback()
