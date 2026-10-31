#!/usr/bin/env sh
# =============================================================================
# Backend production entrypoint.
#
# Responsibilities:
#   1. Sanity-check the runtime environment.
#   2. Surface the resolved settings so a `docker logs` reveals what the
#      container is actually configured with (without leaking secrets).
#   3. Pre-import the app module to surface config errors before gunicorn
#      forks workers (so a typo in the env fails fast instead of
#      producing a worker crashloop).
#   4. Hand off to gunicorn, which is the only process the image runs.
#
# The app's lifespan calls ``bootstrap_schema()`` (see
# ``app/utils/database.py``) on first connect, which creates the
# schema from SQLAlchemy metadata when it is missing. Operators
# who want to manage schema changes explicitly can run Alembic
# migrations against ``$DATABASE_URL`` before this container
# starts and the bootstrap will detect the existing schema and
# skip the step.
# =============================================================================

set -eu

log() {
    printf '[entrypoint] %s\n' "$*" >&2
}

# Default values match the Dockerfile ENV block. Operators override
# these in the compose file or the env_file.
APP_MODULE="${APP_MODULE:-app.main:app}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-60}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8001}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

log "starting UrsBiz backend"
log "  app_module=${APP_MODULE}"
log "  workers=${GUNICORN_WORKERS} threads=${GUNICORN_THREADS} timeout=${GUNICORN_TIMEOUT}s"
log "  bind=${APP_HOST}:${APP_PORT}"
log "  log_level=${LOG_LEVEL}"

# Make sure the writable volumes are present. compose creates them,
# but `docker run --rm` without a volume mount would otherwise fail
# at the first SQLAlchemy connect.
mkdir -p /var/log/ursbiz /var/lib/ursbiz

# Pre-import the app so config / migration errors surface BEFORE
# gunicorn forks workers. APP_MODULE is "package.module:attr" so
# we split on the colon and import the package side only.
APP_PKG=$(printf '%s' "${APP_MODULE}" | cut -d: -f1)
log "preloading module ${APP_PKG} to validate configuration"
python -c "import ${APP_PKG}" || {
    log "FATAL: cannot import ${APP_PKG}"
    exit 1
}

# Exec gunicorn with the production config. exec replaces the shell
# so gunicorn becomes the long-running process under tini and
# receives signals directly.
exec gunicorn \
    --config gunicorn_conf.py \
    --workers "${GUNICORN_WORKERS}" \
    --threads "${GUNICORN_THREADS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --bind "${APP_HOST}:${APP_PORT}" \
    --log-level "${LOG_LEVEL}" \
    "${APP_MODULE}"
