"""create integration device tables (Wave 1 Financial Intelligence)

Revision ID: 20261115_0004
Revises: 20261115_0003
Create Date: 2026-11-15 13:00:00

Creates:
  - integration_devices: Registered edge/desktop sync devices (Tally/ERP sync agents).
  - integration_device_nonces: Replay-prevention nonces for signed edge integration requests.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20261115_0004"
down_revision: Union[str, None] = "20261115_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create integration_devices table
    op.create_table(
        "integration_devices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "business_id",
            sa.Integer(),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("device_uuid", sa.String(36), nullable=False),
        sa.Column("public_key_hex", sa.String(64), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("device_uuid", name="uq_integration_devices_uuid"),
    )
    op.create_index("ix_integration_devices_business_id", "integration_devices", ["business_id"], unique=False)
    op.create_index("ix_integration_devices_device_uuid", "integration_devices", ["device_uuid"], unique=True)
    op.create_index("ix_integration_devices_status", "integration_devices", ["status"], unique=False)

    # 2. Create integration_device_nonces table
    op.create_table(
        "integration_device_nonces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "device_uuid",
            sa.String(36),
            sa.ForeignKey("integration_devices.device_uuid", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("device_uuid", "nonce", name="uq_device_nonce"),
    )
    op.create_index("ix_integration_device_nonces_device_uuid", "integration_device_nonces", ["device_uuid"], unique=False)
    op.create_index("ix_integration_device_nonces_nonce", "integration_device_nonces", ["nonce"], unique=False)
    op.create_index("ix_integration_device_nonces_received_at", "integration_device_nonces", ["received_at"], unique=False)


def downgrade() -> None:
    op.drop_table("integration_device_nonces")
    op.drop_table("integration_devices")
