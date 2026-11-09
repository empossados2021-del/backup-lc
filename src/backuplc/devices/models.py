"""Modelos de credencial SSH e switch (Spec E2)."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backuplc.core.db import Base

DeviceType = Literal["generic", "mikrotik_routeros"]


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    # Fernet-encrypted password (ADR-006); nunca em texto puro.
    encrypted_password: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    ssh_port: Mapped[int] = mapped_column(Integer, nullable=False, default=22)
    credential_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("credentials.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True)
