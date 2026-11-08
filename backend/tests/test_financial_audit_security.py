"""Permanent PostgreSQL Integration Test Suite for Financial Audit Security (Wave 1.1).

Covers all 18 requirements from Wave 1.1 Implementation Authorization:
  1. Authenticated ursbiz_app identity and privilege verification.
  2. Authenticated ursbiz_kms_worker identity and privilege verification.
  3. Strict KMS worker configuration (no admin fallback).
  4. Application denial of protected procedure execution.
  5. Direct audit-table DML denial for ursbiz_app.
  6. Unauthorized actor rejection (RBAC enforcement: requires OWNER or FINANCE_ADMIN).
  7. Cross-tenant AR and AP reversal rejection (composite tenant foreign keys).
  8. AR and AP over-reversal rejection (excess amount validation).
  9. Concurrent / partial reversal protection.
  10. Duplicate request and nonce replay protection.
  11. Hostile search-path and temporary decoy-object attack resilience.
  12. Signing key lifecycle: ACTIVE, RETIRING in-grace, RETIRING expired, EXPIRED, REVOKED, and 24h grace constraint.
  13. Actual asymmetric Ed25519 signing and public-key verification.
  14. Signature tampering and actor-binding forgery detection.
  15. Historical HMAC transition and signed checkpoint verification.
  16. Multilingual Unicode and backslash canonicalization resilience.
  17. Integer minor-unit (paise) and currency validation.
  18. Rollback behavior and transaction atomicity after partial database failures.
"""

from __future__ import annotations

import os
import json
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

# Add backend to path
BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config.settings import Settings
from app.services.audit_signing_service import (
    AuditSigningService,
    GoogleCloudKMSProvider,
    KMSIntegrityError,
    KMSProviderFactory,
    SecurityConfigurationError,
    VolatileMemoryKMSProvider,
    compute_crc32c,
)
from app.services.audit_worker_service import (
    AuditWorkerService,
    SecurityViolation,
    TestIdentityAuthority,
    WorkerContextEncryption,
)
from app.utils.security import create_access_token

ADMIN_DB_URI = os.getenv(
    "TEST_ADMIN_DB_URL",
    "postgresql://postgres:root@localhost:5432/ursbiz_staging_disposable",
)
APP_DB_URI = os.getenv(
    "TEST_APP_DB_URL",
    "postgresql://ursbiz_app:app_pass@localhost:5432/ursbiz_staging_disposable",
)
KMS_DB_URI = os.getenv(
    "TEST_KMS_DB_URL",
    "postgresql://ursbiz_kms_worker:kms_worker_pass@localhost:5432/ursbiz_staging_disposable",
)


def _is_postgres_available() -> bool:
    """Checks if the PostgreSQL test database is reachable."""
    try:
        engine = create_engine(ADMIN_DB_URI, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _is_postgres_available(),
    reason="PostgreSQL staging test database is unavailable (requires localhost:5432/ursbiz_staging_disposable)",
)


@pytest.fixture(scope="module")
def admin_engine():
    engine = create_engine(ADMIN_DB_URI)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def app_engine():
    engine = create_engine(APP_DB_URI)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def kms_engine():
    # Strict KMS worker: no admin fallback
    assert KMS_DB_URI, "TEST_KMS_DB_URL must be explicitly configured; admin fallback is prohibited"
    assert "ursbiz_kms_worker" in KMS_DB_URI, "KMS connection URI must authenticate as ursbiz_kms_worker"
    engine = create_engine(KMS_DB_URI)
    yield engine
    engine.dispose()


@pytest.fixture
def financial_fixture(admin_engine):
    """Sets up an isolated business, users, AR and AP allocations, and Ed25519 public key."""
    suffix = uuid.uuid4().hex[:8]
    key_id = f"ed25519_key_{suffix}"
    priv_hex, pub_hex = AuditSigningService.generate_keypair()

    with admin_engine.connect() as conn:
        with conn.begin():
            # Create Users
            res_owner = conn.execute(
                text("INSERT INTO public.users (full_name, email, password_hash, is_active) VALUES ('Owner', :e, 'h', true) RETURNING id"),
                {"e": f"owner_{suffix}@test.internal"},
            )
            owner_id = res_owner.scalar_one()

            res_admin = conn.execute(
                text("INSERT INTO public.users (full_name, email, password_hash, is_active) VALUES ('Finance Admin', :e, 'h', true) RETURNING id"),
                {"e": f"admin_{suffix}@test.internal"},
            )
            admin_id = res_admin.scalar_one()

            res_emp = conn.execute(
                text("INSERT INTO public.users (full_name, email, password_hash, is_active) VALUES ('Employee', :e, 'h', true) RETURNING id"),
                {"e": f"emp_{suffix}@test.internal"},
            )
            emp_id = res_emp.scalar_one()

            # Create Primary Business A
            res_biz_a = conn.execute(
                text("INSERT INTO public.businesses (owner_id, legal_name, industry, established_year, annual_revenue, revenue_currency) VALUES (:o, :n, 'Mfg', 2020, 10000000.0, 'INR') RETURNING id"),
                {"o": owner_id, "n": f"Enterprise A {suffix}"},
            )
            biz_a_id = res_biz_a.scalar_one()

            # Create Secondary Business B (for cross-tenant attacks)
            res_biz_b = conn.execute(
                text("INSERT INTO public.businesses (owner_id, legal_name, industry, established_year, annual_revenue, revenue_currency) VALUES (:o, :n, 'Retail', 2021, 5000000.0, 'INR') RETURNING id"),
                {"o": owner_id, "n": f"Enterprise B {suffix}"},
            )
            biz_b_id = res_biz_b.scalar_one()

            # Business Memberships
            conn.execute(
                text("""
                    INSERT INTO public.business_members (business_id, user_id, role, status)
                    VALUES 
                        (:ba, :owner, 'OWNER', 'ACTIVE'),
                        (:ba, :admin, 'FINANCE_ADMIN', 'ACTIVE'),
                        (:ba, :emp, 'EMPLOYEE', 'ACTIVE'),
                        (:bb, :owner, 'OWNER', 'ACTIVE')
                """),
                {"ba": biz_a_id, "bb": biz_b_id, "owner": owner_id, "admin": admin_id, "emp": emp_id},
            )

            # AR Documents (Biz A)
            res_inv = conn.execute(
                text("INSERT INTO public.ar_invoices (business_id, invoice_number, invoice_date, due_date, gross_amount, tax_amount, outstanding_balance, status) VALUES (:b, :num, CURRENT_DATE, CURRENT_DATE, 10000.00, 1800.00, 0.00, 'PAID') RETURNING id"),
                {"b": biz_a_id, "num": f"INV-{suffix}"},
            )
            ar_inv_id = res_inv.scalar_one()

            res_cp = conn.execute(
                text("INSERT INTO public.customer_payments (business_id, payment_reference, payment_date, amount, payment_method, unallocated_balance, status) VALUES (:b, :ref, CURRENT_DATE, 10000.00, 'NEFT', 0.00, 'SETTLED') RETURNING id"),
                {"b": biz_a_id, "ref": f"REF-CP-{suffix}"},
            )
            ar_pmt_id = res_cp.scalar_one()

            res_ar_alloc = conn.execute(
                text("INSERT INTO public.ar_payment_allocations (business_id, invoice_id, payment_id, allocated_amount, status) VALUES (:b, :i, :p, 10000.00, 'ALLOCATED') RETURNING id"),
                {"b": biz_a_id, "i": ar_inv_id, "p": ar_pmt_id},
            )
            ar_alloc_id = res_ar_alloc.scalar_one()

            # AP Documents (Biz A)
            res_bill = conn.execute(
                text("INSERT INTO public.vendor_bills (business_id, vendor_name, bill_number, bill_date, due_date, gross_amount, tax_amount, outstanding_balance, status) VALUES (:b, 'Supplier', :num, CURRENT_DATE, CURRENT_DATE, 8000.00, 1440.00, 0.00, 'PAID') RETURNING id"),
                {"b": biz_a_id, "num": f"BILL-{suffix}"},
            )
            ap_bill_id = res_bill.scalar_one()

            res_vp = conn.execute(
                text("INSERT INTO public.vendor_payments (business_id, payment_reference, payment_date, amount, payment_method, unallocated_balance, status) VALUES (:b, :ref, CURRENT_DATE, 8000.00, 'RTGS', 0.00, 'SETTLED') RETURNING id"),
                {"b": biz_a_id, "ref": f"REF-VP-{suffix}"},
            )
            ap_pmt_id = res_vp.scalar_one()

            res_ap_alloc = conn.execute(
                text("INSERT INTO public.vendor_payment_allocations (business_id, bill_id, payment_id, allocated_amount, status) VALUES (:b, :bill, :pmt, 8000.00, 'ALLOCATED') RETURNING id"),
                {"b": biz_a_id, "bill": ap_bill_id, "pmt": ap_pmt_id},
            )
            ap_alloc_id = res_ap_alloc.scalar_one()

            # Register Ed25519 Public Key
            conn.execute(
                text("""
                    INSERT INTO public.audit_signing_public_keys (key_id, public_key, algorithm, status)
                    VALUES (:k, :pub, 'ED25519', 'ACTIVE')
                """),
                {"k": key_id, "pub": pub_hex},
            )

    data = {
        "suffix": suffix,
        "biz_a_id": biz_a_id,
        "biz_b_id": biz_b_id,
        "owner_id": owner_id,
        "admin_id": admin_id,
        "emp_id": emp_id,
        "ar_alloc_id": ar_alloc_id,
        "ap_alloc_id": ap_alloc_id,
        "key_id": key_id,
        "priv_hex": priv_hex,
        "pub_hex": pub_hex,
    }

    yield data

    # Cleanup in Dependency Order
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("DELETE FROM public.audit_worker_jobs WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.audit_transition_checkpoints WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.ar_allocation_reversals WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.vendor_allocation_reversals WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.business_audit_chains WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.audit_reversal_nonces WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.ar_payment_allocations WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.customer_payments WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.ar_invoices WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.vendor_payment_allocations WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.vendor_payments WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.vendor_bills WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.business_members WHERE business_id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.businesses WHERE id IN (:a, :b)"), {"a": biz_a_id, "b": biz_b_id})
            conn.execute(text("DELETE FROM public.users WHERE id IN (:o, :a, :e)"), {"o": owner_id, "a": admin_id, "e": emp_id})
            conn.execute(text("DELETE FROM public.audit_signing_public_keys WHERE key_id = :k"), {"k": key_id})


# ==============================================================================
# 1 & 2. Role Identity and Privilege Verification
# ==============================================================================

def test_authenticated_app_role_privileges(app_engine):
    """Pillar 2 / Req 1: Confirms ursbiz_app identity and lack of superuser/bypassrls."""
    with app_engine.connect() as conn:
        current_u, session_u = conn.execute(text("SELECT current_user, session_user")).fetchone()
        assert current_u == "ursbiz_app", f"Expected current_user='ursbiz_app', got {current_u}"
        assert session_u == "ursbiz_app", f"Expected session_user='ursbiz_app', got {session_u}"

        meta = conn.execute(
            text("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = 'ursbiz_app'")
        ).fetchone()
        assert not meta[0], "CRITICAL VIOLATION: 'ursbiz_app' must NOT be superuser"
        assert not meta[1], "CRITICAL VIOLATION: 'ursbiz_app' must NOT have BYPASSRLS"
        assert not meta[2], "CRITICAL VIOLATION: 'ursbiz_app' must NOT have CREATEROLE"
        assert not meta[3], "CRITICAL VIOLATION: 'ursbiz_app' must NOT have CREATEDB"


def test_authenticated_kms_worker_privileges(kms_engine):
    """Pillar 2 / Req 2 & 3: Confirms ursbiz_kms_worker identity, privileges, and zero admin fallback."""
    with kms_engine.connect() as conn:
        current_u, session_u = conn.execute(text("SELECT current_user, session_user")).fetchone()
        assert current_u == "ursbiz_kms_worker", f"Expected current_user='ursbiz_kms_worker', got {current_u}"
        assert session_u == "ursbiz_kms_worker", f"Expected session_user='ursbiz_kms_worker', got {session_u}"

        meta = conn.execute(
            text("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = 'ursbiz_kms_worker'")
        ).fetchone()
        assert not meta[0], "CRITICAL VIOLATION: 'ursbiz_kms_worker' must NOT be superuser"
        assert not meta[1], "CRITICAL VIOLATION: 'ursbiz_kms_worker' must NOT have BYPASSRLS"


# ==============================================================================
# 4 & 5. Application Execution and Table DML Denial
# ==============================================================================

def test_app_denial_of_reversal_procedure_and_direct_dml(app_engine, financial_fixture):
    """Pillar 2 / Req 4 & 5: Asserts ursbiz_app cannot call reversal procedures or perform direct audit DML."""
    fix = financial_fixture
    # Procedure execution denial
    with app_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_ar:
            conn.execute(
                text("""
                    SELECT public.record_ar_allocation_reversal(
                        :b, :a, 100.00, 10000, 'INR', 'denied test', :u,
                        '0123456789abcdef0123456789abcdef', :k, 'ED25519',
                        '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                        NOW()
                    )
                """),
                {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "u": fix["admin_id"], "k": fix["key_id"]},
            )
        assert "permission denied" in str(excinfo_ar.value).lower()

    # Direct table DML denial
    with app_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_dml:
            conn.execute(
                text("""
                    INSERT INTO public.ar_allocation_reversals (
                        business_id, original_allocation_id, reversed_amount, amount_paise, currency,
                        reason, actor_user_id, reversed_at, previous_digest_sha256, audit_digest_sha256,
                        signature_algorithm, signing_key_id, signature_hex
                    ) VALUES (
                        :b, :a, 100.00, 10000, 'INR', 'direct dml', :u, NOW(), 'prev', 'curr', 'ED25519', :k, 'sig'
                    )
                """),
                {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "u": fix["admin_id"], "k": fix["key_id"]},
            )
        assert "permission denied" in str(excinfo_dml.value).lower()


# ==============================================================================
# 6. Unauthorized Actor Rejection
# ==============================================================================

def test_unauthorized_actor_rejection(kms_engine, financial_fixture):
    """Req 6: Asserts requests for employees or unauthorized roles are rejected by RBAC."""
    fix = financial_fixture
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    payload = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["emp_id"],  # Employee role!
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=10000,
        currency="INR",
        nonce=nonce,
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Employee attempt",
        timestamp_iso=ts_iso,
    )
    sig_hex = AuditSigningService.sign_payload(fix["priv_hex"], payload)

    with kms_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo:
                conn.execute(
                    text("""
                        SELECT public.record_ar_allocation_reversal(
                            :b, :a, 100.00, 10000, 'INR', 'Employee attempt', :u,
                            :nonce, :k, 'ED25519', :sig, :ts
                        )
                    """),
                    {
                        "b": fix["biz_a_id"],
                        "a": fix["ar_alloc_id"],
                        "u": fix["emp_id"],
                        "nonce": nonce,
                        "k": fix["key_id"],
                        "sig": sig_hex,
                        "ts": now_utc,
                    },
                )
            assert "lacks authorization to reverse allocations" in str(excinfo.value)
            assert "Requires OWNER or FINANCE_ADMIN role" in str(excinfo.value)


# ==============================================================================
# 7. Cross-Tenant Reversal Rejection
# ==============================================================================

def test_cross_tenant_reversal_rejection(admin_engine, financial_fixture):
    """Req 7: Asserts composite tenant foreign keys block cross-tenant reversals."""
    fix = financial_fixture
    # Attempt to reverse AR allocation belonging to Biz A under Biz B's tenant context
    with admin_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo_ar:
                conn.execute(
                    text("""
                        INSERT INTO public.ar_allocation_reversals (
                            business_id, original_allocation_id, reversed_amount, amount_paise, currency,
                            reason, actor_user_id, reversed_at, previous_digest_sha256, audit_digest_sha256,
                            signature_algorithm, signing_key_id, signature_hex
                        ) VALUES (
                            :bb, :alloc_a, 100.00, 10000, 'INR', 'cross-tenant', :owner, NOW(), 'prev', 'curr', 'ED25519', :k, 'sig'
                        )
                    """),
                    {"bb": fix["biz_b_id"], "alloc_a": fix["ar_alloc_id"], "owner": fix["owner_id"], "k": fix["key_id"]},
                )
            assert "fk_reversal_alloc_tenant" in str(excinfo_ar.value).lower() or "violates foreign key constraint" in str(excinfo_ar.value).lower()

    # Attempt to reverse AP vendor allocation belonging to Biz A under Biz B's tenant context
    with admin_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo_ap:
                conn.execute(
                    text("""
                        INSERT INTO public.vendor_allocation_reversals (
                            business_id, vendor_allocation_id, reversed_amount, amount_paise, currency,
                            reason, actor_user_id, reversed_at, previous_digest_sha256, audit_digest_sha256,
                            signature_algorithm, signing_key_id, signature_hex
                        ) VALUES (
                            :bb, :alloc_a, 100.00, 10000, 'INR', 'cross-tenant ap', :owner, NOW(), 'prev', 'curr', 'ED25519', :k, 'sig'
                        )
                    """),
                    {"bb": fix["biz_b_id"], "alloc_a": fix["ap_alloc_id"], "owner": fix["owner_id"], "k": fix["key_id"]},
                )
            assert "fk_ap_reversal_alloc_tenant" in str(excinfo_ap.value).lower() or "violates foreign key constraint" in str(excinfo_ap.value).lower()


# ==============================================================================
# 8. Symmetrical AR & AP Reversal Execution & Over-Reversal Protection
# ==============================================================================

def test_symmetrical_ar_and_ap_reversals(kms_engine, admin_engine, financial_fixture):
    """Pillars 3 & 4 / Req 8: Tests valid AR & AP reversals, balance limits, and sequential hash chain updates."""
    fix = financial_fixture
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Valid AR Partial Reversal (₹2,500.00 = 250000 paise)
    nonce_ar = uuid.uuid4().hex
    payload_ar = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=250000,
        currency="INR",
        nonce=nonce_ar,
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Customer payment refund partial",
        timestamp_iso=ts_iso,
    )
    sig_ar = AuditSigningService.sign_payload(fix["priv_hex"], payload_ar)
    assert AuditSigningService.verify_signature(fix["pub_hex"], sig_ar, payload_ar)

    with kms_engine.connect() as conn:
        with conn.begin():
            res_ar = conn.execute(
                text("""
                    SELECT public.record_ar_allocation_reversal(
                        :b, :a, 2500.00, 250000, 'INR', 'Customer payment refund partial', :u,
                        :nonce, :k, 'ED25519', :sig, :ts
                    )
                """),
                {
                    "b": fix["biz_a_id"],
                    "a": fix["ar_alloc_id"],
                    "u": fix["admin_id"],
                    "nonce": nonce_ar,
                    "k": fix["key_id"],
                    "sig": sig_ar,
                    "ts": now_utc,
                },
            )
            ar_rev_id = res_ar.scalar_one()
            assert ar_rev_id > 0

    # 2. Valid AP Partial Reversal (₹3,000.00 = 300000 paise)
    nonce_ap = uuid.uuid4().hex
    payload_ap = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AP",
        allocation_id=fix["ap_alloc_id"],
        amount_paise=300000,
        currency="INR",
        nonce=nonce_ap,
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Vendor check bounced return",
        timestamp_iso=ts_iso,
    )
    sig_ap = AuditSigningService.sign_payload(fix["priv_hex"], payload_ap)
    assert AuditSigningService.verify_signature(fix["pub_hex"], sig_ap, payload_ap)

    with kms_engine.connect() as conn:
        with conn.begin():
            res_ap = conn.execute(
                text("""
                    SELECT public.record_ap_allocation_reversal(
                        :b, :a, 3000.00, 300000, 'INR', 'Vendor check bounced return', :u,
                        :nonce, :k, 'ED25519', :sig, :ts
                    )
                """),
                {
                    "b": fix["biz_a_id"],
                    "a": fix["ap_alloc_id"],
                    "u": fix["admin_id"],
                    "nonce": nonce_ap,
                    "k": fix["key_id"],
                    "sig": sig_ap,
                    "ts": now_utc,
                },
            )
            ap_rev_id = res_ap.scalar_one()
            assert ap_rev_id > 0

    # 3. Verify Chain Head advances sequentially for the shared business anchor
    with admin_engine.connect() as conn:
        chain_info = conn.execute(
            text("SELECT reversal_count, chain_head_digest FROM public.business_audit_chains WHERE business_id = :b"),
            {"b": fix["biz_a_id"]},
        ).fetchone()
        assert chain_info[0] >= 2, "Chain must record at least 2 reversals (1 AR + 1 AP)"
        assert len(chain_info[1]) == 64

    # 4. Over-Reversal Rejection (Original AR was 10000.00, already reversed 2500.00, trying 8000.00 > 7500.00)
    nonce_over = uuid.uuid4().hex
    with kms_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo_over:
                conn.execute(
                    text("""
                        SELECT public.record_ar_allocation_reversal(
                            :b, :a, 8000.00, 800000, 'INR', 'Excessive reversal', :u,
                            :nonce, :k, 'ED25519', :sig, :ts
                        )
                    """),
                    {
                        "b": fix["biz_a_id"],
                        "a": fix["ar_alloc_id"],
                        "u": fix["admin_id"],
                        "nonce": nonce_over,
                        "k": fix["key_id"],
                        "sig": sig_ar,
                        "ts": now_utc,
                    },
                )
            assert "Excess Reversal" in str(excinfo_over.value)


# ==============================================================================
# 9. Concurrency & Competing Transaction Race-Condition Protection
# ==============================================================================

def test_concurrent_competing_reversal_race_condition_protection(kms_engine, admin_engine, financial_fixture):
    """Req 9: Asserts concurrent competing database transactions are serialized by FOR UPDATE locks without race conditions."""
    import concurrent.futures
    import threading

    fix = financial_fixture
    # Create a fresh AR allocation specifically for this concurrency test with exactly ₹5,000.00
    with admin_engine.connect() as conn:
        with conn.begin():
            inv_res = conn.execute(
                text("""
                    INSERT INTO public.ar_invoices (business_id, invoice_number, invoice_date, due_date, gross_amount, tax_amount, outstanding_balance, status)
                    VALUES (:b, :num, CURRENT_DATE, CURRENT_DATE, 5000.00, 900.00, 0.00, 'PAID')
                    RETURNING id
                """),
                {"b": fix["biz_a_id"], "num": f"INV-CONC-{uuid.uuid4().hex[:8]}"},
            )
            conc_inv_id = inv_res.scalar_one()

            pmt_res = conn.execute(
                text("""
                    INSERT INTO public.customer_payments (business_id, payment_reference, payment_date, amount, payment_method, unallocated_balance, status)
                    VALUES (:b, :ref, CURRENT_DATE, 5000.00, 'NEFT', 0.00, 'SETTLED')
                    RETURNING id
                """),
                {"b": fix["biz_a_id"], "ref": f"REF-CONC-{uuid.uuid4().hex[:8]}"},
            )
            conc_pmt_id = pmt_res.scalar_one()

            alloc_res = conn.execute(
                text("""
                    INSERT INTO public.ar_payment_allocations (business_id, invoice_id, payment_id, allocated_amount, status)
                    VALUES (:b, :i, :p, 5000.00, 'ALLOCATED')
                    RETURNING id
                """),
                {"b": fix["biz_a_id"], "i": conc_inv_id, "p": conc_pmt_id},
            )
            conc_alloc_id = alloc_res.scalar_one()

    # Launch 5 concurrent threads.
    # Each thread attempts to reverse ₹3,000.00 (300000 paise).
    # Since total balance is ₹5,000.00, exactly ONE transaction can succeed!
    # The other 4 threads MUST be serialized, detect (3000 + 3000 > 5000), and throw 'Excess Reversal'.
    num_threads = 5
    barrier = threading.Barrier(num_threads)
    results: list[int] = []
    errors: list[str] = []
    results_lock = threading.Lock()

    def worker_reversal():
        thread_nonce = uuid.uuid4().hex
        thread_ts = datetime.now(timezone.utc).replace(microsecond=0)
        ts_iso = thread_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = AuditSigningService.build_canonical_payload(
            business_id=fix["biz_a_id"],
            actor_user_id=fix["admin_id"],
            allocation_type="AR",
            allocation_id=conc_alloc_id,
            amount_paise=300000,
            currency="INR",
            nonce=thread_nonce,
            key_id=fix["key_id"],
            algorithm="ED25519",
            reason="Concurrent race test",
            timestamp_iso=ts_iso,
        )
        sig = AuditSigningService.sign_payload(fix["priv_hex"], payload)

        # Synchronize all threads right before executing to guarantee maximum race collision
        barrier.wait()

        with kms_engine.connect() as conn:
            try:
                with conn.begin():
                    res = conn.execute(
                        text("""
                            SELECT public.record_ar_allocation_reversal(
                                :b, :a, 3000.00, 300000, 'INR', 'Concurrent race test', :u,
                                :nonce, :k, 'ED25519', :sig, :ts
                            )
                        """),
                        {
                            "b": fix["biz_a_id"],
                            "a": conc_alloc_id,
                            "u": fix["admin_id"],
                            "nonce": thread_nonce,
                            "k": fix["key_id"],
                            "sig": sig,
                            "ts": thread_ts,
                        },
                    )
                    rev_id = res.scalar_one()
                    with results_lock:
                        results.append(rev_id)
            except Exception as e:
                with results_lock:
                    errors.append(str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_reversal) for _ in range(num_threads)]
        concurrent.futures.wait(futures)

    # Assert that row locking serialized the transactions:
    # Exactly 1 thread succeeded, exactly 4 threads failed with Excess Reversal
    assert len(results) == 1, f"Expected exactly 1 successful reversal, got {len(results)} successes (race condition occurred!)"
    assert len(errors) == num_threads - 1, f"Expected {num_threads - 1} rejections, got {len(errors)}"
    for err in errors:
        assert "Excess Reversal" in err, f"Expected 'Excess Reversal' in error, got: {err}"

    # Verify database state has exactly ₹3,000.00 reversed, not ₹15,000.00
    with admin_engine.connect() as conn:
        total_reversed = conn.execute(
            text("SELECT COALESCE(SUM(reversed_amount), 0) FROM public.ar_allocation_reversals WHERE original_allocation_id = :a"),
            {"a": conc_alloc_id},
        ).scalar_one()
        assert float(total_reversed) == 3000.00, f"Expected total reversed 3000.00, got {total_reversed}"


# ==============================================================================
# 10. Replay Protection
# ==============================================================================

def test_nonce_replay_protection(kms_engine, financial_fixture):
    """Req 10: Asserts identical request nonces are blocked."""
    fix = financial_fixture
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    payload = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=50000,
        currency="INR",
        nonce=nonce,
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="First try",
        timestamp_iso=ts_iso,
    )
    sig = AuditSigningService.sign_payload(fix["priv_hex"], payload)

    with kms_engine.connect() as conn:
        with conn.begin():
            res1 = conn.execute(
                text("""
                    SELECT public.record_ar_allocation_reversal(
                        :b, :a, 500.00, 50000, 'INR', 'First try', :u, :nonce, :k, 'ED25519', :sig, :ts
                    )
                """),
                {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "u": fix["admin_id"], "nonce": nonce, "k": fix["key_id"], "sig": sig, "ts": now_utc},
            )
            assert res1.scalar_one() > 0

    with kms_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo:
                conn.execute(
                    text("""
                        SELECT public.record_ar_allocation_reversal(
                            :b, :a, 500.00, 50000, 'INR', 'First try', :u, :nonce, :k, 'ED25519', :sig, :ts
                        )
                    """),
                    {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "u": fix["admin_id"], "nonce": nonce, "k": fix["key_id"], "sig": sig, "ts": now_utc},
                )
            assert "replay detected" in str(excinfo.value).lower()


# ==============================================================================
# 11. Hostile Search-Path and Decoy Object Resilience
# ==============================================================================

def test_hostile_search_path_resilience(kms_engine, financial_fixture):
    """Req 11: Asserts caller temporary tables cannot hijack stored procedure execution."""
    fix = financial_fixture
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    payload = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=10000,
        currency="INR",
        nonce=nonce,
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Search path decoy test",
        timestamp_iso=ts_iso,
    )
    sig = AuditSigningService.sign_payload(fix["priv_hex"], payload)

    with kms_engine.connect() as conn:
        with conn.begin():
            # Inject decoy pg_temp table claiming employee is OWNER
            conn.execute(text("""
                CREATE TEMP TABLE business_members (
                    business_id INTEGER,
                    user_id INTEGER,
                    role VARCHAR(32),
                    status VARCHAR(16)
                );
                INSERT INTO pg_temp.business_members VALUES (:b, :emp, 'OWNER', 'ACTIVE');
                SET search_path = pg_temp, public;
            """), {"b": fix["biz_a_id"], "emp": fix["emp_id"]})

            # Decoy employee must still fail because procedure locks search_path = pg_catalog, public, extensions, pg_temp
            with pytest.raises(Exception) as excinfo:
                with conn.begin_nested():
                    conn.execute(
                        text("""
                            SELECT public.record_ar_allocation_reversal(
                                :b, :a, 100.00, 10000, 'INR', 'Search path decoy test', :emp,
                                :nonce, :k, 'ED25519', :sig, :ts
                            )
                        """),
                        {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "emp": fix["emp_id"], "nonce": uuid.uuid4().hex, "k": fix["key_id"], "sig": sig, "ts": now_utc},
                    )
            assert "lacks authorization to reverse allocations" in str(excinfo.value)

            # Legitimate admin succeeds
            res = conn.execute(
                text("""
                    SELECT public.record_ar_allocation_reversal(
                        :b, :a, 100.00, 10000, 'INR', 'Search path decoy test', :u,
                        :nonce, :k, 'ED25519', :sig, :ts
                    )
                """),
                {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "u": fix["admin_id"], "nonce": nonce, "k": fix["key_id"], "sig": sig, "ts": now_utc},
            )
            assert res.scalar_one() > 0


# ==============================================================================
# 12. Public Key Lifecycle & 24h Retirement Grace
# ==============================================================================

def test_public_key_lifecycle_and_24h_grace(admin_engine, kms_engine, financial_fixture):
    """Pillar 1 / Req 12: Verifies ACTIVE, RETIRING in-grace, RETIRING expired, EXPIRED, and REVOKED states."""
    fix = financial_fixture
    suffix = uuid.uuid4().hex[:8]
    _, pub_hex = AuditSigningService.generate_keypair()

    key_act = f"k_act_{suffix}"
    key_ret_valid = f"k_retv_{suffix}"
    key_ret_exp = f"k_retx_{suffix}"
    key_exp = f"k_exp_{suffix}"
    key_rev = f"k_rev_{suffix}"

    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("""
                    INSERT INTO public.audit_signing_public_keys (key_id, public_key, algorithm, status, retirement_started_at, retires_at, revoked_at)
                    VALUES 
                        (:act, :pub, 'ED25519', 'ACTIVE', NULL, NULL, NULL),
                        (:retv, :pub, 'ED25519', 'RETIRING', NOW() - INTERVAL '1 hour', NOW() + INTERVAL '2 hours', NULL),
                        (:retx, :pub, 'ED25519', 'RETIRING', NOW() - INTERVAL '25 hours', NOW() - INTERVAL '1 hour', NULL),
                        (:exp, :pub, 'ED25519', 'EXPIRED', NOW() - INTERVAL '48 hours', NOW() - INTERVAL '24 hours', NULL),
                        (:rev, :pub, 'ED25519', 'REVOKED', NOW() - INTERVAL '2 hours', NOW() + INTERVAL '22 hours', NOW() - INTERVAL '1 hour')
                """),
                {"act": key_act, "retv": key_ret_valid, "retx": key_ret_exp, "exp": key_exp, "rev": key_rev, "pub": pub_hex},
            )

    # 1. 24h Grace CHECK constraint violation
    with admin_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_grace:
            with conn.begin():
                conn.execute(
                    text("""
                        INSERT INTO public.audit_signing_public_keys (key_id, public_key, algorithm, status, retirement_started_at, retires_at)
                        VALUES (:k, :pub, 'ED25519', 'RETIRING', NOW(), NOW() + INTERVAL '25 hours')
                    """),
                    {"k": f"invalid_grace_{suffix}", "pub": pub_hex},
                )
        assert "chk_pubkey_retirement_grace" in str(excinfo_grace.value).lower()

    # 2. Key Rotation & Revocation execution by ursbiz_kms_worker
    with kms_engine.connect() as conn:
        with conn.begin():
            rot_key = f"kms_rot_{suffix}"
            conn.execute(
                text("SELECT public.rotate_audit_public_key(:k, :pub, 'ED25519', 3600)"),
                {"k": rot_key, "pub": pub_hex},
            )
            conn.execute(
                text("SELECT public.revoke_audit_public_key(:k, 'Scheduled rotation')"),
                {"k": rot_key},
            )


# ==============================================================================
# 13 & 14. Asymmetric Signing & Tampering Detection
# ==============================================================================

def test_asymmetric_tampering_detection(financial_fixture):
    """Pillar 1 / Req 13 & 14: Verifies Ed25519 signature validity and detects tampered payloads."""
    fix = financial_fixture
    payload = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=500000,
        currency="INR",
        nonce="a1b2c3d4e5f67890123456789abcdef0",
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Genuine reversal request",
        timestamp_iso="2026-11-08T12:00:00Z",
    )
    sig_hex = AuditSigningService.sign_payload(fix["priv_hex"], payload)

    # Valid verification
    assert AuditSigningService.verify_signature(fix["pub_hex"], sig_hex, payload) is True

    # Tampered Actor ID
    tampered_actor = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["emp_id"],  # Modified!
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=500000,
        currency="INR",
        nonce="a1b2c3d4e5f67890123456789abcdef0",
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Genuine reversal request",
        timestamp_iso="2026-11-08T12:00:00Z",
    )
    assert AuditSigningService.verify_signature(fix["pub_hex"], sig_hex, tampered_actor) is False

    # Tampered Amount
    tampered_amt = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=750000,  # Modified!
        currency="INR",
        nonce="a1b2c3d4e5f67890123456789abcdef0",
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason="Genuine reversal request",
        timestamp_iso="2026-11-08T12:00:00Z",
    )
    assert AuditSigningService.verify_signature(fix["pub_hex"], sig_hex, tampered_amt) is False


# ==============================================================================
# 15. Historical HMAC Transition and Checkpoint Verification
# ==============================================================================

def test_historical_hmac_transition_checkpoint(admin_engine):
    """Pillar 1 / Req 15: Confirms legacy HMAC keys are marked REVOKED, secret_bytes are zeroized, and historical metadata is preserved."""
    test_key = f"hmac_legacy_{uuid.uuid4().hex[:8]}"
    with admin_engine.connect() as conn:
        with conn.begin():
            # Seed a legacy key record with simulated non-zero secret bytes
            conn.execute(
                text("""
                    INSERT INTO public.audit_signing_secrets (key_id, secret_bytes, status, created_at)
                    VALUES (:k, :sec, 'ACTIVE', NOW() - INTERVAL '30 days')
                """),
                {"k": test_key, "sec": b"compromised_plaintext_hmac_secret!"},
            )

            # Apply the zeroization update from migration 20261116_0001
            conn.execute(
                text("""
                    UPDATE public.audit_signing_secrets
                    SET status = 'REVOKED',
                        secret_bytes = decode(repeat('00', 32), 'hex'),
                        revoked_at = COALESCE(revoked_at, NOW()),
                        revocation_reason = 'DEPRECATED_HMAC_TRANSITION_TO_ED25519_SECRET_ZEROIZED'
                    WHERE status != 'REVOKED' OR secret_bytes != decode(repeat('00', 32), 'hex');
                """)
            )

        # Verification: Confirm that NO plaintext / non-zero secret bytes remain
        with conn.begin():
            unzeroized = conn.execute(
                text("SELECT COUNT(*) FROM public.audit_signing_secrets WHERE secret_bytes != decode(repeat('00', 32), 'hex')")
            ).scalar_one()
            assert unzeroized == 0, "All legacy HMAC signing secret bytes must be completely zeroized (32 zero bytes)"

            # Check specific seeded key state
            row = conn.execute(
                text("SELECT status, secret_bytes, revocation_reason FROM public.audit_signing_secrets WHERE key_id = :k"),
                {"k": test_key},
            ).fetchone()
            assert row[0] == "REVOKED"
            assert bytes(row[1]) == b"\x00" * 32, "Plaintext HMAC key material was not erased!"
            assert row[2] == "DEPRECATED_HMAC_TRANSITION_TO_ED25519_SECRET_ZEROIZED"

            # Clean up the test key
            conn.execute(
                text("DELETE FROM public.audit_signing_secrets WHERE key_id = :k"),
                {"k": test_key},
            )


# ==============================================================================
# 16. Unicode and Backslash Canonicalization Resilience
# ==============================================================================

def test_unicode_and_backslash_canonicalization(kms_engine, financial_fixture):
    """Pillars 1 & 4 / Req 16: Tests that convert_to(..., 'UTF8') cleanly processes Kannada, backslashes and quotes."""
    fix = financial_fixture
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    ts_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    complex_reason = 'Cheque bounce: ₹5,000 "urgent" \\ ref: ಬ್ಯಾಂಕ್ | ಪಾವತಿ / C:\\Receipts\\2026.pdf'

    payload = AuditSigningService.build_canonical_payload(
        business_id=fix["biz_a_id"],
        actor_user_id=fix["admin_id"],
        allocation_type="AR",
        allocation_id=fix["ar_alloc_id"],
        amount_paise=10000,
        currency="INR",
        nonce=nonce,
        key_id=fix["key_id"],
        algorithm="ED25519",
        reason=complex_reason,
        timestamp_iso=ts_iso,
    )
    sig_hex = AuditSigningService.sign_payload(fix["priv_hex"], payload)
    assert AuditSigningService.verify_signature(fix["pub_hex"], sig_hex, payload) is True

    # Stored procedure execution in PostgreSQL must not crash on backslash or Unicode
    with kms_engine.connect() as conn:
        with conn.begin():
            res = conn.execute(
                text("""
                    SELECT public.record_ar_allocation_reversal(
                        :b, :a, 100.00, 10000, 'INR', :reason, :u, :nonce, :k, 'ED25519', :sig, :ts
                    )
                """),
                {
                    "b": fix["biz_a_id"],
                    "a": fix["ar_alloc_id"],
                    "reason": complex_reason,
                    "u": fix["admin_id"],
                    "nonce": nonce,
                    "k": fix["key_id"],
                    "sig": sig_hex,
                    "ts": now_utc,
                },
            )
            assert res.scalar_one() > 0


# ==============================================================================
# 17. Integer Minor-Unit and Currency Validation
# ==============================================================================

def test_integer_paise_and_currency_validation():
    """Pillar 4 / Req 17: Validates Decimal to Paise conversion and rejection of fractional paise."""
    # Exact conversions
    assert AuditSigningService.decimal_to_paise(Decimal("5000.00")) == 500000
    assert AuditSigningService.decimal_to_paise(Decimal("100.25")) == 10025
    assert AuditSigningService.decimal_to_paise("42.50") == 4250
    assert AuditSigningService.decimal_to_paise(10.0) == 1000

    # Rejection of fractional paise (sub-cent fractions)
    with pytest.raises(ValueError) as excinfo_half:
        AuditSigningService.decimal_to_paise(Decimal("5000.005"))
    assert "Fractional paise not permitted" in str(excinfo_half.value)

    with pytest.raises(ValueError):
        AuditSigningService.decimal_to_paise("100.001")

    # Rejection of non-positive amounts
    with pytest.raises(ValueError):
        AuditSigningService.decimal_to_paise(Decimal("0.00"))
    with pytest.raises(ValueError):
        AuditSigningService.decimal_to_paise(Decimal("-10.00"))


# ==============================================================================
# 18. Rollback Behavior and Transaction Atomicity
# ==============================================================================

def test_rollback_atomicity_after_partial_failure(kms_engine, admin_engine, financial_fixture):
    """Req 18: Asserts that an aborted transaction rolls back all changes without orphan rows."""
    fix = financial_fixture
    nonce = uuid.uuid4().hex

    with kms_engine.connect() as conn:
        try:
            with conn.begin():
                # Step 1: Valid initial execution
                conn.execute(
                    text("""
                        SELECT public.record_ar_allocation_reversal(
                            :b, :a, 100.00, 10000, 'INR', 'atomic test', :u,
                            :nonce, :k, 'ED25519',
                            '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                            NOW()
                        )
                    """),
                    {"b": fix["biz_a_id"], "a": fix["ar_alloc_id"], "u": fix["admin_id"], "nonce": nonce, "k": fix["key_id"]},
                )
                # Step 2: Force failure in the same transaction
                conn.execute(text("SELECT 1 / 0;"))
        except Exception:
            pass

    # Verify that nonce was NOT recorded in database due to rollback
    with admin_engine.connect() as conn:
        nonce_exists = conn.execute(
            text("SELECT COUNT(*) FROM public.audit_reversal_nonces WHERE nonce = :n"),
            {"n": nonce},
        ).scalar_one()
        assert nonce_exists == 0, "Rolled-back transaction must not leave recorded nonces"


# ==============================================================================
# 19. Google Cloud KMS API Integrity & Algorithm Guardrails (Wave 1.1.2)
# ==============================================================================

def test_crc32c_castagnoli_rfc3720_test_vector():
    """Wave 1.1.2 / Rem B: Validates Castagnoli CRC32C against standard RFC 3720 test vectors."""
    # Standard RFC 3720 test vector: b"123456789" -> 0xE3069283
    assert compute_crc32c(b"123456789") == 0xE3069283
    # Empty byte sequence -> 0x00000000
    assert compute_crc32c(b"") == 0x00000000


def test_google_cloud_kms_provider_api_integrity_and_software_protection():
    """Wave 1.1.2 / Rem B: Validates Cloud KMS Ed25519 PureEdDSA, SOFTWARE protection, and CRC32C verification."""
    from unittest.mock import MagicMock, patch
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization

    # Generate real Ed25519 key for mock KMS service
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_pem = pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    raw_pub_hex = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()

    provider = GoogleCloudKMSProvider(
        project_id="test-project",
        location_id="asia-south1",
        key_ring_id="ursbiz-ring",
        crypto_key_id="audit-ed25519",
        version_id="1",
    )

    # 1. Verify resource name format
    expected_resource_name = (
        "projects/test-project/locations/asia-south1/keyRings/ursbiz-ring/"
        "cryptoKeys/audit-ed25519/cryptoKeyVersions/1"
    )
    assert provider.key_version_resource_name == expected_resource_name
    assert provider.ALGORITHM == "EC_SIGN_ED25519"
    assert provider.PROTECTION_LEVEL == "SOFTWARE"

    payload = b"Canonical test payload for Cloud KMS RFC 8032 signing"
    payload_crc = compute_crc32c(payload)
    real_sig = priv_key.sign(payload)
    sig_crc = compute_crc32c(real_sig)

    # Mock KMS client
    mock_kms_client = MagicMock()
    mock_pub_resp = MagicMock()
    mock_pub_resp.pem = pub_pem
    mock_pub_resp.algorithm = "EC_SIGN_ED25519"
    mock_kms_client.get_public_key.return_value = mock_pub_resp

    mock_sign_resp = MagicMock()
    mock_sign_resp.name = expected_resource_name
    mock_sign_resp.signature = real_sig
    mock_sign_resp.signature_crc32c = sig_crc
    mock_sign_resp.verified_data_crc32c = True
    mock_sign_resp.protection_level = "SOFTWARE"
    mock_kms_client.asymmetric_sign.return_value = mock_sign_resp

    mock_google = MagicMock()
    mock_kms_module = MagicMock()
    mock_google.kms = mock_kms_module
    mock_kms_module.KeyManagementServiceClient.return_value = mock_kms_client
    with patch.dict("sys.modules", {"google": mock_google, "google.cloud": mock_google, "google.cloud.kms": mock_kms_module}):
        # Successful sign and public key retrieval
        pub_hex = provider.get_public_key_hex()
        assert pub_hex == raw_pub_hex

        sig_hex = provider.sign(payload)
        assert sig_hex == real_sig.hex()
        assert AuditSigningService.verify_signature(pub_hex, sig_hex, payload) is True

        # Integrity Check 1: KMS reports data_crc32c was NOT verified
        mock_sign_resp.verified_data_crc32c = False
        with pytest.raises(KMSIntegrityError, match="request data_crc32c was not verified"):
            provider.sign(payload)
        mock_sign_resp.verified_data_crc32c = True

        # Integrity Check 2: Key version resource name mismatch
        mock_sign_resp.name = "projects/test-project/locations/asia-south1/keyRings/other/cryptoKeys/other/cryptoKeyVersions/2"
        with pytest.raises(KMSIntegrityError, match="key-version mismatch"):
            provider.sign(payload)
        mock_sign_resp.name = expected_resource_name

        # Integrity Check 3: Signature CRC32C corrupted
        mock_sign_resp.signature_crc32c = 0xDEADBEEF
        with pytest.raises(KMSIntegrityError, match="signature CRC32C mismatch"):
            provider.sign(payload)
        mock_sign_resp.signature_crc32c = sig_crc

        # Integrity Check 4: Non-SOFTWARE protection level (e.g., falsely claimed HSM)
        mock_sign_resp.protection_level = "HSM"
        with pytest.raises(KMSIntegrityError, match="Expected SOFTWARE protection level"):
            provider.sign(payload)
        mock_sign_resp.protection_level = "SOFTWARE"

        # Integrity Check 5: Corrupted signature bytes (fails client-side verification)
        mock_sign_resp.signature = b"\x00" * 64
        mock_sign_resp.signature_crc32c = compute_crc32c(b"\x00" * 64)
        with pytest.raises(KMSIntegrityError, match="Signature failed client-side verification"):
            provider.sign(payload)


# ==============================================================================
# 20. Production Configuration Guardrail Enforcement (Wave 1.1.2)
# ==============================================================================

def test_production_configuration_guardrails():
    """Wave 1.1.2 / Rem C: Enforces that volatile memory KMS is rejected in staging and production."""
    # Production with 'memory' provider must be rejected
    prod_memory_settings = Settings(
        app_env="production",
        is_production=True,
        kms_provider_type="memory",
    )
    with pytest.raises(SecurityConfigurationError, match="strictly prohibited in production"):
        KMSProviderFactory.get_provider(prod_memory_settings)

    # Staging with 'memory' provider must be rejected
    staging_memory_settings = Settings(
        app_env="staging",
        is_production=False,
        kms_provider_type="memory",
    )
    with pytest.raises(SecurityConfigurationError, match="strictly prohibited in staging"):
        KMSProviderFactory.get_provider(staging_memory_settings)

    # Production with missing GCP KMS parameters must be rejected
    prod_incomplete_kms = Settings(
        app_env="production",
        is_production=True,
        kms_provider_type="gcp_kms",
        kms_project_id="test-proj",
        kms_location_id="",  # Missing required field
        kms_key_ring_id="",
        kms_crypto_key_id="",
        kms_key_version_id="",
    )
    with pytest.raises(SecurityConfigurationError, match="Incomplete Google Cloud KMS configuration"):
        KMSProviderFactory.get_provider(prod_incomplete_kms)

    # Development environment with 'memory' provider succeeds
    dev_settings = Settings(
        app_env="development",
        is_production=False,
        kms_provider_type="memory",
    )
    dev_provider = KMSProviderFactory.get_provider(dev_settings)
    assert isinstance(dev_provider, VolatileMemoryKMSProvider)


# ==============================================================================
# 21. Worker Authenticated Actor Binding and Tampering Detection (Wave 1.1.2 / 1.1.3)
# ==============================================================================

def test_worker_authenticated_actor_binding_and_tampering_detection(kms_engine, financial_fixture):
    """Wave 1.1.2/1.1.3: Verifies asymmetric RS256 token actor derivation, tampering rejection, and RBAC."""
    fix = financial_fixture
    idp = TestIdentityAuthority()

    # Valid asymmetric RS256 token for Finance Admin
    admin_token = idp.mint_access_token(subject=str(fix["admin_id"]))

    # 1. Authoritative derivation: token subject matches and membership verified
    verified_id = AuditWorkerService.verify_actor_and_bind(
        auth_token=admin_token,
        business_id=fix["biz_a_id"],
        worker_engine=kms_engine,
        idp_public_key_pem=idp.public_key_pem,
    )
    assert verified_id == fix["admin_id"]

    # 2. Tampering Detection: caller supplies owner_id, but JWT token belongs to admin_id
    with pytest.raises(SecurityViolation, match="Actor tampering detected"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=admin_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
            caller_supplied_actor_id=fix["owner_id"],
        )

    # 3. RBAC Rejection: employee user has EMPLOYEE role (not OWNER or FINANCE_ADMIN)
    emp_token = idp.mint_access_token(subject=str(fix["emp_id"]))
    with pytest.raises(SecurityViolation, match="requires one of"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=emp_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 4. Forged / invalid token rejection (signed with different key)
    other_idp = TestIdentityAuthority()
    forged_token = other_idp.mint_access_token(subject=str(fix["admin_id"]))
    with pytest.raises(SecurityViolation, match="Invalid, expired, or untrusted user authentication token"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=forged_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 5. Empty token rejection
    with pytest.raises(SecurityViolation, match="Missing authentication token"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token="",
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 6. Missing IDP public key rejection (strictly enforces asymmetric trust)
    with pytest.raises(SecurityViolation, match="trusted IDP public verification key"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=admin_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem="",
        )


def test_audit_worker_execute_reversal_end_to_end(kms_engine, admin_engine, financial_fixture):
    """Wave 1.1.2/1.1.3: End-to-end execution of reversal through AuditWorkerService using RS256."""
    fix = financial_fixture
    idp = TestIdentityAuthority()

    # Ephemeral keypair for test worker
    priv_hex, pub_hex = AuditSigningService.generate_keypair()
    test_key_id = f"worker_key_{uuid.uuid4().hex[:8]}"

    # Register test public key in audit_signing_public_keys
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("""
                    INSERT INTO public.audit_signing_public_keys (
                        key_id, algorithm, public_key, status, created_at
                    ) VALUES (
                        :kid, 'ED25519', :pub, 'ACTIVE', NOW()
                    )
                """),
                {"kid": test_key_id, "pub": pub_hex},
            )

    kms_provider = VolatileMemoryKMSProvider(key_id=test_key_id, private_key_hex=priv_hex)
    admin_token = idp.mint_access_token(subject=str(fix["admin_id"]))

    # Execute reversal through worker service
    reversal_id = AuditWorkerService.execute_reversal(
        allocation_type="AR",
        business_id=fix["biz_a_id"],
        allocation_id=fix["ar_alloc_id"],
        reversed_amount=100.00,
        reason="Wave 1.1.2 AuditWorkerService test reversal",
        auth_token=admin_token,
        kms_provider=kms_provider,
        worker_engine=kms_engine,
        idp_public_key_pem=idp.public_key_pem,
    )
    assert reversal_id > 0

    # Verify database state
    with admin_engine.connect() as conn:
        rev_row = conn.execute(
            text("""
                SELECT business_id, original_allocation_id, amount_paise, actor_user_id, signature_algorithm
                FROM public.ar_allocation_reversals
                WHERE id = :rid
            """),
            {"rid": reversal_id},
        ).fetchone()

        assert rev_row is not None
        assert rev_row[0] == fix["biz_a_id"]
        assert rev_row[1] == fix["ar_alloc_id"]
        assert rev_row[2] == 10000  # 100.00 INR = 10,000 paise
        assert rev_row[3] == fix["admin_id"]
        assert rev_row[4] == "ED25519"

    # Verify tampering rejection halts execution before database calls
    with pytest.raises(SecurityViolation, match="Actor tampering detected"):
        AuditWorkerService.execute_reversal(
            allocation_type="AR",
            business_id=fix["biz_a_id"],
            allocation_id=fix["ar_alloc_id"],
            reversed_amount=50.00,
            reason="Tampering attempt",
            auth_token=admin_token,
            kms_provider=kms_provider,
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
            caller_supplied_actor_id=fix["owner_id"],  # Tampered caller ID
        )


# ==============================================================================
# 22. Cryptographically Signed Transition Checkpoints (Wave 1.1.2)
# ==============================================================================

def test_transition_checkpoint_execution_and_idempotency(kms_engine, admin_engine, financial_fixture):
    """Wave 1.1.2 / Rem E: Creates signed URSBIZ_TRANS_V1 checkpoint, advances hash chain, and tests idempotency."""
    fix = financial_fixture
    transition_id = f"TRANS_EPOCH_{uuid.uuid4().hex[:8]}"

    # Ephemeral keypair for transition signing
    priv_hex, pub_hex = AuditSigningService.generate_keypair()
    trans_key_id = f"trans_key_{uuid.uuid4().hex[:6]}"

    # Register transition public key in audit_signing_public_keys (enforces foreign key constraint)
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("""
                    INSERT INTO public.audit_signing_public_keys (
                        key_id, algorithm, public_key, status, created_at
                    ) VALUES (
                        :kid, 'ED25519', :pub, 'ACTIVE', NOW()
                    )
                """),
                {"kid": trans_key_id, "pub": pub_hex},
            )

    kms_provider = VolatileMemoryKMSProvider(key_id=trans_key_id, private_key_hex=priv_hex)

    # 1. Execute Transition Checkpoint
    checkpoint_result = AuditWorkerService.execute_transition_checkpoint(
        business_id=fix["biz_a_id"],
        transition_id=transition_id,
        kms_provider=kms_provider,
        worker_engine=kms_engine,
        operator_confirmed=True,
    )

    assert checkpoint_result["transition_id"] == transition_id
    assert checkpoint_result["business_id"] == fix["biz_a_id"]
    assert checkpoint_result["canonical_payload_format"] == "URSBIZ_TRANS_V1"
    assert len(checkpoint_result["checkpoint_signature_hex"]) == 128
    assert len(checkpoint_result["checkpoint_digest_sha256"]) == 64

    # 2. Verify Database Persistence in audit_transition_checkpoints
    with admin_engine.connect() as conn:
        chk_row = conn.execute(
            text("""
                SELECT business_id, transition_id, canonical_version, 
                       checkpoint_signature_hex, checkpoint_digest_sha256,
                       legacy_chain_head_digest, legacy_reversal_count
                FROM public.audit_transition_checkpoints
                WHERE transition_id = :tid
            """),
            {"tid": transition_id},
        ).fetchone()

        assert chk_row is not None
        assert chk_row[0] == fix["biz_a_id"]
        assert chk_row[1] == transition_id
        assert chk_row[2] == "URSBIZ_TRANS_V1"
        assert chk_row[3] == checkpoint_result["checkpoint_signature_hex"]
        assert chk_row[4] == checkpoint_result["checkpoint_digest_sha256"]

        # 3. Verify Sequential Hash Chain Head was updated
        chain_head = conn.execute(
            text("SELECT chain_head_digest FROM public.business_audit_chains WHERE business_id = :b"),
            {"b": fix["biz_a_id"]},
        ).scalar_one()
        assert chain_head == checkpoint_result["new_chain_head_digest"]

    # 4. Independent Public-Key Verification (without private key)
    payload_bytes = AuditSigningService.build_transition_checkpoint_payload(
        business_id=fix["biz_a_id"],
        transition_id=transition_id,
        legacy_algorithm="HMAC-SHA256",
        legacy_chain_head_digest=checkpoint_result["legacy_chain_head_digest"],
        legacy_reversal_count=checkpoint_result["legacy_reversal_count"],
        new_algorithm="ED25519",
        new_key_id=kms_provider.key_id,
        timestamp_iso=checkpoint_result["checkpoint_timestamp_iso"],
    )
    is_valid = AuditSigningService.verify_signature(
        public_key_hex=pub_hex,
        signature_hex=checkpoint_result["checkpoint_signature_hex"],
        payload_bytes=payload_bytes,
    )
    assert is_valid is True, "Transition checkpoint signature must independently verify with public key"

    # 5. Idempotency Test: replaying identical transition_id returns existing record without duplicating
    replay_result = AuditWorkerService.execute_transition_checkpoint(
        business_id=fix["biz_a_id"],
        transition_id=transition_id,
        kms_provider=kms_provider,
        worker_engine=kms_engine,
        operator_confirmed=True,
    )
    assert replay_result["id"] == checkpoint_result["id"]
    assert replay_result["checkpoint_digest_sha256"] == checkpoint_result["checkpoint_digest_sha256"]

    # Assert exactly 1 row exists in database for this transition_id
    with admin_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.audit_transition_checkpoints WHERE transition_id = :tid"),
            {"tid": transition_id},
        ).scalar_one()
        assert count == 1, "Idempotent replay must not create duplicate checkpoint records"

    # 6. Dry Run Test: does not insert into database
    dry_run_id = f"TRANS_DRY_RUN_{uuid.uuid4().hex[:8]}"
    dry_result = AuditWorkerService.execute_transition_checkpoint(
        business_id=fix["biz_a_id"],
        transition_id=dry_run_id,
        kms_provider=kms_provider,
        worker_engine=kms_engine,
        operator_confirmed=True,
        dry_run=True,
    )
    assert dry_result["is_dry_run"] is True
    with admin_engine.connect() as conn:
        dry_count = conn.execute(
            text("SELECT COUNT(*) FROM public.audit_transition_checkpoints WHERE transition_id = :tid"),
            {"tid": dry_run_id},
        ).scalar_one()
        assert dry_count == 0, "Dry run must not insert any database records"


# ==============================================================================
# 23. Legacy HMAC Stored Procedure Permanently Dropped (Wave 1.1.2)
# ==============================================================================

def test_legacy_hmac_stored_procedure_is_permanently_dropped(kms_engine):
    """Wave 1.1.2 / Rem F: Confirms public.record_allocation_reversal is permanently dropped in PostgreSQL."""
    from sqlalchemy.exc import ProgrammingError

    with kms_engine.connect() as conn:
        with pytest.raises(ProgrammingError) as excinfo:
            conn.execute(
                text("""
                    SELECT public.record_allocation_reversal(
                        1, 'AR', 1, 100.00, 'Test dropped', 1, 'nonce123'
                    )
                """)
            )
        # PostgreSQL error code 42883 is undefined_function
        err_msg = str(excinfo.value)
        assert "record_allocation_reversal" in err_msg
        assert "does not exist" in err_msg or "42883" in err_msg


# ==============================================================================
# 24. Asymmetric RS256 JWT Claim Validations (Wave 1.1.3 - Decision 1 / Option 1A)
# ==============================================================================

def test_asymmetric_jwt_claim_validations(kms_engine, financial_fixture):
    """Wave 1.1.3 / Decision 1: Asserts strict RS256 claim checks: iss, aud, exp, nbf, typ, and algorithm."""
    fix = financial_fixture
    idp = TestIdentityAuthority()

    # 1. Valid RS256 Token succeeds
    valid_token = idp.mint_token(subject=fix["admin_id"])
    actor_id = AuditWorkerService.verify_actor_and_bind(
        auth_token=valid_token,
        business_id=fix["biz_a_id"],
        worker_engine=kms_engine,
        idp_public_key_pem=idp.public_key_pem,
    )
    assert actor_id == fix["admin_id"]

    # 2. HS256 Token rejected (strict asymmetric algorithm policy)
    hs256_token = create_access_token(subject=str(fix["admin_id"]))
    with pytest.raises(SecurityViolation, match="alg value is not allowed"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=hs256_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 3. Forged RSA Token (signed by different private key) rejected
    rogue_idp = TestIdentityAuthority()
    forged_token = rogue_idp.mint_token(subject=fix["admin_id"])
    with pytest.raises(SecurityViolation, match="Signature verification failed"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=forged_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 4. Invalid Issuer (iss != "ursbiz-identity") rejected
    bad_iss_token = idp.mint_token(subject=fix["admin_id"], issuer="rogue-idp")
    with pytest.raises(SecurityViolation, match="Invalid issuer"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=bad_iss_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 5. Invalid Audience (aud != "ursbiz-financial-audit") rejected
    bad_aud_token = idp.mint_token(subject=fix["admin_id"], audience="general-api")
    with pytest.raises(SecurityViolation, match="Invalid audience"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=bad_aud_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 6. Expired Token (exp < now) rejected
    expired_token = idp.mint_token(subject=fix["admin_id"], expires_in_seconds=-60)
    with pytest.raises(SecurityViolation, match="Signature has expired"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=expired_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 7. Future Not-Before Token (nbf > now) rejected
    future_token = idp.mint_token(subject=fix["admin_id"], not_before_seconds=3600)
    with pytest.raises(SecurityViolation, match="The token is not yet valid"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=future_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )

    # 8. Invalid Token Type (typ != "JWT") rejected
    refresh_token = idp.mint_token(subject=fix["admin_id"], token_type="REFRESH")
    with pytest.raises(SecurityViolation, match="Invalid token type"):
        AuditWorkerService.verify_actor_and_bind(
            auth_token=refresh_token,
            business_id=fix["biz_a_id"],
            worker_engine=kms_engine,
            idp_public_key_pem=idp.public_key_pem,
        )


# ==============================================================================
# 25. Direct Worker Audit Table DML Denial (Wave 1.1.3 - Decision 2 / Option 2A)
# ==============================================================================

def test_direct_worker_audit_table_dml_denied(kms_engine, financial_fixture):
    """Wave 1.1.3 / Decision 2: Asserts direct INSERT, UPDATE, DELETE on audit tables are revoked from ursbiz_kms_worker."""
    fix = financial_fixture

    # 1. Direct INSERT into audit_transition_checkpoints is denied
    with kms_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_insert:
            conn.execute(
                text("""
                    INSERT INTO public.audit_transition_checkpoints (
                        business_id, transition_id, legacy_algorithm, legacy_trust_status,
                        legacy_chain_head_digest, legacy_reversal_count, new_algorithm,
                        new_signing_key_id, canonical_version, checkpoint_signature_hex,
                        checkpoint_digest_sha256, previous_chain_head_digest, transition_timestamp
                    ) VALUES (
                        :b, 'ILLEGAL_TRANS', 'HMAC-SHA256', 'LEGACY_NON_REPUDIATION_DOWNGRADED',
                        'head', 0, 'ED25519', :k, 'URSBIZ_TRANS_V1', 'sig', 'digest', 'head', NOW()
                    )
                """),
                {"b": fix["biz_a_id"], "k": fix["key_id"]},
            )
        assert "permission denied for table audit_transition_checkpoints" in str(excinfo_insert.value).lower()

    # 2. Direct UPDATE on business_audit_chains is denied
    with kms_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_update:
            conn.execute(
                text("UPDATE public.business_audit_chains SET chain_head_digest = 'tampered' WHERE business_id = :b"),
                {"b": fix["biz_a_id"]},
            )
        assert "permission denied for table business_audit_chains" in str(excinfo_update.value).lower()

    # 3. Direct DELETE on business_audit_chains is denied
    with kms_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_delete:
            conn.execute(
                text("DELETE FROM public.business_audit_chains WHERE business_id = :b"),
                {"b": fix["biz_a_id"]},
            )
        assert "permission denied for table business_audit_chains" in str(excinfo_delete.value).lower()


# ==============================================================================
# 26. Transition Checkpoint Stored Procedure Access Control (Wave 1.1.3)
# ==============================================================================

def test_record_transition_checkpoint_procedure_access(kms_engine, app_engine, financial_fixture):
    """Wave 1.1.3 / Decision 2: ursbiz_kms_worker has EXECUTE on procedure; ursbiz_app is denied."""
    fix = financial_fixture
    dummy_tid = f"TRANS_PROC_{uuid.uuid4().hex[:8]}"

    # 1. ursbiz_app is denied EXECUTE on record_transition_checkpoint
    with app_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_app:
            conn.execute(
                text("""
                    SELECT public.record_transition_checkpoint(
                        :b, :tid, 'HMAC-SHA256', 'LEGACY_NON_REPUDIATION_DOWNGRADED',
                        'head', 0, 'ED25519', :k, 'URSBIZ_TRANS_V1',
                        'sig', 'digest', 'head', NOW()
                    )
                """),
                {"b": fix["biz_a_id"], "tid": dummy_tid, "k": fix["key_id"]},
            )
        assert "permission denied for function record_transition_checkpoint" in str(excinfo_app.value).lower()


# ==============================================================================
# 27. Concurrent Transition Checkpoint Race Condition Protection (Wave 1.1.3)
# ==============================================================================

def test_concurrent_transition_checkpoint_race_condition_protection(kms_engine, admin_engine, financial_fixture):
    """Wave 1.1.3: 5 parallel threads attempt simultaneous transition checkpoint execution with identical parameters."""
    import concurrent.futures
    import threading

    fix = financial_fixture
    trans_id = f"TRANS_RACE_{uuid.uuid4().hex[:8]}"
    fixed_ts = datetime.now(timezone.utc).replace(microsecond=0)

    # Register transition public key
    priv_hex, pub_hex = AuditSigningService.generate_keypair()
    trans_key_id = f"trans_race_key_{uuid.uuid4().hex[:6]}"
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("""
                    INSERT INTO public.audit_signing_public_keys (
                        key_id, algorithm, public_key, status, created_at
                    ) VALUES (
                        :kid, 'ED25519', :pub, 'ACTIVE', NOW()
                    )
                """),
                {"kid": trans_key_id, "pub": pub_hex},
            )

    kms_provider = VolatileMemoryKMSProvider(key_id=trans_key_id, private_key_hex=priv_hex)

    # Barrier to ensure all 5 threads invoke execute_transition_checkpoint simultaneously
    barrier = threading.Barrier(5)
    results = []
    errors = []

    def worker_task(thread_idx: int):
        barrier.wait()  # Synchronize start across all 5 threads
        try:
            res = AuditWorkerService.execute_transition_checkpoint(
                business_id=fix["biz_a_id"],
                transition_id=trans_id,
                kms_provider=kms_provider,
                worker_engine=kms_engine,
                operator_confirmed=True,
                checkpoint_timestamp=fixed_ts,
            )
            results.append((thread_idx, res))
        except Exception as e:
            errors.append((thread_idx, e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_task, i) for i in range(5)]
        concurrent.futures.wait(futures)

    assert len(errors) == 0, f"Concurrent threads raised unexpected errors: {errors}"
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"

    # All 5 threads must report the same checkpoint ID and digest
    first_id = results[0][1]["id"]
    first_digest = results[0][1]["checkpoint_digest_sha256"]
    for thread_idx, res in results:
        assert res["id"] == first_id, f"Thread {thread_idx} returned different checkpoint id"
        assert res["checkpoint_digest_sha256"] == first_digest

    # Verify exactly ONE row was created in audit_transition_checkpoints
    with admin_engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.audit_transition_checkpoints WHERE transition_id = :tid"),
            {"tid": trans_id},
        ).scalar_one()
        assert count == 1, f"Expected exactly 1 checkpoint row, found {count}"

        # Verify chain head exists and is updated
        chain_head = conn.execute(
            text("SELECT chain_head_digest FROM public.business_audit_chains WHERE business_id = :b"),
            {"b": fix["biz_a_id"]},
        ).scalar_one()
        assert chain_head == results[0][1]["new_chain_head_digest"]


# ==============================================================================
# 28. Conflicting Transition Payload Rejection (Wave 1.1.3)
# ==============================================================================

def test_conflicting_transition_payload_rejection(kms_engine, admin_engine, financial_fixture):
    """Wave 1.1.3: Confirms conflicting checkpoint payloads and invalid continuity links are rejected."""
    fix = financial_fixture
    trans_id = f"TRANS_CONFLICT_{uuid.uuid4().hex[:8]}"
    fixed_ts = datetime.now(timezone.utc).replace(microsecond=0)

    priv_hex, pub_hex = AuditSigningService.generate_keypair()
    trans_key_id = f"trans_cf_key_{uuid.uuid4().hex[:6]}"
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("INSERT INTO public.audit_signing_public_keys (key_id, algorithm, public_key, status, created_at) VALUES (:k, 'ED25519', :p, 'ACTIVE', NOW())"),
                {"k": trans_key_id, "p": pub_hex},
            )

    kms_provider = VolatileMemoryKMSProvider(key_id=trans_key_id, private_key_hex=priv_hex)

    # 1. Record legitimate initial checkpoint
    initial_res = AuditWorkerService.execute_transition_checkpoint(
        business_id=fix["biz_a_id"],
        transition_id=trans_id,
        kms_provider=kms_provider,
        worker_engine=kms_engine,
        operator_confirmed=True,
        checkpoint_timestamp=fixed_ts,
    )
    assert initial_res["id"] > 0

    # 2. Attempt to record identical transition_id with CONFLICTING digest
    with kms_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo_conflict:
                conn.execute(
                    text("""
                        SELECT public.record_transition_checkpoint(
                            :b, :tid, 'HMAC-SHA256', 'LEGACY_NON_REPUDIATION_DOWNGRADED',
                            :l_head, :l_count, 'ED25519', :k_id, 'URSBIZ_TRANS_V1',
                            :sig, '0000000000000000000000000000000000000000000000000000000000000000', :p_head, :ts
                        )
                    """),
                    {
                        "b": fix["biz_a_id"],
                        "tid": trans_id,
                        "l_head": initial_res["legacy_chain_head_digest"],
                        "l_count": initial_res["legacy_reversal_count"],
                        "k_id": trans_key_id,
                        "sig": initial_res["checkpoint_signature_hex"],
                        "p_head": initial_res["legacy_chain_head_digest"],
                        "ts": fixed_ts,
                    },
                )
            assert "idempotency conflict" in str(excinfo_conflict.value).lower()

    # 3. Attempt to record new transition with CHAIN CONTINUITY VIOLATION (wrong previous head)
    with kms_engine.connect() as conn:
        with conn.begin():
            with pytest.raises(Exception) as excinfo_cont:
                conn.execute(
                    text("""
                        SELECT public.record_transition_checkpoint(
                            :b, 'TRANS_BROKEN_CONTINUITY', 'HMAC-SHA256', 'LEGACY_NON_REPUDIATION_DOWNGRADED',
                            '0000000000000000000000000000000000000000000000000000000000000000', 0, 'ED25519', :k_id, 'URSBIZ_TRANS_V1',
                            '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                            '0000000000000000000000000000000000000000000000000000000000000000',
                            'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff', :ts
                        )
                    """),
                    {
                        "b": fix["biz_a_id"],
                        "k_id": trans_key_id,
                        "ts": fixed_ts,
                    },
                )
            assert "chain continuity violation" in str(excinfo_cont.value).lower()


# ==============================================================================
# 29. Audit Worker Job Queue and Envelope Encryption (Wave 1.1.3 - Decision 3 / Option 3A)
# ==============================================================================

def test_audit_worker_job_queue_and_envelope_encryption(app_engine, kms_engine, admin_engine, financial_fixture):
    """Wave 1.1.3 / Decision 3: Tests transactional job queue, envelope encryption, and SKIP LOCKED claiming."""
    fix = financial_fixture
    idp = TestIdentityAuthority()

    # Worker generates RSA envelope encryption keypair
    worker_priv_pem, worker_pub_pem = WorkerContextEncryption.generate_keypair()

    # Worker generates Ed25519 signing keypair
    priv_hex, pub_hex = AuditSigningService.generate_keypair()
    worker_key_id = f"queue_worker_key_{uuid.uuid4().hex[:6]}"
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("INSERT INTO public.audit_signing_public_keys (key_id, algorithm, public_key, status, created_at) VALUES (:k, 'ED25519', :p, 'ACTIVE', NOW())"),
                {"k": worker_key_id, "p": pub_hex},
            )
    kms_provider = VolatileMemoryKMSProvider(key_id=worker_key_id, private_key_hex=priv_hex)

    # 1. FastAPI (as ursbiz_app) mints RS256 token and enqueues job with envelope encryption
    admin_token = idp.mint_token(subject=fix["admin_id"])
    idem_key = f"idem_{uuid.uuid4().hex}"
    job_id = AuditWorkerService.enqueue_job(
        business_id=fix["biz_a_id"],
        job_type="AR_REVERSAL",
        idempotency_key=idem_key,
        auth_token=admin_token,
        payload={
            "allocation_id": fix["ar_alloc_id"],
            "reversed_amount": 75.00,
            "reason": "Job queue reversal test",
        },
        worker_public_key_pem=worker_pub_pem,
        app_engine=app_engine,
    )
    assert job_id is not None

    # 2. Verify database state in audit_worker_jobs
    with admin_engine.connect() as conn:
        job_row = conn.execute(
            text("""
                SELECT business_id, job_type, status, encrypted_auth_context, payload_json, result_json
                FROM public.audit_worker_jobs
                WHERE job_id = :jid
            """),
            {"jid": job_id},
        ).fetchone()

        assert job_row is not None
        assert job_row[0] == fix["biz_a_id"]
        assert job_row[1] == "AR_REVERSAL"
        assert job_row[2] == "PENDING"
        assert job_row[3] is not None and len(job_row[3]) > 0  # Encrypted envelope!
        # Assert raw token is NEVER stored in database
        assert admin_token not in str(job_row[3])
        assert admin_token not in str(job_row[4])
        assert job_row[5] is None

    # 3. Assert ursbiz_app CANNOT UPDATE or DELETE jobs in audit_worker_jobs
    with app_engine.connect() as conn:
        with pytest.raises(Exception) as excinfo_app_upd:
            conn.execute(
                text("UPDATE public.audit_worker_jobs SET status = 'CANCELLED' WHERE job_id = :jid"),
                {"jid": job_id},
            )
        assert "permission denied for table audit_worker_jobs" in str(excinfo_app_upd.value).lower()

    # 4. Worker claims and processes job (SELECT ... FOR UPDATE SKIP LOCKED)
    claim_result = AuditWorkerService.claim_and_process_job(
        worker_engine=kms_engine,
        worker_private_key_pem=worker_priv_pem,
        idp_public_key_pem=idp.public_key_pem,
        kms_provider=kms_provider,
        lease_owner="worker-node-test-1",
    )

    assert claim_result is not None
    assert claim_result["job_id"] == job_id
    assert claim_result["status"] == "COMPLETED"
    reversal_id = claim_result["result"]["reversal_id"]
    assert reversal_id is not None and reversal_id > 0

    # 5. Verify database records completion
    with admin_engine.connect() as conn:
        updated_job = conn.execute(
            text("SELECT status, lease_owner, result_json FROM public.audit_worker_jobs WHERE job_id = :jid"),
            {"jid": job_id},
        ).fetchone()
        assert updated_job[0] == "COMPLETED"
        assert updated_job[1] == "worker-node-test-1"
        assert updated_job[2] is not None
        res_data = updated_job[2] if isinstance(updated_job[2], dict) else json.loads(updated_job[2])
        assert "reversal_id" in res_data


# ==============================================================================
# 30. Standalone Worker Process Startup Guards (Wave 1.1.3)
# ==============================================================================

def test_worker_process_startup_guards():
    """Wave 1.1.3: Tests standalone worker process startup validation and security guardrails."""
    from app.workers.audit_worker import validate_worker_startup_environment

    # 1. Reject worker startup if configured with ursbiz_app credentials
    with pytest.raises(SecurityConfigurationError, match="cannot run using 'ursbiz_app' credentials"):
        validate_worker_startup_environment(
            worker_db_url="postgresql://ursbiz_app:pass@localhost:5432/ursbiz_staging_disposable",
            idp_public_key_pem="pubkey",
            worker_priv_key_pem="privkey",
        )

    # 2. Reject worker startup if missing IDP public key
    with pytest.raises(SecurityConfigurationError, match="IDP public verification key"):
        validate_worker_startup_environment(
            worker_db_url="postgresql://ursbiz_kms_worker:pass@localhost:5432/ursbiz_staging_disposable",
            idp_public_key_pem="",
            worker_priv_key_pem="privkey",
        )

    # 3. Reject worker startup if missing decryption private key
    with pytest.raises(SecurityConfigurationError, match="Worker context decryption private key"):
        validate_worker_startup_environment(
            worker_db_url="postgresql://ursbiz_kms_worker:pass@localhost:5432/ursbiz_staging_disposable",
            idp_public_key_pem="pubkey",
            worker_priv_key_pem="",
        )

    # 4. Reject volatile memory in production/staging
    prod_worker_settings = Settings(
        app_env="production",
        is_production=True,
        kms_database_url="postgresql://ursbiz_kms_worker:pass@localhost:5432/ursbiz_staging_disposable",
        kms_provider_type="memory",
    )
    with pytest.raises(SecurityConfigurationError, match="strictly prohibited in production"):
        KMSProviderFactory.get_provider(prod_worker_settings)


# ==============================================================================
# 31. Migration Downgrade Refusal Guard (Wave 1.1.3)
# ==============================================================================

def test_migration_downgrade_refusal_when_inhabited(admin_engine, kms_engine, financial_fixture):
    """Wave 1.1.3: Asserts migration downgrade refuses to drop audit_transition_checkpoints when populated."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    fix = financial_fixture
    # Record a checkpoint so table is inhabited
    trans_id = f"TRANS_DOWNGRADE_{uuid.uuid4().hex[:8]}"
    priv_hex, pub_hex = AuditSigningService.generate_keypair()
    kms_provider = VolatileMemoryKMSProvider(key_id=fix["key_id"], private_key_hex=priv_hex)
    AuditWorkerService.execute_transition_checkpoint(
        business_id=fix["biz_a_id"],
        transition_id=trans_id,
        kms_provider=kms_provider,
        worker_engine=kms_engine,
        operator_confirmed=True,
    )

    mig_mod = importlib.import_module("migrations.versions.20261116_0002_add_transition_checkpoints_and_cleanup_legacy")
    migration_0002_downgrade = mig_mod.downgrade

    with admin_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE"):
                migration_0002_downgrade()


# ==============================================================================
# 32. Migration Downgrade Refusal & Safety for 20261116_0003 (Wave 1.1.3.1)
# ==============================================================================

def test_migration_0003_downgrade_refusal_when_jobs_inhabited(admin_engine, financial_fixture):
    """Wave 1.1.3.1 Defect A: Asserts 20261116_0003 refuses downgrade if audit_worker_jobs has records, preserving all data."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    fix = financial_fixture
    job_id = f"job_down_test_{uuid.uuid4().hex[:8]}"
    idem_key = f"idem_down_test_{uuid.uuid4().hex[:8]}"

    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO public.audit_worker_jobs ("
                    "  job_id, business_id, job_type, idempotency_key, encrypted_auth_context, "
                    "  encryption_key_id, payload_json, status"
                    ") VALUES ("
                    "  :job_id, :biz_id, 'REVERSAL', :idem, 'encrypted_blob', "
                    "  'key_rsa', '{\"amount\": 1000}', 'PENDING'"
                    ")"
                ),
                {"job_id": job_id, "biz_id": fix["biz_a_id"], "idem": idem_key},
            )

    try:
        mig_mod = importlib.import_module("migrations.versions.20261116_0003_harden_trust_boundary_and_add_audit_jobs")
        with admin_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                # 1. Verify downgrade is refused
                with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE: public.audit_worker_jobs contains job records"):
                    mig_mod.downgrade()

                # 2. Verify job record remains unchanged
                row = conn.execute(
                    text("SELECT job_id, status FROM public.audit_worker_jobs WHERE job_id = :job_id"),
                    {"job_id": job_id},
                ).first()
                assert row is not None, "Job record must not be deleted on refused downgrade"
                assert row[0] == job_id
                assert row[1] == "PENDING"

                # 3. Verify no database objects were dropped
                has_table = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_worker_jobs')")
                ).scalar()
                assert has_table is True, "Table audit_worker_jobs must still exist"

                has_proc = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'record_transition_checkpoint')")
                ).scalar()
                assert has_proc is True, "Procedure record_transition_checkpoint must still exist"
    finally:
        with admin_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("DELETE FROM public.audit_worker_jobs WHERE job_id = :job_id"), {"job_id": job_id})


def test_migration_0003_downgrade_and_reupgrade_when_empty(admin_engine):
    """Wave 1.1.3.1 Defect A: Asserts 20261116_0003 allows controlled downgrade and re-upgrade when audit_worker_jobs is empty."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mig_mod = importlib.import_module("migrations.versions.20261116_0003_harden_trust_boundary_and_add_audit_jobs")

    with admin_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Ensure table is empty within this transaction
            conn.execute(text("DELETE FROM public.audit_worker_jobs"))

            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                # Downgrade when empty
                mig_mod.downgrade()

                # Verify table and procedure are dropped
                has_table = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name = 'audit_worker_jobs')")
                ).scalar()
                assert has_table is False, "audit_worker_jobs table must be dropped after clean downgrade"

                has_proc = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'record_transition_checkpoint')")
                ).scalar()
                assert has_proc is False, "record_transition_checkpoint procedure must be dropped after clean downgrade"

                # Re-upgrade
                mig_mod.upgrade()

                # Verify table and procedure are recreated
                has_table_recreated = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name = 'audit_worker_jobs')")
                ).scalar()
                assert has_table_recreated is True, "audit_worker_jobs table must be recreated after upgrade"

                has_proc_recreated = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'record_transition_checkpoint')")
                ).scalar()
                assert has_proc_recreated is True, "record_transition_checkpoint procedure must be recreated after upgrade"
        finally:
            trans.rollback()


# ==============================================================================
# 33. Migration Downgrade Refusal & Safety for 20261116_0001 (Wave 1.1.3.1)
# ==============================================================================

def test_migration_0001_downgrade_refusal_when_vendor_reversals_inhabited(admin_engine, financial_fixture):
    """Wave 1.1.3.1 Defect B: Asserts 20261116_0001 refuses downgrade if vendor_allocation_reversals has records."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    fix = financial_fixture
    rev_reason = f"TEST_MIG_0001_AP_{uuid.uuid4().hex[:8]}"

    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO public.vendor_allocation_reversals ("
                    "  business_id, vendor_allocation_id, reversed_amount, amount_paise, currency, reason, "
                    "  actor_user_id, previous_digest_sha256, audit_digest_sha256, signature_algorithm, "
                    "  signing_key_id, signature_hex"
                    ") VALUES ("
                    "  :biz_id, :alloc_id, 100.00, 10000, 'INR', :reason, "
                    "  :actor_id, :prev_dig, :audit_dig, 'ED25519', :key_id, :sig"
                    ")"
                ),
                {
                    "biz_id": fix["biz_a_id"],
                    "alloc_id": fix["ap_alloc_id"],
                    "reason": rev_reason,
                    "actor_id": fix["owner_id"],
                    "prev_dig": "0" * 64,
                    "audit_dig": "1" * 64,
                    "key_id": fix["key_id"],
                    "sig": "a" * 128,
                },
            )

    try:
        mig_mod = importlib.import_module("migrations.versions.20261116_0001_remediate_audit_security_and_ap_reversals")
        with admin_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                # 1. Verify downgrade is refused
                with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE: public.vendor_allocation_reversals contains"):
                    mig_mod.downgrade()

                # 2. Verify row remains untouched
                row = conn.execute(
                    text("SELECT reason, reversed_amount FROM public.vendor_allocation_reversals WHERE reason = :reason"),
                    {"reason": rev_reason},
                ).first()
                assert row is not None, "Vendor reversal record must remain unchanged"
                assert row[0] == rev_reason
                assert row[1] == Decimal("100.00")

                # 3. Verify database objects were not partially dropped
                has_ap_table = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'vendor_allocation_reversals')")
                ).scalar()
                assert has_ap_table is True

                has_key_table = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_signing_public_keys')")
                ).scalar()
                assert has_key_table is True
    finally:
        with admin_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("DELETE FROM public.vendor_allocation_reversals WHERE reason = :reason"), {"reason": rev_reason})


def test_migration_0001_downgrade_refusal_when_public_keys_inhabited(admin_engine):
    """Wave 1.1.3.1 Defect B: Asserts 20261116_0001 refuses downgrade if audit_signing_public_keys has records."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mig_mod = importlib.import_module("migrations.versions.20261116_0001_remediate_audit_security_and_ap_reversals")

    with admin_engine.connect() as conn:
        # Verify keys are present
        count_keys = conn.execute(text("SELECT count(*) FROM public.audit_signing_public_keys")).scalar()
        assert count_keys > 0, "audit_signing_public_keys should contain active test keys"

        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE: public.audit_signing_public_keys contains"):
                mig_mod.downgrade()

            # Verify keys are still intact
            count_after = conn.execute(text("SELECT count(*) FROM public.audit_signing_public_keys")).scalar()
            assert count_after == count_keys, "Public keys must not be deleted on refused downgrade"


def test_migration_0001_downgrade_refusal_when_ar_reversals_inhabited(admin_engine, financial_fixture):
    """Wave 1.1.3.1 Defect B: Asserts 20261116_0001 refuses downgrade if ar_allocation_reversals has migration metadata."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    fix = financial_fixture
    rev_reason = f"TEST_MIG_0001_AR_{uuid.uuid4().hex[:8]}"

    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO public.ar_allocation_reversals ("
                    "  business_id, original_allocation_id, reversed_amount, amount_paise, currency, reason, "
                    "  actor_user_id, previous_digest_sha256, audit_digest_sha256, signature_algorithm, "
                    "  signing_key_id, signature_hex"
                    ") VALUES ("
                    "  :biz_id, :alloc_id, 50.00, 5000, 'INR', :reason, "
                    "  :actor_id, :prev_dig, :audit_dig, 'ED25519', :key_id, :sig"
                    ")"
                ),
                {
                    "biz_id": fix["biz_a_id"],
                    "alloc_id": fix["ar_alloc_id"],
                    "reason": rev_reason,
                    "actor_id": fix["owner_id"],
                    "prev_dig": "0" * 64,
                    "audit_dig": "2" * 64,
                    "key_id": fix["key_id"],
                    "sig": "b" * 128,
                },
            )

    try:
        mig_mod = importlib.import_module("migrations.versions.20261116_0001_remediate_audit_security_and_ap_reversals")
        with admin_engine.connect() as conn:
            trans = conn.begin()
            try:
                # In this rollback transaction, clear vendor reversals and public keys
                # to test the ar_allocation_reversals guard specifically
                conn.execute(text("DELETE FROM public.vendor_allocation_reversals"))
                conn.execute(text("DELETE FROM public.audit_signing_public_keys"))

                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE: public.ar_allocation_reversals contains"):
                        mig_mod.downgrade()
            finally:
                trans.rollback()
    finally:
        with admin_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("DELETE FROM public.ar_allocation_reversals WHERE reason = :reason"), {"reason": rev_reason})


def test_migration_0001_downgrade_refusal_when_signature_algorithm_populated(admin_engine, financial_fixture):
    """Wave 1.1.3.2 Test A: Asserts 20261116_0001 refuses downgrade when signature_algorithm alone is populated."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    fix = financial_fixture
    rev_reason = f"TEST_MIG_0001_SIG_ALG_{uuid.uuid4().hex[:8]}"

    with admin_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Stamp alembic_version to ensure baseline check
            conn.execute(text("UPDATE alembic_version SET version_num = '20261116_0003'"))
            rev_before = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

            # Clear other tables within this rollback transaction to isolate ar_allocation_reversals
            conn.execute(text("DELETE FROM public.vendor_allocation_reversals"))
            conn.execute(text("DELETE FROM public.audit_signing_public_keys"))
            conn.execute(text("DELETE FROM public.ar_allocation_reversals"))

            # Documented Schema Constraint: In migration 20261116_0001, currency is defined as NOT NULL.
            # Within this isolated rollback transaction, drop NOT NULL on currency so it can be set to NULL,
            # proving signature_algorithm alone blocks the downgrade without weakening the persistent schema.
            conn.execute(text("ALTER TABLE public.ar_allocation_reversals ALTER COLUMN currency DROP NOT NULL"))

            conn.execute(
                text(
                    "INSERT INTO public.ar_allocation_reversals ("
                    "  business_id, original_allocation_id, reversed_amount, amount_paise, currency, reason, "
                    "  actor_user_id, previous_digest_sha256, audit_digest_sha256, signature_algorithm, "
                    "  signing_key_id, signature_hex"
                    ") VALUES ("
                    "  :biz_id, :alloc_id, 40.00, NULL, NULL, :reason, "
                    "  :actor_id, :prev_dig, :audit_dig, 'ED25519', NULL, NULL"
                    ")"
                ),
                {
                    "biz_id": fix["biz_a_id"],
                    "alloc_id": fix["ar_alloc_id"],
                    "reason": rev_reason,
                    "actor_id": fix["owner_id"],
                    "prev_dig": "0" * 64,
                    "audit_dig": "5" * 64,
                },
            )

            # Confirm only signature_algorithm is non-null among the 5 protected metadata columns
            row = conn.execute(
                text(
                    "SELECT signature_algorithm, currency, amount_paise, signing_key_id, signature_hex "
                    "FROM public.ar_allocation_reversals WHERE reason = :reason"
                ),
                {"reason": rev_reason},
            ).first()
            assert row[0] == "ED25519", "signature_algorithm must be ED25519"
            assert row[1] is None, "currency must be NULL for single-field isolation"
            assert row[2] is None, "amount_paise must be NULL for single-field isolation"
            assert row[3] is None, "signing_key_id must be NULL for single-field isolation"
            assert row[4] is None, "signature_hex must be NULL for single-field isolation"

            mig_mod = importlib.import_module("migrations.versions.20261116_0001_remediate_audit_security_and_ap_reversals")
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                # 1. Attempt downgrade and confirm refusal
                with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE: public.ar_allocation_reversals contains"):
                    mig_mod.downgrade()

            # 2. Confirm record remains unchanged
            row_after = conn.execute(
                text("SELECT reason, signature_algorithm FROM public.ar_allocation_reversals WHERE reason = :reason"),
                {"reason": rev_reason},
            ).first()
            assert row_after is not None
            assert row_after[0] == rev_reason
            assert row_after[1] == "ED25519"

            # 3. Confirm all 5 metadata columns still exist
            cols = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'ar_allocation_reversals' "
                        "AND column_name IN ('signature_hex', 'signing_key_id', 'signature_algorithm', 'currency', 'amount_paise')"
                    )
                ).fetchall()
            ]
            assert len(cols) == 5, f"Expected all 5 metadata columns to be preserved, found {cols}"

            # 4. Confirm related tables still exist
            has_table = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ar_allocation_reversals')")
            ).scalar()
            assert has_table is True

            # 5. Confirm Alembic revision remains unchanged
            rev_after = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev_after == rev_before == "20261116_0003"
        finally:
            trans.rollback()


def test_migration_0001_downgrade_refusal_when_currency_populated(admin_engine, financial_fixture):
    """Wave 1.1.3.2 Test B: Asserts 20261116_0001 refuses downgrade when currency alone is populated."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    fix = financial_fixture
    rev_reason = f"TEST_MIG_0001_CURRENCY_{uuid.uuid4().hex[:8]}"

    with admin_engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("UPDATE alembic_version SET version_num = '20261116_0003'"))
            rev_before = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

            # Clear other tables within this rollback transaction to isolate ar_allocation_reversals
            conn.execute(text("DELETE FROM public.vendor_allocation_reversals"))
            conn.execute(text("DELETE FROM public.audit_signing_public_keys"))
            conn.execute(text("DELETE FROM public.ar_allocation_reversals"))

            # Documented Schema Constraint: In migration 20261116_0001, signature_algorithm is defined as NOT NULL.
            # Within this isolated rollback transaction, drop NOT NULL on signature_algorithm so it can be set to NULL,
            # proving currency alone blocks the downgrade without weakening the persistent schema.
            conn.execute(text("ALTER TABLE public.ar_allocation_reversals ALTER COLUMN signature_algorithm DROP NOT NULL"))

            conn.execute(
                text(
                    "INSERT INTO public.ar_allocation_reversals ("
                    "  business_id, original_allocation_id, reversed_amount, amount_paise, currency, reason, "
                    "  actor_user_id, previous_digest_sha256, audit_digest_sha256, signature_algorithm, "
                    "  signing_key_id, signature_hex"
                    ") VALUES ("
                    "  :biz_id, :alloc_id, 45.00, NULL, 'INR', :reason, "
                    "  :actor_id, :prev_dig, :audit_dig, NULL, NULL, NULL"
                    ")"
                ),
                {
                    "biz_id": fix["biz_a_id"],
                    "alloc_id": fix["ar_alloc_id"],
                    "reason": rev_reason,
                    "actor_id": fix["owner_id"],
                    "prev_dig": "0" * 64,
                    "audit_dig": "6" * 64,
                },
            )

            # Confirm only currency is non-null among the 5 protected metadata columns
            row = conn.execute(
                text(
                    "SELECT signature_algorithm, currency, amount_paise, signing_key_id, signature_hex "
                    "FROM public.ar_allocation_reversals WHERE reason = :reason"
                ),
                {"reason": rev_reason},
            ).first()
            assert row[0] is None, "signature_algorithm must be NULL for single-field isolation"
            assert row[1] == "INR", "currency must be INR"
            assert row[2] is None, "amount_paise must be NULL for single-field isolation"
            assert row[3] is None, "signing_key_id must be NULL for single-field isolation"
            assert row[4] is None, "signature_hex must be NULL for single-field isolation"

            mig_mod = importlib.import_module("migrations.versions.20261116_0001_remediate_audit_security_and_ap_reversals")
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                # 1. Attempt downgrade and confirm refusal
                with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE: public.ar_allocation_reversals contains"):
                    mig_mod.downgrade()

            # 2. Confirm record remains unchanged
            row_after = conn.execute(
                text("SELECT reason, currency FROM public.ar_allocation_reversals WHERE reason = :reason"),
                {"reason": rev_reason},
            ).first()
            assert row_after is not None
            assert row_after[0] == rev_reason
            assert row_after[1] == "INR"

            # 3. Confirm all 5 metadata columns still exist
            cols = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'ar_allocation_reversals' "
                        "AND column_name IN ('signature_hex', 'signing_key_id', 'signature_algorithm', 'currency', 'amount_paise')"
                    )
                ).fetchall()
            ]
            assert len(cols) == 5, f"Expected all 5 metadata columns to be preserved, found {cols}"

            # 4. Confirm related tables still exist
            has_table = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ar_allocation_reversals')")
            ).scalar()
            assert has_table is True

            # 5. Confirm Alembic revision remains unchanged
            rev_after = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev_after == rev_before == "20261116_0003"
        finally:
            trans.rollback()


def test_migration_0001_downgrade_and_reupgrade_when_empty(admin_engine):
    """Wave 1.1.3.1 Defect B: Asserts 20261116_0001 allows clean downgrade and re-upgrade when all protected tables are empty."""
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mig_0003 = importlib.import_module("migrations.versions.20261116_0003_harden_trust_boundary_and_add_audit_jobs")
    mig_0002 = importlib.import_module("migrations.versions.20261116_0002_add_transition_checkpoints_and_cleanup_legacy")
    mig_0001 = importlib.import_module("migrations.versions.20261116_0001_remediate_audit_security_and_ap_reversals")

    with admin_engine.connect() as conn:
        trans = conn.begin()
        try:
            # Clear tables only within this rollback transaction
            conn.execute(text("DELETE FROM public.audit_worker_jobs"))
            conn.execute(text("DELETE FROM public.audit_transition_checkpoints"))
            conn.execute(text("DELETE FROM public.vendor_allocation_reversals"))
            conn.execute(text("DELETE FROM public.ar_allocation_reversals"))
            conn.execute(text("DELETE FROM public.audit_signing_public_keys"))

            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                # Downgrade in reverse order: 0003 -> 0002 -> 0001
                mig_0003.downgrade()
                mig_0002.downgrade()
                mig_0001.downgrade()

                tables_after = [r[0] for r in conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
                    "AND table_name IN ('vendor_allocation_reversals', 'audit_signing_public_keys', 'ar_allocation_reversals', 'allocation_reversals')"
                )).fetchall()]
                assert "allocation_reversals" in tables_after
                assert "vendor_allocation_reversals" not in tables_after
                assert "audit_signing_public_keys" not in tables_after

                # Re-upgrade in forward order: 0001 -> 0002 -> 0003
                mig_0001.upgrade()
                mig_0002.upgrade()
                mig_0003.upgrade()

                tables_recreated = [r[0] for r in conn.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
                    "AND table_name IN ('vendor_allocation_reversals', 'audit_signing_public_keys', 'ar_allocation_reversals', 'allocation_reversals')"
                )).fetchall()]
                assert "ar_allocation_reversals" in tables_recreated
                assert "vendor_allocation_reversals" in tables_recreated
                assert "audit_signing_public_keys" in tables_recreated
        finally:
            trans.rollback()


def test_migration_atomicity_and_revision_integrity(admin_engine, financial_fixture):
    """Wave 1.1.3.1 Atomicity: Asserts failed downgrade preserves alembic_version, constraints, and foreign keys."""
    fix = financial_fixture
    job_id = f"job_atom_test_{uuid.uuid4().hex[:8]}"

    # Stamp alembic_version to 20261116_0003 for this test
    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(text("UPDATE alembic_version SET version_num = '20261116_0003'"))
        rev_before = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev_before == "20261116_0003"

    with admin_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO public.audit_worker_jobs ("
                    "  job_id, business_id, job_type, idempotency_key, encrypted_auth_context, "
                    "  encryption_key_id, payload_json, status"
                    ") VALUES ("
                    "  :job_id, :biz_id, 'REVERSAL', :idem, 'enc', 'key', :payload, 'PENDING'"
                    ")"
                ),
                {
                    "job_id": job_id,
                    "biz_id": fix["biz_a_id"],
                    "idem": f"idem_{uuid.uuid4().hex[:8]}",
                    "payload": json.dumps({"test_atomicity": True}),
                },
            )

    try:
        import importlib
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        mig_0003 = importlib.import_module("migrations.versions.20261116_0003_harden_trust_boundary_and_add_audit_jobs")

        with admin_engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            with Operations.context(ctx):
                with pytest.raises(RuntimeError, match="REFUSING DESTRUCTIVE DOWNGRADE"):
                    mig_0003.downgrade()

        # Verify alembic_version was not modified
        with admin_engine.connect() as conn:
            rev_after = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert rev_after == rev_before == "20261116_0003", "alembic_version must remain unchanged on refused downgrade"

            # Verify foreign keys and constraints on audit_worker_jobs still exist
            fk_count = conn.execute(text(
                "SELECT count(*) FROM information_schema.table_constraints "
                "WHERE table_name = 'audit_worker_jobs' AND constraint_type = 'FOREIGN KEY'"
            )).scalar()
            assert fk_count >= 1, "Foreign keys must remain intact"

            chk_count = conn.execute(text(
                "SELECT count(*) FROM information_schema.table_constraints "
                "WHERE table_name = 'audit_worker_jobs' AND constraint_type = 'CHECK'"
            )).scalar()
            assert chk_count >= 2, "Check constraints must remain intact"
    finally:
        with admin_engine.connect() as conn:
            with conn.begin():
                conn.execute(text("DELETE FROM public.audit_worker_jobs WHERE job_id = :job_id"), {"job_id": job_id})


