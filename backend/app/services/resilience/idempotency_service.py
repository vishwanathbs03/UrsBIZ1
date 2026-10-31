"""Idempotency Service (Phase 5 Platform Resilience).

Guarantees at-most-once execution for mission-critical write operations
(sales data ingestion, recommendation state updates, and export generation).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any, Optional
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import IdempotencyConflictError
from app.models.idempotency import IdempotencyRecord

logger = logging.getLogger("atlas.resilience.idempotency")


class IdempotencyService:
    """Manages operation locking, duplicate detection, and idempotent response replay."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def compute_request_hash(*parts: str | bytes | dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash across heterogeneous request elements."""
        hasher = hashlib.sha256()
        for p in parts:
            if isinstance(p, bytes):
                hasher.update(p)
            elif isinstance(p, dict):
                hasher.update(json.dumps(p, sort_keys=True).encode("utf-8"))
            elif isinstance(p, str):
                hasher.update(p.encode("utf-8"))
            else:
                hasher.update(str(p).encode("utf-8"))
        return hasher.hexdigest()

    def acquire_lock(
        self,
        business_id: int,
        idempotency_key: str,
        operation_type: str,
        request_hash: str,
        ttl_seconds: int = 86400,
    ) -> tuple[bool, Optional[dict[str, Any]]]:
        """Check idempotency status and acquire processing lock.

        Returns:
            (is_cached_replay, cached_response_payload_dict)
            - If (True, payload): caller should immediately return cached payload without executing operation.
            - If (False, None): lock acquired; caller proceeds with execution.
        Raises:
            IdempotencyConflictError: If request with same key is currently in progress.
        """
        now = datetime.now(timezone.utc)
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.business_id == business_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        record = self.db.scalars(stmt).first()

        if record is not None:
            # Check if expired (normalizing tzinfo for SQLite compatibility)
            exp = record.expires_at
            if exp is not None and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)

            if exp and exp < now:
                logger.info(f"[idempotency] Key {idempotency_key} expired. Re-initializing lock.")
                record.status = "PROCESSING"
                record.request_hash = request_hash
                record.operation_type = operation_type
                record.created_at = now
                record.expires_at = now + timedelta(seconds=ttl_seconds)
                record.response_payload = None
                self.db.commit()
                return False, None

            # Check status
            if record.status == "COMPLETED":
                logger.info(f"[idempotency] Cache hit for key {idempotency_key}. Replaying payload.")
                payload = json.loads(record.response_payload) if record.response_payload else {}
                return True, payload

            elif record.status == "PROCESSING":
                # If processing for less than 120 seconds, reject concurrent duplicate
                rec_created = record.created_at
                if rec_created is not None and rec_created.tzinfo is None:
                    rec_created = rec_created.replace(tzinfo=timezone.utc)
                elapsed = (now - rec_created).total_seconds()
                if elapsed < 120.0:
                    logger.warning(
                        f"[idempotency] Concurrent lock conflict on key {idempotency_key} (in-flight {elapsed:.1f}s)."
                    )
                    raise IdempotencyConflictError(
                        safe_message="An identical operation is currently being processed. Please wait a moment."
                    )
                else:
                    # Stuck in-progress lock (> 120s) -> reclaim
                    logger.warning(f"[idempotency] Reclaiming orphaned lock on key {idempotency_key} ({elapsed:.1f}s).")
                    record.status = "PROCESSING"
                    record.request_hash = request_hash
                    record.created_at = now
                    record.expires_at = now + timedelta(seconds=ttl_seconds)
                    self.db.commit()
                    return False, None

            else:  # FAILED
                logger.info(f"[idempotency] Prior attempt failed for key {idempotency_key}. Retrying execution.")
                record.status = "PROCESSING"
                record.request_hash = request_hash
                record.created_at = now
                record.expires_at = now + timedelta(seconds=ttl_seconds)
                self.db.commit()
                return False, None

        # Create new lock
        new_record = IdempotencyRecord(
            business_id=business_id,
            idempotency_key=idempotency_key,
            operation_type=operation_type,
            request_hash=request_hash,
            status="PROCESSING",
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self.db.add(new_record)
        self.db.commit()
        return False, None

    def record_success(
        self,
        business_id: int,
        idempotency_key: str,
        response_data: dict[str, Any] | BaseModel,
    ) -> None:
        """Mark operation completed and cache response JSON for deterministic replay."""
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.business_id == business_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        record = self.db.scalars(stmt).first()
        if record is not None:
            if hasattr(response_data, "model_dump"):
                payload_str = json.dumps(response_data.model_dump(), default=str)
            elif isinstance(response_data, dict):
                payload_str = json.dumps(response_data, default=str)
            else:
                payload_str = str(response_data)

            record.status = "COMPLETED"
            record.response_payload = payload_str
            self.db.commit()

    def record_failure(
        self,
        business_id: int,
        idempotency_key: str,
        error_msg: str,
    ) -> None:
        """Mark operation failed so subsequent requests can re-attempt."""
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.business_id == business_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        record = self.db.scalars(stmt).first()
        if record is not None:
            record.status = "FAILED"
            self.db.commit()
