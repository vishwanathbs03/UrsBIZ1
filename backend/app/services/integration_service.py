"""Integration and Connector Framework Service (Phase 6.27).

Orchestrates:
  - Connector catalog registry and capabilities.
  - Tenant-isolated connection lifecycle (NOT_CONFIGURED -> CONFIGURED -> CONNECTING -> CONNECTED).
  - Secure credential storage and authenticated encryption with zero plaintext leakage.
  - Concurrency-protected synchronization execution and incremental cursor progression.
  - Data normalization and deduplication directly into standard SalesTransaction models.
  - Provenance lineage registration in BusinessDataProvenance.
  - Immutable audit logging for all connection and sync lifecycle events.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
import uuid

from fastapi import HTTPException, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.data_provenance import BusinessDataProvenance
from app.models.integration import (
    ConnectionStatus,
    ErrorCategory,
    IntegrationAudit,
    IntegrationConnection,
    IntegrationSyncExecution,
    SyncExecutionStatus,
    SyncTriggerType,
)
from app.models.sales import SalesTransaction, SalesUpload
from app.models.user import User
from app.repositories.sales_repository import SalesRepository
from app.schemas.integration import (
    ConfigFieldOut,
    ConnectionConfigUpdateReq,
    ConnectionCreateReq,
    ConnectionOut,
    ConnectionTestResultOut,
    ConnectorCatalogueItemOut,
    CredentialRotateReq,
    IntegrationAuditListResponse,
    IntegrationAuditOut,
    SyncExecutionListResponse,
    SyncExecutionOut,
)
from app.services.connectors.base import (
    BaseDataConnector,
    NormalizedTransaction,
    OperationalStatus,
)
from app.services.connectors.registry import ConnectorRegistry
from app.services.connectors.vault import ConnectorCredentialVault

logger = logging.getLogger("atlas.integrations.service")


class IntegrationService:
    """Service facade coordinating external connectors, credentials, and data synchronization."""

    def __init__(self, db: Session, vault: ConnectorCredentialVault | None = None) -> None:
        self.db = db
        self.vault = vault or ConnectorCredentialVault()
        self.sales_repo = SalesRepository(db)

    # =========================================================================
    # 1. CATALOGUE
    # =========================================================================

    def list_catalogue(self) -> list[ConnectorCatalogueItemOut]:
        """Return the available connectors and their operational metadata."""
        connectors = ConnectorRegistry.list()
        items: list[ConnectorCatalogueItemOut] = []

        for conn in connectors:
            fields = [
                ConfigFieldOut(
                    key=f.key,
                    label=f.label,
                    field_type=f.field_type,
                    required=f.required,
                    description=f.description,
                    default_value=f.default_value,
                    options=f.options,
                    is_secret=f.is_secret,
                )
                for f in conn.get_config_fields()
            ]
            items.append(
                ConnectorCatalogueItemOut(
                    connector_id=conn.connector_id,
                    name=conn.name,
                    provider=conn.provider,
                    version=conn.version,
                    description=conn.description,
                    capabilities=[c.value for c in conn.capabilities],
                    auth_method=conn.auth_method,
                    sync_direction=conn.sync_direction.value,
                    operational_status=conn.operational_status.value,
                    known_limitations=conn.known_limitations,
                    config_fields=fields,
                )
            )
        return items

    # =========================================================================
    # 2. CONNECTION MANAGEMENT
    # =========================================================================

    def list_connections(self, business_id: int) -> list[ConnectionOut]:
        """List all external data connections for the given business with masked credentials."""
        connections = (
            self.db.query(IntegrationConnection)
            .filter(IntegrationConnection.business_id == business_id)
            .order_by(desc(IntegrationConnection.created_at))
            .all()
        )
        return [self._to_connection_out(c) for c in connections]

    def get_connection(self, business_id: int, connection_id: int) -> IntegrationConnection:
        """Fetch connection guaranteeing tenant containment, or raise 404."""
        conn = (
            self.db.query(IntegrationConnection)
            .filter(
                IntegrationConnection.id == connection_id,
                IntegrationConnection.business_id == business_id,
            )
            .first()
        )
        if not conn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found for this business.",
            )
        return conn

    def create_connection(
        self,
        business: Business,
        user: User,
        req: ConnectionCreateReq,
    ) -> ConnectionOut:
        """Create and configure a new external data connection."""
        connector = self._get_connector_or_400(req.connector_id)

        # Validate config and credentials syntax
        ok, err = connector.validate_configuration(req.configuration, req.credentials)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration validation failed: {err}",
            )

        # Check duplicate name within the same business
        existing = (
            self.db.query(IntegrationConnection)
            .filter(
                IntegrationConnection.business_id == business.id,
                IntegrationConnection.connector_id == req.connector_id,
                IntegrationConnection.name == req.name.strip(),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A connection named '{req.name.strip()}' already exists for connector '{req.connector_id}'.",
            )

        # Encrypt credentials
        encrypted_creds = self.vault.encrypt_credentials(business.id, req.credentials)
        fingerprint = self.vault.compute_credential_fingerprint(req.credentials)

        conn = IntegrationConnection(
            business_id=business.id,
            connector_id=req.connector_id,
            name=req.name.strip(),
            status=ConnectionStatus.CONFIGURED.value,
            configuration=req.configuration,
            encrypted_credentials=encrypted_creds,
            credential_fingerprint=fingerprint,
            created_by_user_id=user.id,
        )
        self.db.add(conn)
        self.db.flush()

        # Audit event
        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="connection_created",
            details={
                "name": conn.name,
                "connector_id": conn.connector_id,
                "configuration": self.vault.redact_secrets_from_dict(conn.configuration),
            },
        )
        self.db.commit()
        self.db.refresh(conn)

        return self._to_connection_out(conn)

    def update_configuration(
        self,
        business: Business,
        user: User,
        connection_id: int,
        req: ConnectionConfigUpdateReq,
    ) -> ConnectionOut:
        """Update non-sensitive configuration fields for a connection."""
        conn = self.get_connection(business.id, connection_id)
        connector = self._get_connector_or_400(conn.connector_id)

        # Decrypt credentials to re-validate complete configuration
        creds = self._decrypt_connection_creds(conn)
        ok, err = connector.validate_configuration(req.configuration, creds)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration update failed validation: {err}",
            )

        conn.configuration = req.configuration
        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="configuration_updated",
            details={"configuration": self.vault.redact_secrets_from_dict(req.configuration)},
        )
        self.db.commit()
        self.db.refresh(conn)

        return self._to_connection_out(conn)

    def rotate_credentials(
        self,
        business: Business,
        user: User,
        connection_id: int,
        req: CredentialRotateReq,
    ) -> ConnectionOut:
        """Rotate or update encrypted credentials for an existing connection."""
        conn = self.get_connection(business.id, connection_id)
        connector = self._get_connector_or_400(conn.connector_id)

        ok, err = connector.validate_configuration(conn.configuration, req.credentials)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential validation failed: {err}",
            )

        encrypted = self.vault.encrypt_credentials(business.id, req.credentials)
        fingerprint = self.vault.compute_credential_fingerprint(req.credentials)

        conn.encrypted_credentials = encrypted
        conn.credential_fingerprint = fingerprint
        # Reset any lingering reauth status
        if conn.status == ConnectionStatus.REAUTH_REQUIRED.value:
            conn.status = ConnectionStatus.CONFIGURED.value

        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="credentials_rotated",
            details={"credential_fingerprint": fingerprint},
        )
        self.db.commit()
        self.db.refresh(conn)

        return self._to_connection_out(conn)

    def test_connection(
        self,
        business: Business,
        user: User,
        connection_id: int,
    ) -> ConnectionTestResultOut:
        """Test upstream authentication and reachability without mutating connection state."""
        conn = self.get_connection(business.id, connection_id)
        connector = self._get_connector_or_400(conn.connector_id)
        creds = self._decrypt_connection_creds(conn)

        ok, err = connector.test_connection(conn.configuration, creds)
        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="authentication_tested",
            details={"success": ok, "error": err},
        )
        self.db.commit()

        return ConnectionTestResultOut(
            success=ok,
            status="SUCCESS" if ok else "FAILED",
            message="Connection and authentication verified successfully." if ok else (err or "Test failed."),
            tested_at=datetime.now(timezone.utc),
        )

    def connect(
        self,
        business: Business,
        user: User,
        connection_id: int,
    ) -> ConnectionOut:
        """Verify upstream credentials and transition connection state to CONNECTED."""
        conn = self.get_connection(business.id, connection_id)
        connector = self._get_connector_or_400(conn.connector_id)
        creds = self._decrypt_connection_creds(conn)

        conn.status = ConnectionStatus.CONNECTING.value
        self.db.flush()

        ok, err = connector.test_connection(conn.configuration, creds)
        if ok:
            conn.status = ConnectionStatus.CONNECTED.value
            conn.last_error_category = None
            conn.last_error_message = None
            self._record_audit(
                business_id=business.id,
                connection_id=conn.id,
                connector_id=conn.connector_id,
                actor_user_id=user.id,
                event_type="connection_connected",
                details={"status": conn.status},
            )
        else:
            # Determine appropriate failure state
            is_reauth = "expired" in (err or "").lower() or "re-authentication" in (err or "").lower()
            conn.status = ConnectionStatus.REAUTH_REQUIRED.value if is_reauth else ConnectionStatus.ERROR.value
            conn.last_error_category = ErrorCategory.AUTHENTICATION_FAILURE.value
            conn.last_error_message = err
            self._record_audit(
                business_id=business.id,
                connection_id=conn.id,
                connector_id=conn.connector_id,
                actor_user_id=user.id,
                event_type="connection_connect_failed",
                details={"status": conn.status, "error": err},
            )

        self.db.commit()
        self.db.refresh(conn)
        return self._to_connection_out(conn)

    def disconnect(
        self,
        business: Business,
        user: User,
        connection_id: int,
    ) -> ConnectionOut:
        """Disconnect an active connection, preventing further synchronizations."""
        conn = self.get_connection(business.id, connection_id)
        conn.status = ConnectionStatus.DISCONNECTED.value

        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="connection_disconnected",
            details={"status": conn.status},
        )
        self.db.commit()
        self.db.refresh(conn)
        return self._to_connection_out(conn)

    def delete_connection(
        self,
        business: Business,
        user: User,
        connection_id: int,
    ) -> None:
        """Delete a connection and its associated executions."""
        conn = self.get_connection(business.id, connection_id)

        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="connection_deleted",
            details={"connection_name": conn.name},
        )
        self.db.delete(conn)
        self.db.commit()

    # =========================================================================
    # 3. SYNCHRONIZATION ENGINE
    # =========================================================================

    def trigger_sync(
        self,
        business: Business,
        user: User,
        connection_id: int,
        trigger_type: str = "MANUAL",
        batch_limit: int = 100,
    ) -> SyncExecutionOut:
        """Execute a synchronization run for a connected data source."""
        conn = self.get_connection(business.id, connection_id)

        # 1. State check: Must be in CONNECTED status
        if conn.status != ConnectionStatus.CONNECTED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot synchronize connection '{conn.name}' in status '{conn.status}'. "
                    "Connection must be in 'CONNECTED' status."
                ),
            )

        # 2. Concurrency guard: Ensure no other sync is active for this connection
        active_sync = (
            self.db.query(IntegrationSyncExecution)
            .filter(
                IntegrationSyncExecution.connection_id == conn.id,
                IntegrationSyncExecution.status.in_([
                    SyncExecutionStatus.RUNNING.value,
                    SyncExecutionStatus.QUEUED.value,
                ]),
            )
            .first()
        )
        if active_sync:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A synchronization job (ID: {active_sync.execution_id}) is already {active_sync.status} for this connection.",
            )

        # 3. Create execution tracking record
        exec_id = f"sync-{uuid.uuid4().hex[:16]}"
        execution = IntegrationSyncExecution(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            execution_id=exec_id,
            trigger_type=trigger_type,
            status=SyncExecutionStatus.RUNNING.value,
            started_at=datetime.now(timezone.utc),
            sync_cursor_before=conn.sync_cursor,
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        # 4. Execute connector fetch & ingest
        connector = self._get_connector_or_400(conn.connector_id)
        creds = self._decrypt_connection_creds(conn)

        try:
            fetch_result = connector.fetch_records(
                config=conn.configuration,
                credentials=creds,
                sync_cursor=conn.sync_cursor,
                limit=batch_limit,
            )
        except PermissionError as e:
            return self._fail_sync(
                execution=execution,
                connection=conn,
                business=business,
                category=ErrorCategory.AUTHENTICATION_FAILURE,
                err_msg=str(e),
            )
        except TimeoutError as e:
            return self._fail_sync(
                execution=execution,
                connection=conn,
                business=business,
                category=ErrorCategory.TIMEOUT,
                err_msg=str(e),
            )
        except Exception as e:
            err_str = str(e)
            category = (
                ErrorCategory.RATE_LIMITED
                if "rate limit" in err_str.lower()
                else ErrorCategory.PROVIDER_UNAVAILABLE
            )
            return self._fail_sync(
                execution=execution,
                connection=conn,
                business=business,
                category=category,
                err_msg=err_str,
            )

        # 5. Normalize, validate, and persist transactional records
        discovered_count = len(fetch_result.records)
        imported_count = 0
        updated_count = 0
        skipped_count = 0
        dup_count = 0
        val_fail_count = 0

        # Create synthetic SalesUpload parent for data provenance
        sales_upload = SalesUpload(
            business_id=business.id,
            filename=f"sync:{conn.connector_id}:{exec_id[:8]}",
            file_format="connector",
            file_size_bytes=discovered_count * 128,
            row_count=discovered_count,
            status="confirmed",
        )
        self.db.add(sales_upload)
        self.db.flush()

        # Fetch existing fingerprints for deduplication (strictly scoped to this business)
        existing_fps = self.sales_repo.get_transaction_fingerprints(business.id)
        current_batch_fps: set[tuple[Any, ...]] = set()

        # Pre-fetch existing invoice transactions for in-place amendment handling
        existing_invoice_txs: dict[tuple[str, str], SalesTransaction] = {}
        for t in (
            self.db.query(SalesTransaction)
            .filter(
                SalesTransaction.business_id == business.id,
                SalesTransaction.invoice_id.isnot(None),
            )
            .all()
        ):
            if t.invoice_id and t.product_name:
                key = (t.invoice_id.strip().lower(), t.product_name.strip().lower())
                existing_invoice_txs[key] = t

        for raw_rec in fetch_result.records:
            try:
                norm_tx: NormalizedTransaction = connector.map_record(raw_rec)
            except Exception as e:
                logger.warning("Record normalization failed: %s", e)
                val_fail_count += 1
                skipped_count += 1
                continue

            # Deduplication fingerprint conforming to SalesRepository specification
            p_name = (norm_tx.product_name or "").strip().lower()
            q_val = round(float(norm_tx.quantity), 4)
            tot_val = round(float(norm_tx.total_amount), 2)
            if norm_tx.invoice_id:
                fp = ("inv", norm_tx.invoice_id.strip().lower(), p_name, q_val, tot_val)
            else:
                date_str = norm_tx.transaction_date.strftime("%Y-%m-%d")
                c_name = (norm_tx.customer_name or norm_tx.customer_id or "").strip().lower()
                fp = ("date", date_str, c_name, p_name, q_val, tot_val)

            # 1. Exact duplicate check (exact same fingerprint already in DB or current batch)
            is_duplicate = fp in existing_fps or fp in current_batch_fps
            if is_duplicate:
                dup_count += 1
                skipped_count += 1
                continue

            current_batch_fps.add(fp)

            # 2. In-place amendment check for legitimate upstream invoice corrections
            if norm_tx.invoice_id:
                inv_key = (norm_tx.invoice_id.strip().lower(), p_name)
                if inv_key in existing_invoice_txs:
                    existing_tx = existing_invoice_txs[inv_key]
                    existing_tx.quantity = norm_tx.quantity
                    existing_tx.unit_price = norm_tx.unit_price
                    existing_tx.total_amount = norm_tx.total_amount
                    existing_tx.transaction_date = norm_tx.transaction_date
                    if norm_tx.customer_name:
                        existing_tx.customer_name = norm_tx.customer_name
                    if norm_tx.customer_id:
                        existing_tx.customer_id = norm_tx.customer_id
                    existing_tx.upload_id = sales_upload.id
                    updated_count += 1
                    continue

            # 3. New transaction insertion
            tx_entity = SalesTransaction(
                upload_id=sales_upload.id,
                business_id=business.id,
                transaction_date=norm_tx.transaction_date,
                invoice_id=norm_tx.invoice_id,
                customer_id=norm_tx.customer_id,
                customer_name=norm_tx.customer_name,
                product_id=norm_tx.product_id,
                product_name=norm_tx.product_name,
                quantity=norm_tx.quantity,
                unit_price=norm_tx.unit_price,
                total_amount=norm_tx.total_amount,
                is_duplicate=False,
            )
            self.db.add(tx_entity)
            imported_count += 1
            if norm_tx.invoice_id:
                existing_invoice_txs[(norm_tx.invoice_id.strip().lower(), p_name)] = tx_entity

        total_active_records = imported_count + updated_count
        sales_upload.valid_row_count = total_active_records
        sales_upload.invalid_row_count = val_fail_count

        # 6. Update Provenance lineage
        if total_active_records > 0:
            self._register_provenance(
                business_id=business.id,
                connector=connector,
                imported_count=total_active_records,
                exec_id=exec_id,
            )

        # 7. Finalize sync execution
        final_status = (
            SyncExecutionStatus.SUCCEEDED.value
            if val_fail_count == 0
            else SyncExecutionStatus.PARTIAL.value
        )

        execution.status = final_status
        execution.records_discovered = discovered_count
        execution.records_imported = imported_count
        execution.records_skipped = skipped_count
        execution.duplicate_count = dup_count
        execution.validation_failure_count = val_fail_count
        execution.sync_cursor_after = fetch_result.next_cursor
        execution.completed_at = datetime.now(timezone.utc)
        execution.summary = {
            "has_more": fetch_result.has_more,
            "next_cursor": fetch_result.next_cursor,
            "records_updated": updated_count,
        }

        # Update connection metadata
        conn.last_sync_at = execution.completed_at
        conn.last_sync_status = execution.status
        conn.sync_cursor = fetch_result.next_cursor
        conn.last_error_category = None
        conn.last_error_message = None

        self._record_audit(
            business_id=business.id,
            connection_id=conn.id,
            connector_id=conn.connector_id,
            actor_user_id=user.id,
            event_type="sync_completed",
            details={
                "execution_id": execution.execution_id,
                "status": execution.status,
                "records_imported": imported_count,
                "records_updated": updated_count,
                "duplicate_count": dup_count,
                "validation_failure_count": val_fail_count,
            },
        )

        self.db.commit()
        self.db.refresh(execution)
        return SyncExecutionOut.model_validate(execution)

    def _fail_sync(
        self,
        execution: IntegrationSyncExecution,
        connection: IntegrationConnection,
        business: Business,
        category: ErrorCategory,
        err_msg: str,
    ) -> SyncExecutionOut:
        """Helper to safely record sync failure without exposing credentials."""
        safe_msg = self.vault.redact_secrets_from_dict(err_msg) if isinstance(err_msg, dict) else str(err_msg)
        execution.status = SyncExecutionStatus.FAILED.value
        execution.error_category = category.value
        execution.error_message = safe_msg
        execution.completed_at = datetime.now(timezone.utc)

        connection.last_sync_at = execution.completed_at
        connection.last_sync_status = SyncExecutionStatus.FAILED.value
        connection.last_error_category = category.value
        connection.last_error_message = safe_msg

        if category == ErrorCategory.AUTHENTICATION_FAILURE:
            connection.status = ConnectionStatus.REAUTH_REQUIRED.value

        self._record_audit(
            business_id=business.id,
            connection_id=connection.id,
            connector_id=connection.connector_id,
            actor_user_id=None,
            event_type="sync_failed",
            details={
                "execution_id": execution.execution_id,
                "error_category": category.value,
                "error_message": safe_msg,
            },
        )
        self.db.commit()
        self.db.refresh(execution)
        return SyncExecutionOut.model_validate(execution)

    # =========================================================================
    # 4. SYNC HISTORY & AUDIT LOGS
    # =========================================================================

    def get_sync_executions(
        self,
        business_id: int,
        connection_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SyncExecutionListResponse:
        """Fetch paginated synchronization execution records."""
        query = self.db.query(IntegrationSyncExecution).filter(
            IntegrationSyncExecution.business_id == business_id
        )
        if connection_id is not None:
            query = query.filter(IntegrationSyncExecution.connection_id == connection_id)

        total = query.count()
        items = (
            query.order_by(desc(IntegrationSyncExecution.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return SyncExecutionListResponse(
            items=[SyncExecutionOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_audits(
        self,
        business_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> IntegrationAuditListResponse:
        """Fetch paginated append-only integration audits."""
        query = self.db.query(IntegrationAudit).filter(IntegrationAudit.business_id == business_id)
        total = query.count()
        items = (
            query.order_by(desc(IntegrationAudit.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return IntegrationAuditListResponse(
            items=[IntegrationAuditOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _get_connector_or_400(self, connector_id: str) -> BaseDataConnector:
        try:
            return ConnectorRegistry.get(connector_id)
        except KeyError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    def _decrypt_connection_creds(self, conn: IntegrationConnection) -> dict[str, Any]:
        if not conn.encrypted_credentials:
            return {}
        return self.vault.decrypt_credentials(conn.business_id, conn.encrypted_credentials)

    def _to_connection_out(self, conn: IntegrationConnection) -> ConnectionOut:
        creds = self._decrypt_connection_creds(conn)
        masked = self.vault.mask_credentials(creds)
        return ConnectionOut(
            id=conn.id,
            business_id=conn.business_id,
            connector_id=conn.connector_id,
            name=conn.name,
            status=conn.status,
            configuration=conn.configuration,
            has_credentials=bool(conn.encrypted_credentials),
            masked_credentials=masked,
            credential_fingerprint=conn.credential_fingerprint,
            last_sync_at=conn.last_sync_at,
            last_sync_status=conn.last_sync_status,
            last_error_category=conn.last_error_category,
            last_error_message=conn.last_error_message,
            sync_cursor=conn.sync_cursor,
            is_enabled=conn.is_enabled,
            created_at=conn.created_at,
            updated_at=conn.updated_at,
        )

    def _record_audit(
        self,
        business_id: int,
        connection_id: int | None,
        connector_id: str | None,
        actor_user_id: int | None,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        clean_details = self.vault.redact_secrets_from_dict(details)
        audit = IntegrationAudit(
            business_id=business_id,
            connection_id=connection_id,
            connector_id=connector_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            details=clean_details,
        )
        self.db.add(audit)

    def _register_provenance(
        self,
        business_id: int,
        connector: BaseDataConnector,
        imported_count: int,
        exec_id: str,
    ) -> None:
        """Register verifiable provenance lineage for connector imported sales records.

        Note: 'data_quality_status = VERIFIED' signifies that imported transactional records
        have passed deterministic internal schema, type safety, and sanity validation checks
        during ingestion. It does not certify an independent third-party physical audit of the
        remote upstream system.
        """
        provenance = (
            self.db.query(BusinessDataProvenance)
            .filter(
                BusinessDataProvenance.business_id == business_id,
                BusinessDataProvenance.metric_name == "sales_transactions",
                BusinessDataProvenance.source_module == f"connector:{connector.connector_id}",
            )
            .first()
        )
        methodology = (
            f"Ingested and normalized via {connector.name} adapter with deduplication and in-place "
            "invoice amendment handling. 'VERIFIED' denotes internal deterministic schema, type safety, "
            "and sanity validation upon ingestion; it does not constitute an external audit of the "
            "third-party source."
        )
        if not provenance:
            provenance = BusinessDataProvenance(
                business_id=business_id,
                metric_name="sales_transactions",
                metric_value={"imported_records": imported_count, "sync_execution": exec_id},
                source_module=f"connector:{connector.connector_id}",
                source_record_ref=exec_id,
                measurement_period="continuous_sync",
                unit="transactions",
                currency="INR",
                calculation_methodology=methodology,
                data_quality_status="VERIFIED",
                nature="actual",
                freshness_status="FRESH",
                freshness_as_of=datetime.now(timezone.utc),
                confidence_score=100.0,
            )
            self.db.add(provenance)
        else:
            val = provenance.metric_value or {}
            val["imported_records"] = val.get("imported_records", 0) + imported_count
            val["last_sync_execution"] = exec_id
            provenance.metric_value = val
            provenance.calculation_methodology = methodology
            provenance.freshness_as_of = datetime.now(timezone.utc)
