"""Configurações persistentes em banco (Spec E2.3)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backuplc.core.db import Base, Database, utcnow

DEFAULT_CRON = "0 2 * * *"


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def get_schedule_cron(db: Database) -> str:
    """Retorna o cron do banco ou o padrão se não configurado (ou tabela ausente)."""
    from sqlalchemy.exc import OperationalError

    try:
        with db.session() as s:
            row = s.get(AppSetting, "schedule_cron")
            return row.value if row is not None else DEFAULT_CRON
    except OperationalError:
        return DEFAULT_CRON


def set_schedule_cron(db: Database, cron: str) -> None:
    """Persiste o cron no banco (insert or update)."""
    with db.session() as s:
        row = s.get(AppSetting, "schedule_cron")
        if row is None:
            s.add(AppSetting(key="schedule_cron", value=cron, updated_at=utcnow()))
        else:
            row.value = cron
            row.updated_at = utcnow()
