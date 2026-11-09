"""Spec E2.3 — Agendamento configurável pela interface."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backuplc.core.config import AppSecrets
from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.core.settings_store import (
    DEFAULT_CRON,
    get_schedule_cron,
    set_schedule_cron,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf(client: TestClient, secrets: AppSecrets) -> str:
    from backuplc.auth.service import make_csrf_token

    sid = client.cookies.get("session_id", "")
    return make_csrf_token(sid, secrets.session_secret)


def _make_scheduler_mock() -> MagicMock:
    mock_job = MagicMock()
    mock_job.id = "run_all_devices"
    mock_job.next_run_time = None
    scheduler = MagicMock()
    scheduler.get_jobs.return_value = [mock_job]
    return scheduler


# ---------------------------------------------------------------------------
# Testes unitários: settings_store
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_schedule_cron_retorna_padrao_sem_registro(db: Database) -> None:
    upgrade(db)
    assert get_schedule_cron(db) == DEFAULT_CRON


@pytest.mark.unit
def test_set_schedule_cron_persiste(db: Database) -> None:
    upgrade(db)
    set_schedule_cron(db, "30 3 * * *")
    assert get_schedule_cron(db) == "30 3 * * *"


@pytest.mark.unit
def test_set_schedule_cron_atualiza(db: Database) -> None:
    upgrade(db)
    set_schedule_cron(db, "0 2 * * *")
    set_schedule_cron(db, "15 6 * * *")
    assert get_schedule_cron(db) == "15 6 * * *"


@pytest.mark.unit
def test_get_schedule_cron_sem_tabela_retorna_padrao(db: Database) -> None:
    """Sem executar migrate, tabela não existe — retorna padrão sem erro."""
    assert get_schedule_cron(db) == DEFAULT_CRON


# ---------------------------------------------------------------------------
# Testes de integração: rotas /settings
# ---------------------------------------------------------------------------


def test_get_settings_admin_ok(admin_client: TestClient) -> None:
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = admin_client.get("/settings")
    assert resp.status_code == 200
    assert "Configurações" in resp.text
    assert "Agendamento da coleta automática" in resp.text


def test_get_settings_exibe_cron_padrao(admin_client: TestClient) -> None:
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = admin_client.get("/settings")
    assert DEFAULT_CRON in resp.text


def test_get_settings_exibe_cron_do_banco(admin_client: TestClient, db: Database) -> None:
    set_schedule_cron(db, "45 22 * * *")
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = admin_client.get("/settings")
    assert "45 22 * * *" in resp.text


def test_get_settings_reader_recebe_403(reader_client: TestClient) -> None:
    reader_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = reader_client.get("/settings")
    assert resp.status_code == 403


def test_post_settings_salva_e_redireciona(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = admin_client.post(
        "/settings",
        data={"hour": "3", "minute": "30", "csrf_token": _csrf(admin_client, secrets)},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/settings?msg=salvo" in resp.headers["location"]
    assert get_schedule_cron(db) == "30 3 * * *"


def test_post_settings_cron_formato_correto(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    admin_client.post(
        "/settings",
        data={"hour": "0", "minute": "0", "csrf_token": _csrf(admin_client, secrets)},
        follow_redirects=False,
    )
    assert get_schedule_cron(db) == "0 0 * * *"


def test_post_settings_hora_invalida_retorna_422(
    admin_client: TestClient, secrets: AppSecrets
) -> None:
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = admin_client.post(
        "/settings",
        data={"hour": "25", "minute": "0", "csrf_token": _csrf(admin_client, secrets)},
    )
    assert resp.status_code == 422
    assert "Hora deve ser entre 0 e 23" in resp.text


def test_post_settings_minuto_invalido_retorna_422(
    admin_client: TestClient, secrets: AppSecrets
) -> None:
    admin_client.app.state.scheduler = _make_scheduler_mock()  # type: ignore[union-attr]
    resp = admin_client.post(
        "/settings",
        data={"hour": "2", "minute": "10", "csrf_token": _csrf(admin_client, secrets)},
    )
    assert resp.status_code == 422
    assert "Minuto deve ser 0, 15, 30 ou 45" in resp.text


def test_post_settings_chama_reschedule(admin_client: TestClient, secrets: AppSecrets) -> None:
    mock_scheduler = _make_scheduler_mock()
    admin_client.app.state.scheduler = mock_scheduler  # type: ignore[union-attr]
    admin_client.post(
        "/settings",
        data={"hour": "5", "minute": "15", "csrf_token": _csrf(admin_client, secrets)},
        follow_redirects=False,
    )
    mock_scheduler.reschedule_job.assert_called_once()
