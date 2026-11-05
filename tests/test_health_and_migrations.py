"""E1-01 (health) e E1-03 (migração reversível)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database
from backuplc.core.migrate import current_revision, downgrade, head_revision, upgrade
from backuplc.web.app import create_app

pytestmark = pytest.mark.integration


def _schema(db: Database) -> dict[str, list[tuple[str, str]]]:
    insp = inspect(db.engine)
    return {
        table: sorted((c["name"], str(c["type"])) for c in insp.get_columns(table))
        for table in sorted(insp.get_table_names())
    }


def test_live(client: TestClient) -> None:
    resposta = client.get("/health/live")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


def test_ready_ok(client: TestClient) -> None:
    resposta = client.get("/health/ready")
    assert resposta.status_code == 200
    assert resposta.json()["checks"] == {"database": True, "schema": True, "storage": True}


def test_ready_falha_sem_migracao(settings: Settings, secrets: AppSecrets, db: Database) -> None:
    with TestClient(create_app(settings, secrets, db)) as client:
        resposta = client.get("/health/ready")
    assert resposta.status_code == 503
    assert resposta.json()["checks"]["schema"] is False


def test_migracao_ida_e_volta(db: Database) -> None:
    upgrade(db)
    assert current_revision(db) == head_revision()
    esperado = _schema(db)
    assert "events" in esperado

    downgrade(db, "base")
    assert current_revision(db) is None
    assert set(_schema(db)) <= {"alembic_version"}

    upgrade(db)
    assert _schema(db) == esperado


def test_banco_em_modo_wal(db: Database) -> None:
    upgrade(db)
    with db.engine.connect() as conn:
        modo = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        fks = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert modo == "wal"
    assert fks == 1
