"""Registro de eventos (PRD F-11). Detalhes passam pelo filtro de segredos antes de gravar."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from backuplc.core.db import Base, utcnow
from backuplc.core.logging import redact


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    actor: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


def record_event(
    session: Session,
    action: str,
    actor: str | None = None,
    detail: dict[str, Any] | None = None,
) -> Event:
    event = Event(action=action, actor=actor, detail=redact(detail or {}))
    session.add(event)
    return event
