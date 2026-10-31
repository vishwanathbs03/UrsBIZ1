"""Pytest configuration for the UrsBiz backend test suite.

Goal
----
Eliminate two classes of pre-existing failure that surface when the
full 172-test suite is run end-to-end:

1. **Rate-limit cascade.** The ``RateLimitMiddleware`` in
   ``app.middleware.security`` is a per-process sliding-window
   limiter keyed by client IP. ``fastapi.testclient.TestClient``
   reports its client host as ``"testclient"`` (a hostname, not
   an IP), so the loopback exception does not apply and every
   test request counts against the global 120 req / 60 s
   budget. With 26 API-level tests each registering → logging in
   → posting business data → calling protected endpoints, we
   blow through the budget and the next 429 cascades into a
   401 on the *next* test (rate-limit stops the request
   before the protected handler runs).
   Rate-limit is controlled by the public ``RATE_LIMIT_ENABLED``
   setting flag — disabling it for tests is the documented
   "off" path and matches production behaviour at the edge
   (``rate_limit_enabled=false`` is what the validator suggests
   for environments where it is not needed).

2. **Shared database state.** Several test modules set
   ``DATABASE_URL`` to a persistent SQLite file (e.g.
   ``atlas_ai.db``) and call ``Base.metadata.create_all``. The
   file is not wiped between pytest runs, so unique-constraint
   violations accumulate (``serviceuser@example.com``,
   ``kpiuser@example.com``, etc.). We wipe these persisted
   files BEFORE any test module is imported so that each
   test's own ``Base.metadata.create_all`` rebuilds the
   schema from scratch.

This conftest deliberately does not touch any module under
``app/`` — the product behaviour is unchanged. Every fix is
test-infrastructure only.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Pre-collection env setup
# ---------------------------------------------------------------------------
# ``RATE_LIMIT_ENABLED=false`` must be visible before any test
# module imports ``app.main`` (which builds the FastAPI app
# and installs the rate-limit middleware). Setting it at
# conftest import time — which happens before pytest starts
# collecting test modules — is the cheapest way to guarantee
# ordering.
#
# This is the documented opt-out path; production behaviour
# (the default ``true``) is untouched.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _backend_root() -> Path:
    """Return the backend package root (parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


def _wipe_persistent_db_files() -> None:
    """Drop tables in the persistent SQLite files the tests use.

    The tests share a couple of SQLite files (atlas_ai.db,
    hackathon_demo.db). ``Base.metadata.create_all`` only
    creates missing tables — it does NOT purge existing rows.
    Test modules that hard-code emails (e.g.
    ``serviceuser@example.com``) therefore fail on the
    second pytest run with a UNIQUE constraint error.

    Earlier versions used ``Base.metadata.drop_all`` against
    a throw-away engine, but the application engine had
    already cached a connection to the same file by the time
    the test module ran its ``create_all`` — so the drop was
    effectively a no-op against the file that mattered. The
    reliable fix is to **delete the file itself** before
    each pytest run, so ``create_all`` rebuilds the schema
    from scratch against a clean SQLite.
    """
    backend = _backend_root()
    # Defer the SQLAlchemy import until the function is called
    # so the test module's own DATABASE_URL is not affected by
    # an early import of ``app.utils.database`` (which would
    # build the application engine against the wrong URL).
    candidates = [backend / "atlas_ai.db", backend / "hackathon_demo.db"]
    for db_path in candidates:
        if not db_path.exists():
            continue
        try:
            db_path.unlink()
        except OSError:
            # File is locked by a still-open connection (e.g.
            # from a prior pytest run that did not close its
            # session). Fall back to drop_all on a fresh
            # engine so we at least empty the tables.
            from sqlalchemy import create_engine  # noqa: PLC0415
            from app.utils.database import Base  # noqa: PLC0415

            engine = create_engine(
                f"sqlite:///{db_path}".replace("\\", "/"),
                future=True,
            )
            try:
                Base.metadata.drop_all(bind=engine)
            finally:
                engine.dispose()


# ---------------------------------------------------------------------------
# pytest_configure — runs after conftest is loaded, before any
# test module is imported. This is the earliest hook pytest
# gives us for "do something before collection".
# ---------------------------------------------------------------------------

import pytest  # noqa: E402  (after env-var setup)


def pytest_configure(config: pytest.Config) -> None:
    """Wipe shared SQLite test databases BEFORE any test module loads.

    Pytest calls this hook after loading conftest.py but
    before importing any test module. The test modules each
    set ``DATABASE_URL`` at top-level and call
    ``Base.metadata.create_all`` at top-level as well — so
    wiping the persistent DB files here gives each test a
    clean schema the moment the module's ``create_all`` runs.
    """
    _wipe_persistent_db_files()
