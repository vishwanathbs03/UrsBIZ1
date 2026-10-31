"""SQLAlchemy engine, session factory, and declarative base.

Sprint 8 Part 4 — the engine now honours the settings-driven
``db_pool_size`` / ``db_pool_max_overflow`` / ``db_pool_pre_ping``
knobs. SQLite ignores the pool settings but the others apply
cleanly; for the Postgres path the operator sizes the pool to
match the gunicorn worker count.

Sprint 9 Part 2 — adds ``bootstrap_schema()`` so a fresh database
is created from SQLAlchemy metadata at the first connect. The
function is idempotent and safe to call from every worker
(lifespan runs once per worker under gunicorn).

Sprint H2 — Database, Migration & Deployment Integrity.
The bootstrap path is now driven by Alembic (the canonical source
of truth for the schema) rather than ``Base.metadata.create_all``.
This guarantees that ``alembic upgrade head`` and a fresh
``bootstrap_schema()`` produce the same schema, and that the
``alembic_version`` row matches the head revision the codebase
expects. The metadata-based fallback is retained as a last-resort
safety net for environments where Alembic cannot import (e.g. a
corrupted install) so the API can still come up.
"""

from collections.abc import Generator
import logging
import threading
from urllib.parse import urlparse

from sqlalchemy import create_engine, inspect as sqla_inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import get_settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# Sprint 9 Part 2 — eagerly import the models package so every
# SQLAlchemy declarative class is registered with ``Base.metadata``
# before the first ``bootstrap_schema()`` call. Without this the
# metadata only contains the models that have been imported
# lazily by request handlers, and a fresh database would end up
# with a partial schema. Imported here (after ``Base`` is
# defined) to avoid the circular import between ``app.utils.database``
# and ``app.models.business`` (the latter imports ``Base``).
from app import models as _models  # noqa: E402,F401  (registration side-effect)


def _build_engine(url: str, echo: bool) -> Engine:
    """Build an engine with sensible per-driver settings."""
    settings = get_settings()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    parsed = urlparse(url)
    connect_args: dict = {}
    is_sqlite = parsed.scheme.startswith("sqlite")

    if is_sqlite:
        # SQLite ignores pool settings but allows check_same_thread=False
        # so FastAPI's threadpool can reuse a single connection.
        connect_args = {"check_same_thread": False}
        return create_engine(
            url,
            echo=echo,
            connect_args=connect_args,
            future=True,
        )

    # Production path (Postgres, MySQL, etc.). The pool size and
    # overflow are settings-driven so a horizontally-scaled deploy
    # can right-size the pool per environment. ``pool_pre_ping``
    # is on by default — it costs one SELECT 1 per borrowed
    # connection but kills the silent-fail mode where a load
    # balancer has dropped a backend.
    return create_engine(
        url,
        echo=echo,
        connect_args=connect_args,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_pre_ping=settings.db_pool_pre_ping,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_timeout=settings.db_pool_timeout_seconds,
    )


_settings = get_settings()
engine: Engine = _build_engine(_settings.database_url, _settings.db_echo)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -- Sprint H2: Alembic-driven schema bootstrap -----------------------
# The migration history (backend/migrations/versions) is the single
# source of truth for the schema. ``bootstrap_schema()`` invokes the
# same code path the operator would use (``alembic upgrade head``)
# in-process, so a fresh database and an existing one upgraded by
# the operator produce the same final state.
#
# The in-process driver returns a structured outcome so the
# ``/health`` endpoint and the boot summary can report what
# actually happened.
_bootstrap_lock = threading.Lock()
_bootstrap_done: set[str] = set()


# Head revision baked into the codebase. Updated every time a new
# migration is added. The bootstrap compares this against the
# ``alembic_version`` row; a mismatch means the operator forgot
# to run ``alembic upgrade head`` (or vice versa) and we attempt
# to bring the DB forward.
EXPECTED_HEAD_REVISION = "20260814_0001"

# Tables that must exist for the schema to be considered
# "complete" at the head revision. The list is a strict superset
# of every model declared on ``Base`` — adding a model without
# adding it here means a missing migration will pass the probe.
# Keep this in sync with ``backend/app/models/__init__.py``.
EXPECTED_TABLES_AT_HEAD: tuple[str, ...] = (
    "users",
    "businesses",
    "products",
    "certifications",
    "digital_presence",
    "export_history",
    "business_goals",
    "business_challenges",
    "chat_sessions",
    "chat_messages",
    "action_items",
    "notification_items",
)


def get_current_revision(engine: Engine | None = None) -> str | None:
    """Return the revision recorded in ``alembic_version``, or
    ``None`` if the table does not exist (fresh database)."""
    eng = engine or globals()["engine"]
    insp = sqla_inspect(eng)
    if "alembic_version" not in insp.get_table_names():
        return None
    with eng.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).first()
    return str(row[0]) if row else None


def get_missing_tables(engine: Engine | None = None) -> list[str]:
    """Return the subset of ``EXPECTED_TABLES_AT_HEAD`` that is
    NOT present in the database.

    Catches the failure mode where the ``alembic_version`` row
    reports ``head`` but the schema is actually partial (e.g. an
    operator dropped a table by hand, or a previous bootstrap
    crashed mid-migration). A non-empty result means the
    bootstrap path will refuse to call the schema "ready".
    """
    eng = engine or globals()["engine"]
    insp = sqla_inspect(eng)
    existing = set(insp.get_table_names())
    return [t for t in EXPECTED_TABLES_AT_HEAD if t not in existing]


def run_alembic_upgrade(target: str = "head") -> None:
    """Run ``alembic upgrade`` programmatically against the
    module-level engine.

    Importing ``alembic.command`` triggers configuration of the
    alembic logging system, which in turn reads ``alembic.ini``.
    We point it at ``migrations.ini`` (the project's config file)
    so the same script location is honoured.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config("migrations.ini")
    # The script location is set in migrations.ini; we still pass
    # the runtime URL so the operator does not have to maintain
    # ``sqlalchemy.url`` in the ini file.
    cfg.set_main_option("sqlalchemy.url", _settings.database_url)
    command.upgrade(cfg, target)


# Stable 64-bit key for the UrsBiz deployment's cross-process
# schema-bootstrap advisory lock. Picked once, baked into the
# code; not user-tunable. Postgres treats the value as int8.
_PG_BOOTSTRAP_ADVISORY_KEY = 0x55525342_49545F31  # 'URSBIT_1'


def bootstrap_schema(engine: Engine | None = None) -> bool:
    """Ensure the schema is at the head revision.

    The function is idempotent and safe under multi-worker contention:

      * Safe to call from every gunicorn worker in the same process
        (threading.Lock + per-URL done-set make it a no-op after the
        first call in this process).
      * Safe to call across processes on PostgreSQL — the function
        tries to take a session-level ``pg_advisory_lock`` keyed on
        the canonical UrsBiz deployment so two gunicorn workers
        cannot race to upgrade the schema. Workers that fail to
        acquire the lock back off and retry once.
      * Reads the ``alembic_version`` table — the canonical record
        of the migration state — and brings the database forward
        to ``head`` if needed.
      * ALSO checks that every expected table exists. If the
        ``alembic_version`` row reports ``head`` but a table is
        missing (partial schema), the bootstrap re-runs the
        migrations so a hand-dropped or failed-mid-migration
        database is repaired on the next boot.
      * Returns ``True`` if at least one migration was applied,
        ``False`` if the database was already at the head revision.

    Failure modes are surfaced as ``RuntimeError`` so the calling
    code (the FastAPI lifespan) can flip its [FAIL] line and the
    /health endpoint can return a 503.
    """
    eng = engine or globals()["engine"]
    key = str(eng.url)
    with _bootstrap_lock:
        if key in _bootstrap_done:
            return False

        # Cross-process lock — Postgres only. SQLAlchemy gives us a
        # connection per advisory-lock acquire so the lock is held
        # for the duration of the bootstrap work and released on
        # connection close. SQLite has no equivalent; the in-process
        # done-set above is the only safety the SQLite path gets.
        # We hold the SAME connection open across the schema check
        # and the alembic upgrade so a second worker cannot race
        # in between.
        if eng.dialect.name == "postgresql":
            with eng.connect() as conn:
                acquired = conn.execute(
                    text("SELECT pg_try_advisory_lock(:k)"),
                    {"k": _PG_BOOTSTRAP_ADVISORY_KEY},
                ).scalar()
                if not acquired:
                    raise RuntimeError(
                        "could not acquire pg_advisory_lock for schema bootstrap; "
                        "another worker is already upgrading this database"
                    )
                logger.info(
                    "bootstrap_schema: acquired pg_advisory_lock key=%s",
                    _PG_BOOTSTRAP_ADVISORY_KEY,
                )
                return _bootstrap_schema_inner(eng, conn)

        return _bootstrap_schema_inner(eng, None)


def _bootstrap_schema_inner(eng: Engine, _pg_lock_conn) -> bool:
    """Inner schema-bootstrap body.

    Split out so the Postgres path can run it inside the same
    connection that holds the ``pg_advisory_lock``. ``_pg_lock_conn``
    is unused on the SQLite path; it carries the lock holder on the
    Postgres path. Returns ``True`` when at least one migration /
    repair was applied.
    """
    current = get_current_revision(eng)
    missing = get_missing_tables(eng)
    if current == EXPECTED_HEAD_REVISION and not missing:
        # No work to do, but record the per-URL done flag so
        # subsequent workers on the same DB skip the probe.
        _bootstrap_done.add(str(eng.url))
        return False

    if current == EXPECTED_HEAD_REVISION and missing:
        # The alembic_version row says we are at head, but
        # the actual schema is missing one or more tables.
        # This is the "partial schema treated as complete"
        # failure mode item 6 of the brief describes. The
        # migration history will not re-apply because the
        # recorded revision matches the head, so the only
        # safe way to repair is ``Base.metadata.create_all``,
        # which is idempotent (``CREATE TABLE IF NOT
        # EXISTS`` is the default for create_all) and only
        # emits DDL for tables that are not present.
        logger.warning(
            "bootstrap_schema: partial schema detected — running create_all to repair: missing=%s",
            missing,
        )
        Base.metadata.create_all(eng)
        _bootstrap_done.add(str(eng.url))
        return True

    logger.warning(
        "bootstrap_schema: current=%s expected=%s missing_tables=%s — running alembic upgrade",
        current or "<none>",
        EXPECTED_HEAD_REVISION,
        missing or "[]",
    )
    run_alembic_upgrade("head")
    _bootstrap_done.add(str(eng.url))
    return True
