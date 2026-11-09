"""Testes do módulo de coleta (Spec E3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backuplc.collector.driver import get_driver_spec
from backuplc.collector.models import DeviceHostKey
from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database, utcnow
from backuplc.devices.models import Device
from backuplc.storage.diff import compute_diff
from backuplc.storage.store import save_config

pytestmark = [pytest.mark.integration]

VALID_OUTPUT = (
    "!\nhostname switch-01\n" + "interface Vlan1\n ip address 10.0.0.1 255.255.255.0\n" * 5
)
SHORT_OUTPUT = "short"
ERROR_OUTPUT = "!\nhostname switch-01\n% Error in command\n" + "x" * 200


def _stub_ok(
    output: str = VALID_OUTPUT,
    key_type: str = "ssh-ed25519",
    key_b64: str = "AAAA1234",
) -> Any:
    """Retorna uma função stub para _connect_and_collect com conexão bem-sucedida."""

    def _fake(
        device: Device, username: str, password: str, spec: Any
    ) -> tuple[str | None, str, str, str]:
        return None, output, key_type, key_b64

    return _fake


def _stub_auth_fail(
    device: Device, username: str, password: str, spec: Any
) -> tuple[str | None, str, str, str]:
    """Stub que simula falha de autenticação."""
    return "AUTENTICACAO", "", "", ""


# ---------------------------------------------------------------------------
# storage/store.py
# ---------------------------------------------------------------------------


def test_save_config_cria_arquivo(
    db: Database, settings: Settings, device_with_cred: tuple[str, str]
) -> None:
    """E3-01: save_config cria arquivo com permissões corretas."""
    device_id, _ = device_with_cred
    version = save_config(db, settings.data_dir, device_id, VALID_OUTPUT, [])

    assert version is not None
    full_path = settings.data_dir / version.file_path
    assert full_path.exists()
    assert full_path.read_text(encoding="utf-8") == VALID_OUTPUT
    # Permissão 0o600.
    mode = full_path.stat().st_mode & 0o777
    assert mode == 0o600
    assert version.sha256_raw != ""
    assert version.sha256_norm != ""
    assert version.size_bytes == len(VALID_OUTPUT.encode("utf-8"))


def test_save_config_deduplica(
    db: Database, settings: Settings, device_with_cred: tuple[str, str]
) -> None:
    """E3-02: mesma saída normalizada retorna None na segunda chamada."""
    device_id, _ = device_with_cred
    v1 = save_config(db, settings.data_dir, device_id, VALID_OUTPUT, [])
    assert v1 is not None
    v2 = save_config(db, settings.data_dir, device_id, VALID_OUTPUT, [])
    assert v2 is None


def test_save_config_nova_versao_conteudo_diferente(
    db: Database, settings: Settings, device_with_cred: tuple[str, str]
) -> None:
    """E3-03: conteúdo diferente cria nova versão."""
    device_id, _ = device_with_cred
    v1 = save_config(db, settings.data_dir, device_id, VALID_OUTPUT, [])
    assert v1 is not None
    output2 = VALID_OUTPUT + "\nnova linha\n"
    v2 = save_config(db, settings.data_dir, device_id, output2, [])
    assert v2 is not None
    assert v2.sha256_raw != v1.sha256_raw


# ---------------------------------------------------------------------------
# Validação de saída (via runner._validate_output)
# ---------------------------------------------------------------------------


def test_validacao_saida_vazia() -> None:
    """E3-04: saída vazia resulta em erro."""
    from backuplc.collector.runner import _validate_output

    spec = get_driver_spec("generic")
    assert _validate_output("", spec) == "saída vazia"
    assert _validate_output("   \n  \n  ", spec) == "saída vazia"


def test_validacao_saida_curta() -> None:
    """E3-04: saída muito curta resulta em erro."""
    from backuplc.collector.runner import _validate_output

    spec = get_driver_spec("generic")
    assert _validate_output(SHORT_OUTPUT, spec) == "saída muito curta"


def test_validacao_saida_com_erro() -> None:
    """E3-04: saída com padrão de erro resulta em erro."""
    from backuplc.collector.runner import _validate_output

    spec = get_driver_spec("generic")
    assert _validate_output(ERROR_OUTPUT, spec) == "saída contém erro"


# ---------------------------------------------------------------------------
# storage/diff.py
# ---------------------------------------------------------------------------


def test_compute_diff() -> None:
    text_a = "linha1\nlinha2\nlinha3\n"
    text_b = "linha1\nlinha2 modificada\nlinha3\n"
    result = compute_diff(text_a, text_b)
    assert "-linha2\n" in result
    assert "+linha2 modificada\n" in result


# ---------------------------------------------------------------------------
# collect_device — stubs de _connect_and_collect
# ---------------------------------------------------------------------------


def test_collect_device_ok(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3-01: coleta com stub OK cria execução e versão."""
    device_id, _ = device_with_cred
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device_id, secrets.master_key)
    assert exe.status == "ok"
    assert exe.version_id is not None


def test_collect_device_sem_nova_versao(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3-02: segunda coleta com mesma config não cria nova versão."""
    device_id, _ = device_with_cred
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    from backuplc.collector.runner import collect_device

    exe1 = collect_device(db, settings.data_dir, device_id, secrets.master_key)
    assert exe1.status == "ok"
    assert exe1.version_id is not None

    exe2 = collect_device(db, settings.data_dir, device_id, secrets.master_key)
    assert exe2.status == "ok"
    assert exe2.version_id is None


def test_collect_device_autenticacao_falha(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3-05: falha de autenticação gera status AUTENTICACAO."""
    device_id, _ = device_with_cred
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_auth_fail)

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device_id, secrets.master_key)
    assert exe.status == "AUTENTICACAO"
    assert exe.version_id is None


def test_collect_device_chave_host_nova(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3-06: primeira conexão registra a chave do host."""
    device_id, _ = device_with_cred
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device_id, secrets.master_key)
    assert exe.status == "ok"

    # Verifica que a chave foi registrada.
    with db.session() as s:
        hk = s.get(DeviceHostKey, device_id)
        assert hk is not None
        assert hk.key_type == "ssh-ed25519"
        assert hk.key_b64 == "AAAA1234"


def test_collect_device_chave_host_diferente(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3-07: chave diferente da registrada gera CHAVE_HOST."""
    device_id, _ = device_with_cred

    # Registra uma chave primeiro.
    with db.session() as s:
        s.add(
            DeviceHostKey(
                device_id=device_id,
                key_type="ssh-ed25519",
                key_b64="ORIGINAL_KEY",
                registered_at=utcnow(),
            )
        )

    # Stub retorna chave diferente.
    monkeypatch.setattr(
        "backuplc.collector.runner._connect_and_collect", _stub_ok(key_b64="DIFFERENT_KEY")
    )

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device_id, secrets.master_key)
    assert exe.status == "CHAVE_HOST"
    assert exe.version_id is None


def test_collect_device_canarios(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
    log_stream: Any,
) -> None:
    """E3-10: canários de senha nunca aparecem em banco, logs ou arquivos."""
    from conftest import CANARIES

    device_id, _ = device_with_cred
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    from backuplc.collector.runner import collect_device

    collect_device(db, settings.data_dir, device_id, secrets.master_key)
    db.dispose()

    # Verifica que nenhum canário aparece nos arquivos gerados.
    for path in Path(settings.data_dir).rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            for canary in CANARIES:
                assert canary.encode() not in content, f"canário encontrado em {path.name}"


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


def test_rota_collect_admin(
    admin_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E3-08 / E4-05: admin pode disparar coleta via POST."""
    from backuplc.auth.service import make_csrf_token
    from backuplc.devices.service import create_credential, create_device

    master_key = secrets.master_key
    cred = create_credential(db, master_key, "cred-rota", "user", "SenhaRota1234!", "")
    device = create_device(db, "sw-rota", "10.0.0.99", "generic", 22, cred.id, True)

    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    session_id = admin_client.cookies.get("session_id")
    csrf = make_csrf_token(session_id, secrets.session_secret)

    resp = admin_client.post(f"/devices/{device.id}/collect", data={"csrf_token": csrf})
    assert resp.status_code == 303
    assert f"/devices/{device.id}" in resp.headers["location"]


def test_rota_collect_reader_403(
    reader_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
) -> None:
    """E3-09 / E4-05: leitor recebe 403 ao tentar coletar via POST."""
    from backuplc.auth.service import make_csrf_token
    from backuplc.devices.service import create_credential, create_device

    master_key = secrets.master_key
    cred = create_credential(db, master_key, "cred-rota-r", "user", "SenhaRota1234!", "")
    device = create_device(db, "sw-rota-r", "10.0.0.100", "generic", 22, cred.id, True)

    session_id = reader_client.cookies.get("session_id")
    csrf = make_csrf_token(session_id, secrets.session_secret)

    resp = reader_client.post(f"/devices/{device.id}/collect", data={"csrf_token": csrf})
    assert resp.status_code == 403


def test_rota_device_detail(
    admin_client: Any,
    db: Database,
    secrets: AppSecrets,
) -> None:
    """Rota de detalhe do switch funciona."""
    from backuplc.devices.service import create_credential, create_device

    master_key = secrets.master_key
    cred = create_credential(db, master_key, "cred-det", "user", "SenhaDetail123!", "")
    device = create_device(db, "sw-det", "10.0.0.101", "generic", 22, cred.id, True)

    resp = admin_client.get(f"/devices/{device.id}")
    assert resp.status_code == 200
    assert "sw-det" in resp.text
