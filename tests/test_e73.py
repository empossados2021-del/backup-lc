"""Spec E7.3 — Retenção automática de backups."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pytest

from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.devices.service import create_credential, create_device
from backuplc.storage.models import ConfigVersion
from backuplc.storage.retention import run_retention_cleanup

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTENT = b"hostname sw-test\ninterface eth0"


def _make_device(db: Database, secrets: object, suffix: str) -> str:
    from backuplc.core.config import AppSecrets

    assert isinstance(secrets, AppSecrets)
    cred = create_credential(
        db, secrets.master_key, f"cred-ret-{suffix}", "user", "SenhaSegura123!", ""
    )
    dev = create_device(db, f"sw-ret-{suffix}", f"10.9.0.{suffix}", "generic", 22, cred.id, True)
    return dev.id


def _add_version(
    db: Database,
    data_dir: Path,
    device_id: str,
    collected_at: datetime,
    sha: str,
) -> str:
    """Cria ConfigVersion e o arquivo físico correspondente. Retorna version.id."""
    prefix = sha[:2]
    config_dir = data_dir / "configs" / prefix
    config_dir.mkdir(parents=True, exist_ok=True)
    file_path = config_dir / sha
    if not file_path.exists():
        file_path.write_bytes(_CONTENT)

    rel = str(file_path.relative_to(data_dir))
    with db.session() as s:
        v = ConfigVersion(
            device_id=device_id,
            collected_at=collected_at,
            sha256_raw=sha,
            sha256_norm=sha,
            size_bytes=len(_CONTENT),
            file_path=rel,
        )
        s.add(v)
    with db.session() as s:
        return (
            s.query(ConfigVersion)
            .filter_by(device_id=device_id, sha256_raw=sha)
            .order_by(ConfigVersion.collected_at.desc())
            .first()
            .id
        )


def _dt(days_ago: int) -> datetime:
    from datetime import timedelta

    from backuplc.core.db import utcnow

    return utcnow() - timedelta(days=days_ago)


# ---------------------------------------------------------------------------
# E7-01: versões antigas removidas; última versão preservada
# ---------------------------------------------------------------------------


def test_versoes_antigas_removidas(db: Database, settings: object, secrets: object) -> None:
    from backuplc.core.config import Settings

    assert isinstance(settings, Settings)
    upgrade(db)
    dev_id = _make_device(db, secrets, "1")
    data_dir = settings.data_dir

    sha_old1 = "aa" * 32
    sha_old2 = "bb" * 32
    sha_old3 = "cc" * 32
    sha_new = "dd" * 32

    _add_version(db, data_dir, dev_id, _dt(400), sha_old1)
    _add_version(db, data_dir, dev_id, _dt(200), sha_old2)
    _add_version(db, data_dir, dev_id, _dt(100), sha_old3)  # > 30d → removida
    _add_version(db, data_dir, dev_id, _dt(1), sha_new)  # recente → preservada

    result = run_retention_cleanup(db, data_dir, retention_days=30)

    assert result["versions_removed"] == 3
    assert result["bytes_freed"] == len(_CONTENT) * 3

    with db.session() as s:
        remaining = s.query(ConfigVersion).filter_by(device_id=dev_id).all()
    assert len(remaining) == 1
    assert remaining[0].sha256_raw == sha_new

    assert not (data_dir / "configs" / "aa" / sha_old1).exists()
    assert not (data_dir / "configs" / "bb" / sha_old2).exists()
    assert not (data_dir / "configs" / "cc" / sha_old3).exists()
    assert (data_dir / "configs" / "dd" / sha_new).exists()


# ---------------------------------------------------------------------------
# E7-01: última versão preservada mesmo sendo mais antiga que o corte
# ---------------------------------------------------------------------------


def test_ultima_versao_preservada_mesmo_sendo_antiga(
    db: Database, settings: object, secrets: object
) -> None:
    from backuplc.core.config import Settings

    assert isinstance(settings, Settings)
    upgrade(db)
    dev_id = _make_device(db, secrets, "2")
    data_dir = settings.data_dir

    sha = "ee" * 32
    _add_version(db, data_dir, dev_id, _dt(500), sha)  # única versão e antiga

    result = run_retention_cleanup(db, data_dir, retention_days=30)

    assert result["versions_removed"] == 0
    assert result["bytes_freed"] == 0

    with db.session() as s:
        count = s.query(ConfigVersion).filter_by(device_id=dev_id).count()
    assert count == 1
    assert (data_dir / "configs" / "ee" / sha).exists()


# ---------------------------------------------------------------------------
# E7-02: arquivo físico não removido quando outra versão referencia o mesmo sha256_raw
# ---------------------------------------------------------------------------


def test_arquivo_nao_removido_com_dupla_referencia(
    db: Database, settings: object, secrets: object
) -> None:
    from backuplc.core.config import Settings

    assert isinstance(settings, Settings)
    upgrade(db)
    data_dir = settings.data_dir

    dev_a = _make_device(db, secrets, "3")
    dev_b = _make_device(db, secrets, "4")

    sha_shared = "ff" * 32  # mesmo sha_raw compartilhado pelos dois dispositivos
    sha_new_a = "fe" * 32  # versão mais recente do dev A (sha diferente)

    # dev A: versão antiga (sha_shared) + versão recente (sha_new_a → torna-se latest)
    _add_version(db, data_dir, dev_a, _dt(400), sha_shared)  # candidata à remoção
    _add_version(db, data_dir, dev_a, _dt(1), sha_new_a)  # latest de dev A

    # dev B: versão recente usando o mesmo sha_shared — mantém referência ao arquivo
    _add_version(db, data_dir, dev_b, _dt(1), sha_shared)  # latest de dev B (preservada)

    result = run_retention_cleanup(db, data_dir, retention_days=30)

    # Versão antiga do dev A é removida do banco...
    assert result["versions_removed"] == 1
    # ...mas o arquivo físico NÃO é excluído (dev B ainda referencia sha_shared).
    assert result["bytes_freed"] == 0
    assert (data_dir / "configs" / "ff" / sha_shared).exists()


# ---------------------------------------------------------------------------
# E7-01: device sem versões antigas → nenhuma remoção
# ---------------------------------------------------------------------------


def test_sem_versoes_antigas_nenhuma_remocao(
    db: Database, settings: object, secrets: object
) -> None:
    from backuplc.core.config import Settings

    assert isinstance(settings, Settings)
    upgrade(db)
    dev_id = _make_device(db, secrets, "5")
    data_dir = settings.data_dir

    sha = "11" * 32
    _add_version(db, data_dir, dev_id, _dt(10), sha)  # dentro do período

    result = run_retention_cleanup(db, data_dir, retention_days=365)

    assert result["versions_removed"] == 0
    assert result["bytes_freed"] == 0


# ---------------------------------------------------------------------------
# E7-01: retention_days=0 → nenhuma versão removida
# ---------------------------------------------------------------------------


def test_retention_days_zero_desabilita_limpeza(
    db: Database, settings: object, secrets: object
) -> None:
    from backuplc.core.config import Settings

    assert isinstance(settings, Settings)
    upgrade(db)
    dev_id = _make_device(db, secrets, "6")
    data_dir = settings.data_dir

    sha = "22" * 32
    _add_version(db, data_dir, dev_id, _dt(9999), sha)

    result = run_retention_cleanup(db, data_dir, retention_days=0)

    assert result["versions_removed"] == 0
    assert result["bytes_freed"] == 0

    with db.session() as s:
        count = s.query(ConfigVersion).filter_by(device_id=dev_id).count()
    assert count == 1


# ---------------------------------------------------------------------------
# E7-01: log JSON contém versions_removed e bytes_freed
# ---------------------------------------------------------------------------


def test_log_contem_campos_de_retencao(
    db: Database,
    settings: object,
    secrets: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from backuplc.core.config import Settings

    assert isinstance(settings, Settings)
    upgrade(db)
    dev_id = _make_device(db, secrets, "7")
    data_dir = settings.data_dir

    sha = "33" * 32
    _add_version(db, data_dir, dev_id, _dt(400), sha)

    with caplog.at_level(logging.INFO, logger="backuplc.storage"):
        run_retention_cleanup(db, data_dir, retention_days=30)

    records = [r for r in caplog.records if "retenção concluída" in r.getMessage()]
    assert records, "log 'retenção concluída' não encontrado"
    record = records[-1]
    assert hasattr(record, "versions_removed"), "campo versions_removed ausente no log"
    assert hasattr(record, "bytes_freed"), "campo bytes_freed ausente no log"
