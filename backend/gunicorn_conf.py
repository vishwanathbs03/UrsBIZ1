"""Gunicorn production configuration.

This file is referenced by the production ``entrypoint.sh`` and is the only
place the worker count, timeout, and access-log format are tuned. It
contains zero application logic — it is a thin, environment-driven config
for the gunicorn process manager that fronts Uvicorn workers.

Gunicorn imports ``APP_MODULE`` (set to ``app.main:app`` by the Dockerfile)
and runs the FastAPI app via the ``uvicorn.workers.UvicornWorker`` worker
class. That class gives us gunicorn's process supervision (graceful
restarts, worker recycling) with uvicorn's HTTP/1.1 + WebSocket handling.

Sprint 8 Part 4 — the configuration is now the explicit
``preload_app`` toggle, ``graceful_timeout``, and a
``keepalive`` value that matches the load-balancer's idle
timeout. Everything else is a documented env override.
"""

from __future__ import annotations

import multiprocessing
import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


# --- Worker model --------------------------------------------------------- #

# 2 * CPU + 1 is the canonical gunicorn formula. For containerised
# workloads the right answer is "what the CPU limit allows", which we
# approximate with the host CPU count and let operators override.
cpu_count = multiprocessing.cpu_count()
workers = _env_int("GUNICORN_WORKERS", max(2, (cpu_count * 2) + 1))
threads = _env_int("GUNICORN_THREADS", 2)
worker_class = _env_str("GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")

# --- Network -------------------------------------------------------------- #

bind = _env_str("GUNICORN_BIND", f"{_env_str('APP_HOST', '0.0.0.0')}:{_env_str('APP_PORT', '8001')}")
keepalive = _env_int("GUNICORN_KEEPALIVE", 5)
timeout = _env_int("GUNICORN_TIMEOUT", 60)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)

# Allow large OCR uploads. The reverse proxy also enforces this, but we
# set it here so gunicorn does not truncate requests before they reach the
# app when the container is hit directly.
limit_request_line = 0
limit_request_fields = 0
limit_request_field_size = 0

# --- Logging -------------------------------------------------------------- #

accesslog = _env_str("GUNICORN_ACCESSLOG", "-")
errorlog = _env_str("GUNICORN_ERRORLOG", "-")
loglevel = _env_str("GUNICORN_LOGLEVEL", _env_str("LOG_LEVEL", "info")).lower()
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'
)
proc_name = _env_str("APP_NAME", "atlas-ai")

# --- Worker lifecycle ----------------------------------------------------- #

# Recycle workers periodically to bound memory growth and pick up
# configuration changes that the master process already loaded.
# ``preload_app`` is OFF by default — forking a pre-loaded app
# means every worker shares the parent's memory until a write
# happens (copy-on-write), which is great for memory but
# trippers some third-party libraries that open a file at
# import time. The production overlay can opt in.
max_requests = _env_int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)
preload_app = _env_str("GUNICORN_PRELOAD_APP", "false").lower() == "true"

# --- Server mechanics ----------------------------------------------------- #

# Send SIGTERM to workers, wait up to graceful_timeout, then SIGKILL.
# This matches the behaviour `docker stop` expects so a rolling
# redeploy does not lose in-flight requests.
worker_tmpdir = "/dev/shm"
