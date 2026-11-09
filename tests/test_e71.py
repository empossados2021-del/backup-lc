"""Spec E7.1 — Histórico de coletas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backuplc.collector.models import Execution
from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.devices.service import create_credential, create_device
from backuplc.history.service import (
    count_cycles,
    get_cycle_executions,
    get_cycles,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC)


def _add_execution(
    db: Database,
    device_id: str,
    started_at: datetime,
    status: str = "ok",
    trigger: str = "scheduled",
    ended_at: datetime | None = None,
) -> None:
    if ended_at is None:
        ended_at = started_at + timedelta(seconds=90)
    with db.session() as s:
        s.add(
            Execution(
                device_id=device_id,
                started_at=started_at,
                ended_at=ended_at,
                status=status,
                trigger=trigger,
            )
        )


def _make_device(db: Database, secrets: object, suffix: str = "01") -> str:
    from backuplc.core.config import AppSecrets

    assert isinstance(secrets, AppSecrets)
    cred = create_credential(
        db, secrets.master_key, f"cred-{suffix}", "user", "SenhaSegura123!", ""
    )
    device = create_device(db, f"sw-{suffix}", f"10.0.0.{suffix}", "generic", 22, cred.id, True)
    return device.id


# ---------------------------------------------------------------------------
# Testes unitários: service
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_cycles_agrupa_mesmo_minuto(db: Database, secrets: object) -> None:
    """Execuções dentro do mesmo minuto formam um único ciclo."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    _add_execution(db, device_id, t0)
    _add_execution(db, device_id, t0 + timedelta(seconds=30))

    cycles = get_cycles(db)
    assert len(cycles) == 1
    assert cycles[0].total == 2


@pytest.mark.unit
def test_get_cycles_minutos_diferentes_separados(db: Database, secrets: object) -> None:
    """Execuções em minutos diferentes geram ciclos distintos."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    t1 = _utc(datetime(2026, 11, 6, 18, 1, 0))
    _add_execution(db, device_id, t0)
    _add_execution(db, device_id, t1)

    cycles = get_cycles(db)
    assert len(cycles) == 2


@pytest.mark.unit
def test_get_cycles_filtro_trigger(db: Database, secrets: object) -> None:
    """Filtro por trigger exclui ciclos de outra origem."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    t1 = _utc(datetime(2026, 11, 6, 19, 0, 0))
    _add_execution(db, device_id, t0, trigger="scheduled")
    _add_execution(db, device_id, t1, trigger="manual")

    scheduled = get_cycles(db, trigger_filter="scheduled")
    assert len(scheduled) == 1
    assert scheduled[0].trigger == "scheduled"

    manual = get_cycles(db, trigger_filter="manual")
    assert len(manual) == 1
    assert manual[0].trigger == "manual"


@pytest.mark.unit
def test_get_cycles_paginacao(db: Database, secrets: object) -> None:
    """Paginação retorna ciclos corretos por página."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    # Cria 3 ciclos em horas diferentes
    for h in range(3):
        t = _utc(datetime(2026, 11, 6, h, 0, 0))
        _add_execution(db, device_id, t)

    page1 = get_cycles(db, page=1, per_page=2)
    page2 = get_cycles(db, page=2, per_page=2)
    assert len(page1) == 2
    assert len(page2) == 1
    # Ordem: mais recente primeiro
    assert page1[0].started_at > page1[1].started_at


@pytest.mark.unit
def test_get_cycles_contagens_ok_fail(db: Database, secrets: object) -> None:
    """Contagens de ok e fail calculadas corretamente."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    _add_execution(db, device_id, t0, status="ok")
    _add_execution(db, device_id, t0 + timedelta(seconds=5), status="CONEXAO")
    _add_execution(db, device_id, t0 + timedelta(seconds=10), status="running")

    cycles = get_cycles(db)
    c = cycles[0]
    assert c.ok_count == 1
    assert c.fail_count == 1
    assert c.running_count == 1
    assert c.total == 3


@pytest.mark.unit
def test_count_cycles(db: Database, secrets: object) -> None:
    """count_cycles conta corretamente com e sem filtro."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    t1 = _utc(datetime(2026, 11, 6, 19, 0, 0))
    _add_execution(db, device_id, t0, trigger="scheduled")
    _add_execution(db, device_id, t1, trigger="manual")

    assert count_cycles(db) == 2
    assert count_cycles(db, trigger_filter="scheduled") == 1
    assert count_cycles(db, trigger_filter="manual") == 1


@pytest.mark.unit
def test_get_cycle_executions(db: Database, secrets: object) -> None:
    """Retorna execuções do ciclo com nome do dispositivo."""
    upgrade(db)
    device_id = _make_device(db, secrets)
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    _add_execution(db, device_id, t0, trigger="scheduled")

    rows = get_cycle_executions(db, cycle_key="2026-11-06T18:00", trigger="scheduled")
    assert len(rows) == 1
    assert rows[0].device_name == "sw-01"
    assert rows[0].status == "ok"


@pytest.mark.unit
def test_get_cycle_executions_vazio(db: Database, secrets: object) -> None:
    """Retorna lista vazia para ciclo inexistente."""
    upgrade(db)
    rows = get_cycle_executions(db, cycle_key="2026-01-01T00:00", trigger="scheduled")
    assert rows == []


# ---------------------------------------------------------------------------
# Testes de integração: rotas
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_history_lista_reader(reader_client: object) -> None:
    """GET /history (reader) → 200."""
    from fastapi.testclient import TestClient

    assert isinstance(reader_client, TestClient)
    r = reader_client.get("/history")
    assert r.status_code == 200
    assert "Histórico de Coletas" in r.text


@pytest.mark.integration
def test_history_sem_autenticacao(client: object) -> None:
    """GET /history sem sessão → redirect para /login."""
    from fastapi.testclient import TestClient

    assert isinstance(client, TestClient)
    r = client.get("/history")
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


@pytest.mark.integration
def test_history_vazio(admin_client: object) -> None:
    """Sem execuções exibe mensagem de estado vazio."""
    from fastapi.testclient import TestClient

    assert isinstance(admin_client, TestClient)
    r = admin_client.get("/history")
    assert r.status_code == 200
    assert "Nenhuma coleta registrada" in r.text


@pytest.mark.integration
def test_history_com_ciclo(
    admin_client: object,
    db: Database,
    secrets: object,
) -> None:
    """Ciclo agendado aparece na listagem."""
    from fastapi.testclient import TestClient

    assert isinstance(admin_client, TestClient)
    device_id = _make_device(db, secrets, suffix="10")
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    _add_execution(db, device_id, t0, trigger="scheduled")

    r = admin_client.get("/history")
    assert r.status_code == 200
    assert "Agendado" in r.text


@pytest.mark.integration
def test_history_filtro_trigger(
    admin_client: object,
    db: Database,
    secrets: object,
) -> None:
    """Filtro ?trigger=scheduled exclui manuais."""
    from fastapi.testclient import TestClient

    assert isinstance(admin_client, TestClient)
    device_id = _make_device(db, secrets, suffix="11")
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    t1 = _utc(datetime(2026, 11, 6, 19, 0, 0))
    _add_execution(db, device_id, t0, trigger="scheduled")
    _add_execution(db, device_id, t1, trigger="manual")

    r = admin_client.get("/history?trigger=scheduled")
    assert r.status_code == 200
    # Deve ter exatamente um ciclo visível
    assert r.text.count("badge--idle") == 1  # badge do tipo Agendado


@pytest.mark.integration
def test_history_detail(
    admin_client: object,
    db: Database,
    secrets: object,
) -> None:
    """GET /history/detail mostra execuções do ciclo."""
    from fastapi.testclient import TestClient

    assert isinstance(admin_client, TestClient)
    device_id = _make_device(db, secrets, suffix="12")
    t0 = _utc(datetime(2026, 11, 6, 18, 0, 0))
    _add_execution(db, device_id, t0, trigger="scheduled")

    r = admin_client.get("/history/detail?key=2026-11-06T18:00&trigger=scheduled")
    assert r.status_code == 200
    assert "sw-12" in r.text
