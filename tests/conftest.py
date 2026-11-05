from __future__ import annotations

import base64
import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backuplc.core.config import AppSecrets, Settings, load_secrets, load_settings
from backuplc.core.db import Database
from backuplc.core.logging import configure_logging
from backuplc.core.migrate import upgrade
from backuplc.web.app import create_app

# Valores marcadores (canários): nunca podem aparecer em logs, banco ou arquivos.
CANARY_SESSION = "canary-session-" + "Q7" * 20
CANARY_MASTER = base64.urlsafe_b64encode(b"CANARY-MASTER-KEY-0123456789abcd").decode()
CANARIES = (CANARY_SESSION, CANARY_MASTER)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "session_secret").write_text(CANARY_SESSION + "\n")
    (secrets_dir / "master_key").write_text(CANARY_MASTER + "\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("BLC_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BLC_SESSION_SECRET_FILE", str(secrets_dir / "session_secret"))
    monkeypatch.setenv("BLC_MASTER_KEY_FILE", str(secrets_dir / "master_key"))
    return tmp_path


@pytest.fixture
def settings(env: Path) -> Settings:
    return load_settings()


@pytest.fixture
def secrets(settings: Settings) -> AppSecrets:
    return load_secrets(settings)


@pytest.fixture
def db(settings: Settings) -> Iterator[Database]:
    database = Database(settings.data_dir)
    yield database
    database.dispose()


@pytest.fixture
def log_stream() -> io.StringIO:
    stream = io.StringIO()
    configure_logging("DEBUG", stream=stream)
    return stream


@pytest.fixture
def client(settings: Settings, secrets: AppSecrets, db: Database) -> Iterator[TestClient]:
    upgrade(db)
    with TestClient(create_app(settings, secrets, db)) as test_client:
        yield test_client
