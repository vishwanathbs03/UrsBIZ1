"""add users.active_business_id (Sprint 23 multi-business)

Revision ID: 20260814_0001
Revises: 20260101_0007
Create Date: 2026-08-14 00:00:00

Sprint 23 - Profile Panel + Multi-Business Support.

Until now the User <-> Business relationship was capped at 1:1
in Python (``BusinessRepository.create`` raised
``BusinessAlreadyExists``; the DB layer's
``Business.owner_id`` is a plain indexed ``ForeignKey`` with
no ``unique=True``). Sprint 23 lifts the Python-side cap so a
single user can own many businesses, and adds
``User.active_business_id`` so the rest of the app (dashboard,
assistant, analytics, ...) can resolve "which business is the
user currently working against?" without a join on every
request.

Schema change
-------------

* New nullable column ``users.active_business_id`` -
  ``ForeignKey("businesses.id", ondelete="SET NULL")``.
  ``SET NULL`` is the right cascade for this relationship:
  deleting a business must not cascade-kill the user, but
  it must also not leave the user pointing at a stale row.

SQLite caveat
-------------

SQLite does not support ``ALTER TABLE ... ADD COLUMN`` when
the new column carries a ``ForeignKeyConstraint`` (it raises
``NotImplementedError: No support for ALTER of constraints
in SQLite dialect``). The standard workaround is Alembic's
batch mode, which copies the table to a temp, drops the
original, and recreates it with the new constraint. We branch
on the dialect so Postgres (production) keeps the simple
``add_column`` path.

Backfill
--------

For every user that already owns exactly one business row,
``active_business_id`` is set to that row's ``id``. Users
with zero or multiple businesses get ``NULL``; the service
layer's fallback ("most recently created business") covers
those cases on the read path.

The migration is idempotent on a fresh database (the column
is nullable, the backfill is a single conditional UPDATE)
and reversible by ``op.drop_column`` + the matching
post-downgrade UPDATE that nulls the column.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260814_0001"
down_revision: Union[str, None] = "20260101_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_active_business_id_column() -> None:
    """Add ``users.active_business_id`` in a dialect-appropriate way.

    SQLite has to go through batch mode; Postgres can do it in
    place. Anything else falls back to the batch path too.

    The FK constraint is given an explicit name so Alembic's
    SQLite batch mode (which copies the table to a temp and
    recreates it) can attach the constraint on the new table.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column(
            "users",
            sa.Column(
                "active_business_id",
                sa.Integer(),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_users_active_business_id_businesses",
            "users",
            "businesses",
            ["active_business_id"],
            ["id"],
            ondelete="SET NULL",
        )
        return

    # SQLite (and any other dialect without ALTER-of-constraints)
    # uses batch mode. The ``recreate="always"`` setting makes
    # Alembic copy the table to ``_users_new`` and rename it back,
    # carrying every existing column + the new FK column through.
    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "active_business_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_users_active_business_id_businesses",
            "businesses",
            ["active_business_id"],
            ["id"],
            ondelete="SET NULL",
        )


def upgrade() -> None:
    _add_active_business_id_column()

    # Backfill: a user that owns exactly one business gets that
    # business promoted to "active". Owners of zero or multiple
    # businesses are left at NULL - the service layer resolves
    # those on demand.
    #
    # The subquery filters users whose business count is exactly
    # one, then matches that count to the user's only business id.
    # SQLAlchemy renders this as a correlated scalar subquery.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE users
               SET active_business_id = (
                   SELECT id FROM businesses
                    WHERE businesses.owner_id = users.id
                    ORDER BY businesses.created_at DESC, businesses.id DESC
                    LIMIT 1
               )
             WHERE (
                 SELECT COUNT(*) FROM businesses
                  WHERE businesses.owner_id = users.id
               ) = 1
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_column("users", "active_business_id")
        return

    with op.batch_alter_table("users", recreate="always") as batch_op:
        batch_op.drop_column("active_business_id")
