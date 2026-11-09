"""Spec E7.2 — Restore: consulta e download por data."""

from __future__ import annotations

from datetime import datetime

import pytest

from backuplc.collector.service import list_versions_by_date
from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.devices.service import create_credential, create_device
from backuplc.storage.models import ConfigVersion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_device(db: Database, secrets: object, suffix: str = "01") -> str:
    from backuplc.core.config import AppSecrets

    assert isinstance(secrets, AppSecrets)
    cred = create_credential(
        db, secrets.master_key, f"cred-r{suffix}", "user", "SenhaSegura123!", ""
    )
    device = create_device(db, f"sw-r{suffix}", f"10.1.0.{suffix}", "generic", 22, cred.id, True)
    return device.id


def _add_version(db: Database, device_id: str, collected_at: datetime) -> str:
    sha = "abc123def456abcd" * 4
    with db.session() as s:
        v = ConfigVersion(
            device_id=device_id,
            collected_at=collected_at,
            sha256_raw=sha,
            sha256_norm=sha,
            size_bytes=1024,
            file_path=f"configs/{device_id}/{collected_at.strftime('%Y%m%d%H%M%S')}.txt",
        )
        s.add(v)
    with db.session() as s:
        return (
            s.query(ConfigVersion)
            .filter_by(device_id=device_id)
            .order_by(ConfigVersion.collected_at.desc())
            .first()
            .id
        )


# ---------------------------------------------------------------------------
# Testes unitários: list_versions_by_date
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_list_versions_by_date_com_backup(db: Database, secrets: object) -> None:
    """Data com backup → retorna versão."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    dt = datetime(2026, 11, 6, 18, 0, 0)
    _add_version(db, device_id, dt)

    versions = list_versions_by_date(db, device_id, "2026-11-06")
    assert len(versions) == 1
    assert versions[0].device_id == device_id


@pytest.mark.unit
def test_list_versions_by_date_sem_backup(db: Database, secrets: object) -> None:
    """Data sem backup → lista vazia."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    _add_version(db, device_id, datetime(2026, 11, 5, 18, 0, 0))

    versions = list_versions_by_date(db, device_id, "2026-11-06")
    assert versions == []


@pytest.mark.unit
def test_list_versions_by_date_multiplas_versoes(db: Database, secrets: object) -> None:
    """Múltiplas coletas no mesmo dia → todas retornadas, ordenadas DESC."""
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="02")
    _add_version(db, device_id, datetime(2026, 11, 6, 8, 0, 0))
    _add_version(db, device_id, datetime(2026, 11, 6, 18, 0, 0))

    versions = list_versions_by_date(db, device_id, "2026-11-06")
    assert len(versions) == 2
    assert versions[0].collected_at > versions[1].collected_at


@pytest.mark.unit
def test_list_versions_by_date_data_invalida(db: Database, secrets: object) -> None:
    """Data com formato inválido → lista vazia (sem erro)."""
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="03")
    versions = list_versions_by_date(db, device_id, "nao-e-data")
    assert versions == []


# ---------------------------------------------------------------------------
# Testes de integração: rotas
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_restore_get_sem_data(admin_client: object, db: Database, secrets: object) -> None:
    """GET /devices/{id}/restore sem parâmetro → 200, campo de data visível."""
    from fastapi.testclient import TestClient

    assert isinstance(admin_client, TestClient)
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="10")

    r = admin_client.get(f"/devices/{device_id}/restore")
    assert r.status_code == 200
    assert 'type="date"' in r.text
    assert "Verificar" in r.text


@pytest.mark.integration
def test_restore_sem_autenticacao(client: object, db: Database, secrets: object) -> None:
    """GET /devices/{id}/restore sem sessão → redirect /login."""
    from fastapi.testclient import TestClient

    assert isinstance(client, TestClient)
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="11")

    r = client.get(f"/devices/{device_id}/restore")
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


@pytest.mark.integration
def test_restore_com_backup(
    admin_client: object,
    db: Database,
    secrets: object,
    settings: object,
) -> None:
    """Data com backup → botão Baixar aparece no HTML."""
    from fastapi.testclient import TestClient

    from backuplc.core.config import Settings

    assert isinstance(admin_client, TestClient)
    assert isinstance(settings, Settings)
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="12")
    version_id = _add_version(db, device_id, datetime(2026, 11, 6, 18, 0, 0))

    # Cria arquivo físico para o download não falhar na rota de download
    import pathlib

    data_dir = pathlib.Path(str(settings.data_dir))
    ver_path = data_dir / f"configs/{device_id}/20261106180000.txt"
    ver_path.parent.mkdir(parents=True, exist_ok=True)
    ver_path.write_text("config content")

    r = admin_client.get(f"/devices/{device_id}/restore?date=2026-11-06")
    assert r.status_code == 200
    assert "Baixar" in r.text
    assert version_id in r.text


@pytest.mark.integration
def test_restore_sem_backup(
    admin_client: object,
    db: Database,
    secrets: object,
) -> None:
    """Data sem backup → mensagem 'Nenhum backup encontrado'."""
    from fastapi.testclient import TestClient

    assert isinstance(admin_client, TestClient)
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="13")

    r = admin_client.get(f"/devices/{device_id}/restore?date=2026-11-06")
    assert r.status_code == 200
    assert "Nenhum backup encontrado" in r.text


@pytest.mark.integration
def test_restore_reader(
    reader_client: object,
    db: Database,
    secrets: object,
) -> None:
    """Reader pode acessar a página de restore."""
    from fastapi.testclient import TestClient

    assert isinstance(reader_client, TestClient)
    upgrade(db)
    device_id = _make_device(db, secrets, suffix="14")

    r = reader_client.get(f"/devices/{device_id}/restore")
    assert r.status_code == 200
