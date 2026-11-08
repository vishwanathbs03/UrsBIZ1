"""Standalone Privileged Audit Signing Worker Process.

Part of Wave 1.1.3 Remediation (Process Isolation & Credential Separation):
  - Runs as an independent process/container decoupled from FastAPI.
  - Holds dedicated database credentials (ursbiz_kms_worker).
  - Holds worker decryption private key (to unwrap auth context).
  - Holds IdP public key (to verify asymmetric RS256 JWTs).
  - Holds Cloud KMS signing identity.
  - FastAPI is strictly forbidden from running this entrypoint or reading these credentials.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text

from app.config.settings import get_settings
from app.services.audit_signing_service import (
    KMSProviderFactory,
    SecurityConfigurationError,
)
from app.services.audit_worker_service import AuditWorkerService


def validate_worker_startup_environment(worker_db_url: str, idp_public_key_pem: str | None, worker_priv_key_pem: str | None) -> None:
    """Enforces strict process isolation and credential boundary startup checks."""
    # 1. Database Role Guard: Worker MUST NOT run with application credentials
    if "ursbiz_app" in worker_db_url:
        raise SecurityConfigurationError(
            "CRITICAL VIOLATION: Audit worker process cannot run using 'ursbiz_app' credentials. "
            "Dedicated 'ursbiz_kms_worker' database credentials are required."
        )

    # 2. Key Presence Guard
    if not idp_public_key_pem or not idp_public_key_pem.strip():
        raise SecurityConfigurationError(
            "Worker startup failed: IDP public verification key (IDP_PUBLIC_KEY_PEM) must be configured."
        )

    if not worker_priv_key_pem or not worker_priv_key_pem.strip():
        raise SecurityConfigurationError(
            "Worker startup failed: Worker context decryption private key (WORKER_DECRYPTION_PRIVATE_KEY_PEM) must be configured."
        )

    # 3. Cloud KMS Provider Guard: Memory provider forbidden in staging/production
    settings = get_settings()
    env = getattr(settings, "app_env", "development").lower()
    if env in ("production", "staging") and getattr(settings, "kms_provider_type", "") == "memory":
        raise SecurityConfigurationError(
            f"VolatileMemoryKMSProvider is strictly prohibited in {env}."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="UrsBiz Standalone Privileged Audit Worker")
    parser.add_argument("--run-once", action="store_true", help="Claim and process at most one job and exit")
    parser.add_argument("--test-startup", action="store_true", help="Validate worker startup guards and exit")
    parser.add_argument("--worker-id", default=f"worker-{os.getpid()}", help="Identifier for lease ownership")
    args = parser.parse_args()

    worker_db_url = os.getenv(
        "KMS_DATABASE_URL",
        os.getenv("TEST_KMS_DB_URL", "postgresql://ursbiz_kms_worker:kms_worker_pass@localhost:5432/ursbiz_staging_disposable"),
    )
    idp_pub_key = os.getenv("IDP_PUBLIC_KEY_PEM")
    worker_priv_key = os.getenv("WORKER_DECRYPTION_PRIVATE_KEY_PEM")

    if args.test_startup:
        print("[AUDIT WORKER] Validating startup guards...")
        try:
            validate_worker_startup_environment(worker_db_url, idp_pub_key, worker_priv_key)
            print("[AUDIT WORKER] Startup guards PASSED.")
            return 0
        except SecurityConfigurationError as e:
            print(f"[AUDIT WORKER] Startup guard check FAILED: {e}", file=sys.stderr)
            return 1

    validate_worker_startup_environment(worker_db_url, idp_pub_key, worker_priv_key)
    engine = create_engine(worker_db_url)
    kms_provider = KMSProviderFactory.get_provider()

    print(f"[AUDIT WORKER] Worker '{args.worker_id}' connected to database. Awaiting jobs...")

    if args.run_once:
        res = AuditWorkerService.claim_and_process_job(
            worker_engine=engine,
            worker_private_key_pem=worker_priv_key,  # type: ignore
            idp_public_key_pem=idp_pub_key,          # type: ignore
            kms_provider=kms_provider,
            lease_owner=args.worker_id,
        )
        if res:
            print(f"[AUDIT WORKER] Processed job {res.get('job_id')}: status={res.get('status')}")
        else:
            print("[AUDIT WORKER] No pending jobs found.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
