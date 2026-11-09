"""Testes da E6.1 — Driver Mikrotik RouterOS."""

from __future__ import annotations

from typing import Any

import pytest

from backuplc.collector.driver import UnsupportedTypeError, get_driver_spec
from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.devices.models import Device
from backuplc.devices.service import create_credential, create_device

pytestmark = [pytest.mark.integration]

VALID_MIKROTIK_OUTPUT = (
    "/interface ethernet\n"
    "set [ find default-name=ether1 ] comment=WAN\n"
    "/ip address\n"
    "add address=192.0.2.1/24 interface=ether1\n"
    "/ip route\n"
    "add dst-address=0.0.0.0/0 gateway=192.0.2.254\n"
    "/system identity\n"
    "set name=router-test\n"
) * 5  # repeat to exceed min_chars=200


# ---------------------------------------------------------------------------
# Driver spec
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mikrotik_driver_registrado() -> None:
    """E6.1: get_driver_spec retorna spec correto para mikrotik_routeros."""
    spec = get_driver_spec("mikrotik_routeros")
    assert spec.netmiko_type == "mikrotik_routeros"
    assert "/export" in spec.commands
    assert spec.min_chars == 200


@pytest.mark.unit
def test_tipo_desconhecido_levanta_erro() -> None:
    """E6.1: tipo não registrado levanta UnsupportedTypeError."""
    with pytest.raises(UnsupportedTypeError):
        get_driver_spec("nao_existe_xpto")


# ---------------------------------------------------------------------------
# Correção do username
# ---------------------------------------------------------------------------


def test_collect_device_usa_username_da_credencial(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E6.1: collect_device passa o username real da credencial ao _connect_and_collect."""
    upgrade(db)

    cred = create_credential(db, secrets.master_key, "cred-mkt", "admin", "SenhaMkt123!", "")
    device = create_device(db, "rtr-mkt", "192.0.2.1", "mikrotik_routeros", 22, cred.id, True)

    captured: dict[str, str] = {}

    def _fake_connect(
        dev: Device, username: str, password: str, spec: Any
    ) -> tuple[str | None, str, str, str]:
        captured["username"] = username
        return None, VALID_MIKROTIK_OUTPUT, "ssh-ed25519", "AAAA1234"

    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _fake_connect)

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device.id, secrets.master_key)
    assert exe.status == "ok"
    assert captured.get("username") == "admin"


# ---------------------------------------------------------------------------
# Validação de saída Mikrotik
# ---------------------------------------------------------------------------


def test_mikrotik_saida_curta_falha_saida_incompleta(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E6.1: saída com menos de 200 chars resulta em status SAIDA_INCOMPLETA."""
    upgrade(db)

    cred = create_credential(db, secrets.master_key, "cred-mkt-short", "admin", "SenhaMkt123!", "")
    device = create_device(db, "rtr-mkt-short", "192.0.2.2", "mikrotik_routeros", 22, cred.id, True)

    short_output = "/ip address\nadd address=192.0.2.1/24\n"  # well under 200 chars

    def _fake_connect(
        dev: Device, username: str, password: str, spec: Any
    ) -> tuple[str | None, str, str, str]:
        return None, short_output, "ssh-ed25519", "AAAA1234"

    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _fake_connect)

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device.id, secrets.master_key)
    assert exe.status == "SAIDA_INCOMPLETA"


def test_mikrotik_saida_bad_command_falha_saida_incompleta(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E6.1: saída contendo 'bad command' resulta em status SAIDA_INCOMPLETA."""
    upgrade(db)

    cred = create_credential(db, secrets.master_key, "cred-mkt-err", "admin", "SenhaMkt123!", "")
    device = create_device(db, "rtr-mkt-err", "192.0.2.3", "mikrotik_routeros", 22, cred.id, True)

    # Output long enough but contains error pattern
    error_output = "bad command\n" + "x" * 300

    def _fake_connect(
        dev: Device, username: str, password: str, spec: Any
    ) -> tuple[str | None, str, str, str]:
        return None, error_output, "ssh-ed25519", "AAAA1234"

    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _fake_connect)

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device.id, secrets.master_key)
    assert exe.status == "SAIDA_INCOMPLETA"
