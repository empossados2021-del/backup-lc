"""Testes E5 — Dashboard de saúde."""

from __future__ import annotations

from datetime import timedelta

import pytest

from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database, utcnow

# ---------------------------------------------------------------------------
# Testes unitários – compute_health
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_healthy_device(db: Database, secrets: AppSecrets) -> None:
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-h", "u", "SenhaH12!", "")
    dev = create_device(db, "sw-healthy", "10.1.1.1", "generic", 22, cred.id, True)
    now = utcnow()
    exe = Execution(
        device_id=dev.id,
        started_at=now - timedelta(hours=1),
        ended_at=now - timedelta(hours=1) + timedelta(minutes=1),
        status="ok",
        trigger="scheduled",
    )
    with db.session() as s:
        s.add(exe)

    dash = compute_health(db, now)
    dh = next(d for d in dash.devices if d.device_id == dev.id)
    assert dh.state == "healthy"
    assert dh.age_hours is not None
    assert dh.age_hours < 26


@pytest.mark.unit
def test_attention_device_26h(db: Database, secrets: AppSecrets) -> None:
    """Dispositivo com último backup há 30h (entre 26h e 48h) → atenção."""
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-att", "u", "SenhaAtt12!", "")
    dev = create_device(db, "sw-attention", "10.1.1.2", "generic", 22, cred.id, True)
    now = utcnow()
    exe = Execution(
        device_id=dev.id,
        started_at=now - timedelta(hours=30),
        ended_at=now - timedelta(hours=30) + timedelta(minutes=1),
        status="ok",
        trigger="scheduled",
    )
    with db.session() as s:
        s.add(exe)

    dash = compute_health(db, now)
    dh = next(d for d in dash.devices if d.device_id == dev.id)
    assert dh.state == "attention"


@pytest.mark.unit
def test_critical_device_no_backup(db: Database, secrets: AppSecrets) -> None:
    """Dispositivo ativo sem nenhuma execução → crítico."""
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-crit", "u", "SenhaCrit12!", "")
    dev = create_device(db, "sw-critical", "10.1.1.3", "generic", 22, cred.id, True)
    now = utcnow()

    dash = compute_health(db, now)
    dh = next(d for d in dash.devices if d.device_id == dev.id)
    assert dh.state == "critical"
    assert dh.last_ok_at is None
    assert dh.age_hours is None


@pytest.mark.unit
def test_critical_device_over_48h(db: Database, secrets: AppSecrets) -> None:
    """Dispositivo com último backup há mais de 48h → crítico."""
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-crit2", "u", "SenhaCrit212!", "")
    dev = create_device(db, "sw-critical-old", "10.1.1.4", "generic", 22, cred.id, True)
    now = utcnow()
    exe = Execution(
        device_id=dev.id,
        started_at=now - timedelta(hours=60),
        ended_at=now - timedelta(hours=60) + timedelta(minutes=1),
        status="ok",
        trigger="scheduled",
    )
    with db.session() as s:
        s.add(exe)

    dash = compute_health(db, now)
    dh = next(d for d in dash.devices if d.device_id == dev.id)
    assert dh.state == "critical"
    assert dh.age_hours is not None
    assert dh.age_hours >= 48


@pytest.mark.unit
def test_inactive_device(db: Database, secrets: AppSecrets) -> None:
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-idle", "u", "SenhaIdle12!", "")
    dev = create_device(db, "sw-inactive", "10.1.1.5", "generic", 22, cred.id, False)
    now = utcnow()

    dash = compute_health(db, now)
    dh = next(d for d in dash.devices if d.device_id == dev.id)
    assert dh.state == "inactive"


@pytest.mark.unit
def test_pct_healthy_calculation(db: Database, secrets: AppSecrets) -> None:
    """2 saudáveis, 1 crítico, 1 inativo → 66% (2/3)."""
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-pct", "u", "SenhaPct12!", "")
    now = utcnow()

    # 2 saudáveis
    for i in range(2):
        dev = create_device(db, f"sw-ok-{i}", f"10.2.{i}.1", "generic", 22, cred.id, True)
        exe = Execution(
            device_id=dev.id,
            started_at=now - timedelta(hours=1),
            ended_at=now - timedelta(hours=1) + timedelta(minutes=1),
            status="ok",
            trigger="scheduled",
        )
        with db.session() as s:
            s.add(exe)

    # 1 crítico (sem execuções)
    create_device(db, "sw-crit-pct", "10.2.2.1", "generic", 22, cred.id, True)
    # 1 inativo
    create_device(db, "sw-idle-pct", "10.2.3.1", "generic", 22, cred.id, False)

    dash = compute_health(db, now)
    assert dash.counts["healthy"] == 2
    assert dash.counts["critical"] == 1
    assert dash.counts["inactive"] == 1
    # 2 / (2+0+1) * 100 ≈ 66.67%
    assert abs(dash.pct_healthy - 66.67) < 1.0


@pytest.mark.unit
def test_failures_by_class(db: Database, secrets: AppSecrets) -> None:
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-fail", "u", "SenhaFail12!", "")
    dev = create_device(db, "sw-fails", "10.3.1.1", "generic", 22, cred.id, True)
    now = utcnow()

    statuses = ["CONEXAO", "CONEXAO", "AUTENTICACAO"]
    for i, st in enumerate(statuses):
        exe = Execution(
            device_id=dev.id,
            started_at=now - timedelta(days=1, hours=i),
            ended_at=now - timedelta(days=1, hours=i) + timedelta(minutes=1),
            status=st,
            trigger="scheduled",
        )
        with db.session() as s:
            s.add(exe)

    dash = compute_health(db, now)
    assert dash.failures_by_class.get("CONEXAO", 0) == 2
    assert dash.failures_by_class.get("AUTENTICACAO", 0) == 1


@pytest.mark.unit
def test_recent_changes(db: Database, secrets: AppSecrets) -> None:
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device
    from backuplc.storage.models import ConfigVersion

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-ver", "u", "SenhaVer12!", "")
    dev = create_device(db, "sw-versions", "10.4.1.1", "generic", 22, cred.id, True)
    now = utcnow()

    # Executar coleta fake → versão
    exe = Execution(
        device_id=dev.id,
        started_at=now - timedelta(days=2),
        ended_at=now - timedelta(days=2) + timedelta(minutes=1),
        status="ok",
        trigger="scheduled",
    )
    with db.session() as s:
        s.add(exe)

    ver = ConfigVersion(
        device_id=dev.id,
        collected_at=now - timedelta(days=2),
        sha256_raw="a" * 64,
        sha256_norm="b" * 64,
        file_path="data/sw-versions/v1.txt",
        size_bytes=100,
    )
    with db.session() as s:
        s.add(ver)

    dash = compute_health(db, now)
    assert len(dash.recent_changes) >= 1
    assert dash.recent_changes[0].device_name == "sw-versions"


@pytest.mark.unit
def test_last_cycle_scheduled(db: Database, secrets: AppSecrets) -> None:
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-cyc", "u", "SenhaCyc12!", "")
    now = utcnow()
    # 3 execuções agendadas recentes
    for i in range(3):
        dev = create_device(db, f"sw-cyc-{i}", f"10.5.{i}.1", "generic", 22, cred.id, True)
        exe = Execution(
            device_id=dev.id,
            started_at=now - timedelta(hours=1, minutes=i),
            ended_at=now - timedelta(hours=1, minutes=i) + timedelta(minutes=1),
            status="ok",
            trigger="scheduled",
        )
        with db.session() as s:
            s.add(exe)

    dash = compute_health(db, now)
    assert dash.last_cycle is not None
    assert dash.last_cycle.successes == 3
    assert dash.last_cycle.failures == 0


@pytest.mark.unit
def test_days14_ok_fail_none(db: Database, secrets: AppSecrets) -> None:
    """Verifica que days14 classifica corretamente ok/fail/none."""
    from backuplc.collector.models import Execution
    from backuplc.core.migrate import upgrade
    from backuplc.dashboard.health import compute_health
    from backuplc.devices.service import create_credential, create_device

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-d14", "u", "SenhaD1412!", "")
    dev = create_device(db, "sw-days14", "10.6.1.1", "generic", 22, cred.id, True)
    now = utcnow()

    # Hoje: ok
    exe_ok = Execution(
        device_id=dev.id,
        started_at=now.replace(hour=1, minute=0, second=0, microsecond=0),
        ended_at=now.replace(hour=1, minute=1, second=0, microsecond=0),
        status="ok",
        trigger="scheduled",
    )
    # Ontem: falha
    yesterday = now - timedelta(days=1)
    exe_fail = Execution(
        device_id=dev.id,
        started_at=yesterday.replace(hour=2, minute=0, second=0, microsecond=0),
        ended_at=yesterday.replace(hour=2, minute=1, second=0, microsecond=0),
        status="CONEXAO",
        trigger="scheduled",
    )
    with db.session() as s:
        s.add(exe_ok)
        s.add(exe_fail)

    dash = compute_health(db, now)
    dh = next(d for d in dash.devices if d.device_id == dev.id)
    assert dh.days14[0] == "ok"  # hoje
    assert dh.days14[1] == "fail"  # ontem
    assert dh.days14[2] == "none"  # 2 dias atrás


# ---------------------------------------------------------------------------
# Testes unitários – render_sparkline
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sparkline_14_squares() -> None:
    from backuplc.dashboard.spark import render_sparkline

    days: list = ["ok"] * 7 + ["fail"] * 4 + ["none"] * 3
    svg = render_sparkline(days)
    assert svg.count("<rect") == 14
    assert "<svg" in svg
    assert 'class="sparkline"' in svg


@pytest.mark.unit
def test_sparkline_no_inline_style() -> None:
    from backuplc.dashboard.spark import render_sparkline

    svg = render_sparkline(["ok"] * 14)
    assert "style=" not in svg


@pytest.mark.unit
def test_sparkline_classes() -> None:
    from backuplc.dashboard.spark import render_sparkline

    svg = render_sparkline(["ok", "fail", "none"] + ["none"] * 11)
    assert "spark-ok" in svg
    assert "spark-fail" in svg
    assert "spark-none" in svg


@pytest.mark.unit
def test_sparkline_today_on_right() -> None:
    """O retângulo de hoje (index 0) deve ter o maior x."""
    from backuplc.dashboard.spark import render_sparkline

    svg = render_sparkline(["ok"] + ["none"] * 13)
    # Apenas uma rect com class spark-ok (hoje = direita)
    assert 'class="spark-ok"' in svg
    # Verificar que x=156 (posição mais à direita) está presente para o único ok
    assert 'x="156"' in svg


# ---------------------------------------------------------------------------
# Testes de integração
# ---------------------------------------------------------------------------


def test_dashboard_get_ok(admin_client: object) -> None:
    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert resp.status_code == 200
    assert 'meta http-equiv="refresh"' in resp.text
    assert 'content="60"' in resp.text


def test_dashboard_no_script(admin_client: object) -> None:
    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert "<script" not in resp.text.lower()


def test_dashboard_no_inline_style(admin_client: object) -> None:
    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert 'style="' not in resp.text


def test_dashboard_requires_auth(settings: Settings, secrets: AppSecrets, db: Database) -> None:
    from fastapi.testclient import TestClient

    from backuplc.core.migrate import upgrade
    from backuplc.web.app import create_app

    upgrade(db)
    with TestClient(create_app(settings, secrets, db), follow_redirects=False) as c:
        resp = c.get("/")
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


def test_dashboard_redirect(admin_client: object) -> None:
    resp = admin_client.get("/dashboard")  # type: ignore[attr-defined]
    assert resp.status_code in (302, 303)


def test_dashboard_states_in_html(admin_client: object, db: Database, secrets: AppSecrets) -> None:
    """Dispositivo crítico deve aparecer como 'Crítico' no HTML."""
    from backuplc.devices.service import create_credential, create_device

    cred = create_credential(db, secrets.master_key, "cred-dash", "u", "SenhaDash12!", "")
    create_device(db, "sw-dash-crit", "10.5.5.5", "generic", 22, cred.id, True)

    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert resp.status_code == 200
    assert "Crítico" in resp.text


def test_dashboard_healthy_in_html(admin_client: object, db: Database, secrets: AppSecrets) -> None:
    """Dispositivo saudável deve aparecer como 'Saudável' no HTML."""
    from datetime import timedelta

    from backuplc.collector.models import Execution
    from backuplc.core.db import utcnow
    from backuplc.devices.service import create_credential, create_device

    now = utcnow()
    cred = create_credential(db, secrets.master_key, "cred-dash-ok", "u", "SenhaDashOk12!", "")
    dev = create_device(db, "sw-dash-ok", "10.5.6.5", "generic", 22, cred.id, True)
    exe = Execution(
        device_id=dev.id,
        started_at=now - timedelta(hours=1),
        ended_at=now - timedelta(hours=1) + timedelta(minutes=1),
        status="ok",
        trigger="scheduled",
    )
    with db.session() as s:
        s.add(exe)

    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert resp.status_code == 200
    assert "Saudável" in resp.text


def test_dashboard_contains_statusbar(admin_client: object) -> None:
    """Barra de status deve estar presente no HTML."""
    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert resp.status_code == 200
    assert "dash-statusbar" in resp.text
    assert "saudáveis" in resp.text


def test_dashboard_platform_checks(admin_client: object) -> None:
    """Checks de plataforma devem aparecer no dashboard."""
    resp = admin_client.get("/")  # type: ignore[attr-defined]
    assert resp.status_code == 200
    assert "Banco de dados" in resp.text
    assert "Migrações em dia" in resp.text
