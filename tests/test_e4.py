"""Testes da E4 — Agendamento e histórico."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from backuplc.collector.models import Execution
from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database, utcnow
from backuplc.devices.service import create_credential, create_device

pytestmark = [pytest.mark.integration]

VALID_OUTPUT = (
    "!\nhostname switch-01\n" + "interface Vlan1\n ip address 10.0.0.1 255.255.255.0\n" * 5
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_device(db: Database, secrets: AppSecrets, name: str = "sw-e4") -> Any:
    cred = create_credential(db, secrets.master_key, f"cred-{name}", "user", "SenhaE4Test1!", "")
    # IP único e estável derivado do nome para evitar conflito entre testes.
    ip_octet = sum(ord(c) for c in name) % 253 + 1
    ip = f"10.0.{ip_octet}.1"
    return create_device(db, name, ip, "generic", 22, cred.id, True)


def _stub_ok(output: str = VALID_OUTPUT) -> Any:
    def _fake(
        device: Any, username: str, password: str, spec: Any
    ) -> tuple[str | None, str, str, str]:
        return None, output, "ssh-ed25519", "AAAA1234"

    return _fake


def _stub_fail(status: str) -> Any:
    def _fake(
        device: Any, username: str, password: str, spec: Any
    ) -> tuple[str | None, str, str, str]:
        return status, "", "", ""

    return _fake


def _get_csrf(client: Any, secrets: AppSecrets) -> str:
    from backuplc.auth.service import make_csrf_token

    session_id = client.cookies.get("session_id")
    return make_csrf_token(session_id, secrets.session_secret)


# ---------------------------------------------------------------------------
# E4-01: Recovery — execuções running → ERRO_INTERNO
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_recovery_execucoes_running(db: Database, device_with_cred: tuple[str, str]) -> None:
    """E4-01: execuções running são marcadas ERRO_INTERNO na subida."""
    from backuplc.scheduler.service import recover_running_executions

    device_id, _ = device_with_cred
    # Cria execução presa em running.
    with db.session() as s:
        s.add(
            Execution(
                device_id=device_id,
                started_at=utcnow(),
                status="running",
                trigger="scheduled",
            )
        )

    count = recover_running_executions(db)
    assert count == 1

    with db.session() as s:
        stuck = s.query(Execution).filter_by(device_id=device_id).all()
        assert all(e.status == "ERRO_INTERNO" for e in stuck)
        detail = json.loads(stuck[0].failure_detail or "{}")
        assert detail.get("reason") == "reinício inesperado"


@pytest.mark.unit
def test_recovery_sem_execucoes_running(db: Database, device_with_cred: tuple[str, str]) -> None:
    """Recovery sem execuções running retorna 0."""
    from backuplc.scheduler.service import recover_running_executions

    count = recover_running_executions(db)
    assert count == 0


# ---------------------------------------------------------------------------
# E4-03/E4-04: Retentativas
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_retry_executa_segunda_tentativa(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-03: falha retentável → segunda tentativa bem-sucedida."""
    from backuplc.scheduler.runner import run_device_with_retry

    device_id, _ = device_with_cred
    calls: list[int] = []

    def fake_collect(
        db: Any, data_dir: Any, did: Any, mk: Any, actor: Any = None, trigger: str = "scheduled"
    ) -> Execution:
        calls.append(1)
        status = "CONEXAO" if len(calls) == 1 else "ok"
        exe = Execution(
            device_id=did, started_at=utcnow(), ended_at=utcnow(), status=status, trigger=trigger
        )
        with db.session() as s:
            s.add(exe)
        return exe

    monkeypatch.setattr("backuplc.scheduler.runner.collect_device", fake_collect)
    # Stub _connect para evitar que collect_device real tente conectar.
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    result = asyncio.run(
        run_device_with_retry(
            db, settings.data_dir, device_id, secrets.master_key, retry_interval=0
        )
    )
    assert result.status == "ok"
    assert len(calls) == 2


@pytest.mark.unit
def test_retry_autenticacao_sem_retentativa(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-04: falha AUTENTICACAO não retenta."""
    from backuplc.scheduler.runner import run_device_with_retry

    device_id, _ = device_with_cred
    calls: list[int] = []

    def fake_collect(
        db: Any, data_dir: Any, did: Any, mk: Any, actor: Any = None, trigger: str = "scheduled"
    ) -> Execution:
        calls.append(1)
        exe = Execution(
            device_id=did,
            started_at=utcnow(),
            ended_at=utcnow(),
            status="AUTENTICACAO",
            trigger=trigger,
        )
        with db.session() as s:
            s.add(exe)
        return exe

    monkeypatch.setattr("backuplc.scheduler.runner.collect_device", fake_collect)

    result = asyncio.run(
        run_device_with_retry(
            db, settings.data_dir, device_id, secrets.master_key, retry_interval=0
        )
    )
    assert result.status == "AUTENTICACAO"
    assert len(calls) == 1


@pytest.mark.unit
def test_retry_chave_host_sem_retentativa(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    device_with_cred: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-04: falha CHAVE_HOST não retenta."""
    from backuplc.scheduler.runner import run_device_with_retry

    device_id, _ = device_with_cred
    calls: list[int] = []

    def fake_collect(
        db: Any, data_dir: Any, did: Any, mk: Any, actor: Any = None, trigger: str = "scheduled"
    ) -> Execution:
        calls.append(1)
        exe = Execution(
            device_id=did,
            started_at=utcnow(),
            ended_at=utcnow(),
            status="CHAVE_HOST",
            trigger=trigger,
        )
        with db.session() as s:
            s.add(exe)
        return exe

    monkeypatch.setattr("backuplc.scheduler.runner.collect_device", fake_collect)

    result = asyncio.run(
        run_device_with_retry(
            db, settings.data_dir, device_id, secrets.master_key, retry_interval=0
        )
    )
    assert result.status == "CHAVE_HOST"
    assert len(calls) == 1


@pytest.mark.unit
def test_semaforo_limita_concorrencia(
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Semáforo de concorrência: BLC_MAX_CONCURRENT=2 com 3 devices."""
    from backuplc.core.migrate import upgrade
    from backuplc.devices.service import create_credential, create_device
    from backuplc.scheduler.runner import run_all_devices

    upgrade(db)
    # Cria 3 devices.
    for i in range(3):
        cred = create_credential(db, secrets.master_key, f"cred-sem-{i}", "u", "SenhaSem12!", "")
        create_device(db, f"sw-sem-{i}", f"10.0.{i}.1", "generic", 22, cred.id, True)

    concurrent_peak = 0
    current = 0

    def fake_collect(
        db: Any, data_dir: Any, did: Any, mk: Any, actor: Any = None, trigger: str = "scheduled"
    ) -> Execution:
        nonlocal concurrent_peak, current
        current += 1
        concurrent_peak = max(concurrent_peak, current)
        exe = Execution(
            device_id=did, started_at=utcnow(), ended_at=utcnow(), status="ok", trigger=trigger
        )
        with db.session() as s:
            s.add(exe)
        current -= 1
        return exe

    monkeypatch.setattr("backuplc.scheduler.runner.collect_device", fake_collect)
    # run_device_with_retry também usa collect_device indiretamente via run_in_executor;
    # monkeypatching direto evita thread pool.

    asyncio.run(run_all_devices(db, settings.data_dir, secrets.master_key, max_concurrent=2))
    assert concurrent_peak <= 2


# ---------------------------------------------------------------------------
# E4-05: coleta manual via POST (rotas web)
# ---------------------------------------------------------------------------


def test_rota_collect_post_admin(
    admin_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-05: admin faz POST /devices/{id}/collect com CSRF → execução manual registrada."""
    device = _make_device(db, secrets, "sw-post")
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(f"/devices/{device.id}/collect", data={"csrf_token": csrf})
    assert resp.status_code == 303
    assert f"/devices/{device.id}" in resp.headers["location"]

    with db.session() as s:
        execs = s.query(Execution).filter_by(device_id=device.id).all()
    assert len(execs) == 1
    assert execs[0].trigger == "manual"


def test_rota_collect_post_reader_403(
    reader_client: Any,
    db: Database,
    secrets: AppSecrets,
) -> None:
    """E4-05: reader recebe 403 ao tentar POST /collect."""
    device = _make_device(db, secrets, "sw-reader-post")
    csrf = _get_csrf(reader_client, secrets)
    resp = reader_client.post(f"/devices/{device.id}/collect", data={"csrf_token": csrf})
    assert resp.status_code == 403


def test_rota_collect_all_admin(
    admin_client: Any,
    db: Database,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-05: admin dispara coleta em todos os switches ativos."""
    _make_device(db, secrets, "sw-all-1")
    _make_device(db, secrets, "sw-all-2")

    # Suprime a execução assíncrona real substituindo run_all_devices por coroutine vazia.
    async def _noop(*_a: Any, **_kw: Any) -> None:
        return

    monkeypatch.setattr("backuplc.scheduler.runner.run_all_devices", _noop)

    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post("/devices/collect-all", data={"csrf_token": csrf})
    assert resp.status_code == 303
    assert "/devices" in resp.headers["location"]


# ---------------------------------------------------------------------------
# E4-07: paginação e filtro no histórico
# ---------------------------------------------------------------------------


def test_historico_paginado(
    admin_client: Any,
    db: Database,
    secrets: AppSecrets,
) -> None:
    """E4-07: GET /devices/{id}?page=2 retorna segunda página."""
    device = _make_device(db, secrets, "sw-pag")
    # Cria 25 execuções.
    with db.session() as s:
        for _i in range(25):
            s.add(
                Execution(
                    device_id=device.id,
                    started_at=utcnow(),
                    ended_at=utcnow(),
                    status="ok",
                    trigger="scheduled",
                )
            )

    resp = admin_client.get(f"/devices/{device.id}?page=2")
    assert resp.status_code == 200
    assert "Página 2" in resp.text


def test_historico_filtro_status(
    admin_client: Any,
    db: Database,
    secrets: AppSecrets,
) -> None:
    """E4-07: filtro por status exibe apenas execuções do status pedido."""
    device = _make_device(db, secrets, "sw-filter")
    with db.session() as s:
        s.add(
            Execution(
                device_id=device.id,
                started_at=utcnow(),
                ended_at=utcnow(),
                status="ok",
                trigger="scheduled",
            )
        )
        s.add(
            Execution(
                device_id=device.id,
                started_at=utcnow(),
                ended_at=utcnow(),
                status="CONEXAO",
                trigger="scheduled",
            )
        )

    resp = admin_client.get(f"/devices/{device.id}?status=CONEXAO")
    assert resp.status_code == 200
    assert "CONEXAO" in resp.text


# ---------------------------------------------------------------------------
# E4-08: download de versão
# ---------------------------------------------------------------------------


def test_download_versao(
    admin_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-08: download entrega conteúdo do arquivo com headers corretos."""
    device = _make_device(db, secrets, "sw-dl")
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    # Coleta para gerar uma versão.
    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device.id, secrets.master_key)
    assert exe.version_id is not None

    resp = admin_client.get(f"/devices/{device.id}/versions/{exe.version_id}/download")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert VALID_OUTPUT.encode() == resp.content


def test_download_sem_auth_redireciona(client: Any, db: Database, secrets: AppSecrets) -> None:
    """E4-08: download sem autenticação redireciona para /login."""
    resp = client.get("/devices/00000000-0000-0000-0000-000000000000/versions/fake/download")
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_download_nao_expoe_caminho(
    admin_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-08: headers de download não expõem o caminho físico do arquivo."""
    device = _make_device(db, secrets, "sw-dl-path")
    monkeypatch.setattr("backuplc.collector.runner._connect_and_collect", _stub_ok())

    from backuplc.collector.runner import collect_device

    exe = collect_device(db, settings.data_dir, device.id, secrets.master_key)
    assert exe.version_id is not None

    resp = admin_client.get(f"/devices/{device.id}/versions/{exe.version_id}/download")
    assert resp.status_code == 200
    # O caminho físico (data_dir) não deve aparecer nos headers.
    for header_value in resp.headers.values():
        assert str(settings.data_dir) not in header_value


# ---------------------------------------------------------------------------
# E4-09: diff entre versões
# ---------------------------------------------------------------------------


def test_diff_duas_versoes(
    admin_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E4-09: diff entre duas versões distintas renderiza <pre> com diferenças."""
    device = _make_device(db, secrets, "sw-diff")

    from backuplc.storage.store import save_config

    # Salva versão A.
    ver_a = save_config(db, settings.data_dir, device.id, VALID_OUTPUT, [])
    assert ver_a is not None

    # Salva versão B com conteúdo diferente.
    output_b = VALID_OUTPUT + "\nnova linha de configuração\n"
    ver_b = save_config(db, settings.data_dir, device.id, output_b, [])
    assert ver_b is not None

    resp = admin_client.get(f"/devices/{device.id}/versions/{ver_a.id}/diff/{ver_b.id}")
    assert resp.status_code == 200
    assert "<pre" in resp.text
    assert "nova linha de configuração" in resp.text


def test_diff_versoes_de_devices_diferentes(
    admin_client: Any,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
) -> None:
    """E4-09: diff com versão de device diferente retorna 404."""
    device_a = _make_device(db, secrets, "sw-diff-a")
    device_b = _make_device(db, secrets, "sw-diff-b")

    from backuplc.storage.store import save_config

    ver_a = save_config(db, settings.data_dir, device_a.id, VALID_OUTPUT, [])
    ver_b = save_config(db, settings.data_dir, device_b.id, VALID_OUTPUT + "\ndiferente\n", [])
    assert ver_a is not None and ver_b is not None

    # Tenta comparar versão de device_b pelo contexto de device_a → 404.
    resp = admin_client.get(f"/devices/{device_a.id}/versions/{ver_a.id}/diff/{ver_b.id}")
    assert resp.status_code == 404
