"""Credenciais SSH e switches (E2).

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "credentials",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("encrypted_password", sa.String(512), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_credentials"),
        sa.UniqueConstraint("name", name="uq_credentials_name"),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("ssh_port", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(36), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credentials.id"],
            ondelete="RESTRICT",
            name="fk_devices_credential_id_credentials",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_devices"),
        sa.UniqueConstraint("name", name="uq_devices_name"),
        sa.UniqueConstraint("ip_address", name="uq_devices_ip_address"),
    )


def downgrade() -> None:
    op.drop_table("devices")
    op.drop_table("credentials")
