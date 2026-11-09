"""Coleta de configuração (E3).

Revision ID: 0004
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "config_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256_raw", sa.String(64), nullable=False),
        sa.Column("sha256_norm", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            ondelete="RESTRICT",
            name="fk_config_versions_device_id_devices",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_config_versions"),
    )
    op.create_table(
        "device_host_keys",
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("key_type", sa.String(50), nullable=False),
        sa.Column("key_b64", sa.Text(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            ondelete="CASCADE",
            name="fk_device_host_keys_device_id_devices",
        ),
        sa.PrimaryKeyConstraint("device_id", name="pk_device_host_keys"),
    )
    op.create_table(
        "executions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("trigger", sa.String(10), nullable=False),
        sa.Column("triggered_by", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
            ondelete="RESTRICT",
            name="fk_executions_device_id_devices",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["config_versions.id"],
            ondelete="SET NULL",
            name="fk_executions_version_id_config_versions",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_executions_triggered_by_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_executions"),
    )


def downgrade() -> None:
    op.drop_table("executions")
    op.drop_table("device_host_keys")
    op.drop_table("config_versions")
