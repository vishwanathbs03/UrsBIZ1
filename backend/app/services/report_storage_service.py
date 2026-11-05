"""Secure Storage Service for Reports & Evidence Export Centre (Phase 6.25).

Provides tenant-isolated, safe filesystem storage with path traversal protection,
SHA-256 integrity verification, and safe filename generation.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


class StorageSecurityError(Exception):
    """Raised when an unauthorized path traversal or storage violation occurs."""
    pass


class ReportNotFoundError(Exception):
    """Raised when a requested report file does not exist on disk."""
    pass


class ReportStorageService:
    """Manages report export files on local filesystem with strict tenant isolation."""

    MIME_TYPES: dict[str, str] = {
        "pdf": "application/pdf",
        "csv": "text/csv; charset=utf-8",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def __init__(self, base_dir: str | None = None) -> None:
        if base_dir is None:
            base_dir = os.getenv("REPORTS_STORAGE_DIR", os.path.join("backend", "storage", "reports"))
        self._base_path = Path(base_dir).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    @property
    def base_path(self) -> Path:
        return self._base_path

    def _sanitize_component(self, name: str) -> str:
        """Sanitize a path component ensuring only safe characters."""
        clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)
        clean = clean.strip("._")
        if not clean:
            return "report"
        return clean

    def _resolve_tenant_path(self, business_id: int, filename: str) -> Path:
        """Resolve and validate a tenant path, guarding against path traversal."""
        if business_id <= 0:
            raise StorageSecurityError(f"Invalid business ID: {business_id}")

        safe_filename = self._sanitize_component(filename)
        tenant_dir = (self._base_path / str(business_id)).resolve()

        # Ensure tenant dir is inside base path
        if not str(tenant_dir).startswith(str(self._base_path)):
            raise StorageSecurityError("Tenant directory path traversal attempt detected.")

        target_file = (tenant_dir / safe_filename).resolve()

        # Ensure target file is inside tenant dir
        if not str(target_file).startswith(str(tenant_dir)):
            raise StorageSecurityError("File path traversal attempt detected.")

        return target_file

    def save_report_file(
        self,
        business_id: int,
        report_id: str,
        file_format: str,
        content: bytes,
    ) -> tuple[str, int, str]:
        """Save a report binary to tenant directory.

        Returns:
            tuple[relative_file_path, file_size_bytes, sha256_checksum]
        """
        fmt = file_format.lower().strip(".")
        filename = f"{self._sanitize_component(report_id)}.{fmt}"
        target_path = self._resolve_tenant_path(business_id, filename)

        # Create tenant directory if missing
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Compute SHA-256
        sha256 = hashlib.sha256(content).hexdigest()

        # Write file
        target_path.write_bytes(content)
        file_size = len(content)

        # Relative path from base storage
        rel_path = str(target_path.relative_to(self._base_path)).replace("\\", "/")
        return rel_path, file_size, sha256

    def read_report_file(self, business_id: int, relative_path: str) -> bytes:
        """Read report file binary enforcing strict tenant isolation."""
        # Clean relative path
        norm_rel = os.path.normpath(relative_path).replace("\\", "/")
        if norm_rel.startswith("../") or "/../" in norm_rel or norm_rel.startswith("/"):
            raise StorageSecurityError("Path traversal pattern detected in relative path.")

        parts = norm_rel.split("/")
        if len(parts) < 2 or str(business_id) != parts[0]:
            raise StorageSecurityError(f"Tenant isolation mismatch: Path {relative_path} does not belong to business {business_id}.")

        filename = parts[-1]
        target_path = self._resolve_tenant_path(business_id, filename)

        if not target_path.exists() or not target_path.is_file():
            raise ReportNotFoundError(f"Report file {filename} not found on disk.")

        return target_path.read_bytes()

    def delete_report_file(self, business_id: int, relative_path: str) -> bool:
        """Safely delete a report file from storage."""
        try:
            parts = os.path.normpath(relative_path).replace("\\", "/").split("/")
            if len(parts) >= 2 and str(business_id) == parts[0]:
                target_path = self._resolve_tenant_path(business_id, parts[-1])
                if target_path.exists() and target_path.is_file():
                    target_path.unlink()
                    return True
        except Exception:
            pass
        return False

    def get_mime_type(self, file_format: str) -> str:
        """Get standard MIME type for format."""
        return self.MIME_TYPES.get(file_format.lower().strip("."), "application/octet-stream")
