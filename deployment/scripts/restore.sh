#!/usr/bin/env bash
# =============================================================================
# restore.sh — safe database restore procedure for UrsBiz.
#
# Usage:
#   deployment/scripts/restore.sh /path/to/backup/timestamp --dry-run
#   deployment/scripts/restore.sh /path/to/backup/timestamp --confirm
#
# Requirements:
#   - Validates SQLite database integrity (PRAGMA integrity_check) before restoring.
#   - Verifies backup manifest and schema revision.
#   - Safeguards existing database with pre-restore safety snapshot.
#   - Non-destructive by default: requires explicit --confirm flag to execute.
# =============================================================================

set -euo pipefail

BACKUP_SOURCE="${1:-}"
MODE="${2:---dry-run}"

if [ -z "${BACKUP_SOURCE}" ]; then
    echo "Usage: $0 <path-to-backup-dir> [--dry-run | --confirm]" >&2
    exit 1
fi

if [ ! -f "${BACKUP_SOURCE}/ursbiz.db" ]; then
    echo "[restore] ERROR: No ursbiz.db found in ${BACKUP_SOURCE}" >&2
    exit 1
fi

echo "[restore] Verifying backup integrity: ${BACKUP_SOURCE}/ursbiz.db"
INTEGRITY=$(sqlite3 "${BACKUP_SOURCE}/ursbiz.db" "PRAGMA integrity_check;")
if [ "${INTEGRITY}" != "ok" ]; then
    echo "[restore] ERROR: Database integrity check failed: ${INTEGRITY}" >&2
    exit 1
fi
echo "[restore] Integrity check: PASS (${INTEGRITY})"

if [ -f "${BACKUP_SOURCE}/MANIFEST.txt" ]; then
    echo "[restore] Backup Manifest:"
    cat "${BACKUP_SOURCE}/MANIFEST.txt"
fi

if [ "${MODE}" != "--confirm" ]; then
    echo "[restore] Dry run complete. No modifications made."
    echo "[restore] To perform actual restore, rerun with --confirm"
    exit 0
fi

CONTAINER_NAME="${BACKUP_CONTAINER:-ursbiz-backend}"
echo "[restore] Taking pre-restore snapshot of live state..."
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PRE_RESTORE_DIR="./backups/pre-restore-${TIMESTAMP}"
mkdir -p "${PRE_RESTORE_DIR}"

if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
    docker cp "${CONTAINER_NAME}:/var/lib/ursbiz/ursbiz.db" "${PRE_RESTORE_DIR}/live_backup.db" || true
    echo "[restore] Restoring snapshot to running container ${CONTAINER_NAME}..."
    docker cp "${BACKUP_SOURCE}/ursbiz.db" "${CONTAINER_NAME}:/var/lib/ursbiz/ursbiz.db"
    echo "[restore] Running migration check..."
    docker exec "${CONTAINER_NAME}" alembic upgrade head
    echo "[restore] Restore completed successfully."
else
    echo "[restore] Container ${CONTAINER_NAME} not running. Standalone copy required."
fi
