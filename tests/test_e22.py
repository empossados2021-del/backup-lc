"""Testes E2.2 — Tipos de dispositivo (generic e mikrotik_routeros)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backuplc.core.config import AppSecrets
from backuplc.core.db import Database

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_csrf(client: TestClient, secrets: AppSecrets) -> str:
    from backuplc.auth.service import make_csrf_token

    sid = client.cookies.get("session_id", "")
    return make_csrf_token(sid, secrets.session_secret)


def _make_devices(db: Database, secrets: AppSecrets) -> tuple[str, str, str]:
    """Cria credencial, um dispositivo generic e um mikrotik. Retorna (cred_id, generic_id, mikrotik_id)."""
    from backuplc.devices.service import create_credential, create_device

    cred = create_credential(db, secrets.master_key, "cred-e22", "admin", "Senha1234!X", "")
    generic = create_device(db, "sw-generic", "10.1.1.1", "generic", 22, cred.id, True)
    mikrotik = create_device(db, "mk-router", "10.2.2.2", "mikrotik_routeros", 22, cred.id, True)
    return cred.id, generic.id, mikrotik.id


# ---------------------------------------------------------------------------
# Testes unitários de list_devices com filtro de tipo
# ---------------------------------------------------------------------------


def test_list_devices_filter_generic(db: Database, secrets: AppSecrets) -> None:
    from backuplc.core.migrate import upgrade
    from backuplc.devices.service import list_devices

    upgrade(db)
    _make_devices(db, secrets)
    devices = list_devices(db, device_type="generic")
    assert all(d.device_type == "generic" for d in devices)
    names = [d.name for d in devices]
    assert "sw-generic" in names
    assert "mk-router" not in names


def test_list_devices_filter_mikrotik(db: Database, secrets: AppSecrets) -> None:
    from backuplc.core.migrate import upgrade
    from backuplc.devices.service import list_devices

    upgrade(db)
    _make_devices(db, secrets)
    devices = list_devices(db, device_type="mikrotik_routeros")
    assert all(d.device_type == "mikrotik_routeros" for d in devices)
    names = [d.name for d in devices]
    assert "mk-router" in names
    assert "sw-generic" not in names


def test_list_devices_no_filter_returns_all(db: Database, secrets: AppSecrets) -> None:
    from backuplc.core.migrate import upgrade
    from backuplc.devices.service import list_devices

    upgrade(db)
    _make_devices(db, secrets)
    devices = list_devices(db)
    names = [d.name for d in devices]
    assert "sw-generic" in names
    assert "mk-router" in names


# ---------------------------------------------------------------------------
# Testes de integração — /devices mostra apenas generic
# ---------------------------------------------------------------------------


def test_devices_list_shows_only_generic(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    _make_devices(db, secrets)
    resp = admin_client.get("/devices")
    assert resp.status_code == 200
    assert "sw-generic" in resp.text
    assert "mk-router" not in resp.text


def test_devices_list_does_not_show_mikrotik(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    _make_devices(db, secrets)
    resp = admin_client.get("/devices")
    assert resp.status_code == 200
    assert "mikrotik_routeros" not in resp.text


# ---------------------------------------------------------------------------
# Testes de integração — /mikrotik mostra apenas mikrotik
# ---------------------------------------------------------------------------


def test_mikrotik_list_shows_only_mikrotik(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    _make_devices(db, secrets)
    resp = admin_client.get("/mikrotik")
    assert resp.status_code == 200
    assert "mk-router" in resp.text
    assert "sw-generic" not in resp.text


def test_mikrotik_list_page_title(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    _make_devices(db, secrets)
    resp = admin_client.get("/mikrotik")
    assert resp.status_code == 200
    assert "MikroTik" in resp.text


def test_mikrotik_list_requires_auth(client: TestClient) -> None:
    resp = client.get("/mikrotik")
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Testes de integração — formulário salva o tipo correto
# ---------------------------------------------------------------------------


def test_create_device_mikrotik_type(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    from backuplc.devices.service import create_credential, list_devices

    cred = create_credential(db, secrets.master_key, "cred-form", "admin", "Senha5678!X", "")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        "/devices/new",
        data={
            "csrf_token": csrf,
            "name": "mk-form-test",
            "ip_address": "10.3.3.3",
            "device_type": "mikrotik_routeros",
            "ssh_port": "22",
            "credential_id": cred.id,
            "is_active": "1",
        },
    )
    assert resp.status_code == 303
    devices = list_devices(db, device_type="mikrotik_routeros")
    names = [d.name for d in devices]
    assert "mk-form-test" in names


def test_create_device_generic_type(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    from backuplc.devices.service import create_credential, list_devices

    cred = create_credential(db, secrets.master_key, "cred-form2", "admin", "Senha5678!X", "")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        "/devices/new",
        data={
            "csrf_token": csrf,
            "name": "sw-form-test",
            "ip_address": "10.4.4.4",
            "device_type": "generic",
            "ssh_port": "22",
            "credential_id": cred.id,
            "is_active": "1",
        },
    )
    assert resp.status_code == 303
    devices = list_devices(db, device_type="generic")
    names = [d.name for d in devices]
    assert "sw-form-test" in names


# ---------------------------------------------------------------------------
# Teste — item "Mikrotik" aparece na nav para usuário autenticado
# ---------------------------------------------------------------------------


def test_mikrotik_nav_item_present(admin_client: TestClient) -> None:
    resp = admin_client.get("/")
    assert resp.status_code == 200
    assert "/mikrotik" in resp.text
    assert "MikroTik" in resp.text


def test_mikrotik_nav_item_present_for_reader(reader_client: TestClient) -> None:
    resp = reader_client.get("/devices")
    assert resp.status_code == 200
    assert "/mikrotik" in resp.text
