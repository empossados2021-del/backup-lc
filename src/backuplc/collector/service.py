"""Serviços de leitura para o módulo collector (Spec E3/E4)."""

from __future__ import annotations

from backuplc.collector.models import DeviceHostKey, Execution
from backuplc.core.db import Database
from backuplc.storage.models import ConfigVersion

PAGE_SIZE = 20


def list_executions(
    db: Database,
    device_id: str,
    limit: int = PAGE_SIZE,
    offset: int = 0,
    status_filter: str | None = None,
) -> list[Execution]:
    """Retorna execuções de um dispositivo com paginação e filtro opcional por status."""
    with db.session() as s:
        q = s.query(Execution).filter_by(device_id=device_id)
        if status_filter:
            q = q.filter(Execution.status == status_filter)
        return q.order_by(Execution.started_at.desc()).offset(offset).limit(limit).all()


def count_executions(
    db: Database,
    device_id: str,
    status_filter: str | None = None,
) -> int:
    """Conta execuções de um dispositivo, opcionalmente filtradas por status."""
    with db.session() as s:
        q = s.query(Execution).filter_by(device_id=device_id)
        if status_filter:
            q = q.filter(Execution.status == status_filter)
        return q.count()


def list_versions(db: Database, device_id: str) -> list[ConfigVersion]:
    """Retorna todas as versões de um dispositivo, ordenadas da mais recente."""
    with db.session() as s:
        return (
            s.query(ConfigVersion)
            .filter_by(device_id=device_id)
            .order_by(ConfigVersion.collected_at.desc())
            .all()
        )


def list_versions_by_date(
    db: Database,
    device_id: str,
    date_str: str,
) -> list[ConfigVersion]:
    """Retorna versões de um dispositivo para uma data UTC (formato AAAA-MM-DD)."""
    from datetime import datetime, timedelta

    try:
        day_start = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []
    day_end = day_start + timedelta(days=1)
    with db.session() as s:
        return (
            s.query(ConfigVersion)
            .filter(
                ConfigVersion.device_id == device_id,
                ConfigVersion.collected_at >= day_start,
                ConfigVersion.collected_at < day_end,
            )
            .order_by(ConfigVersion.collected_at.desc())
            .all()
        )


def get_version(db: Database, version_id: str) -> ConfigVersion | None:
    """Retorna uma versão pelo ID."""
    with db.session() as s:
        return s.get(ConfigVersion, version_id)


def get_host_key(db: Database, device_id: str) -> DeviceHostKey | None:
    """Retorna a chave do host registrada para o dispositivo, se houver."""
    with db.session() as s:
        return s.get(DeviceHostKey, device_id)


def delete_host_key(db: Database, device_id: str) -> bool:
    """Remove o registro de chave do host. Retorna True se existia."""
    with db.session() as s:
        hk = s.get(DeviceHostKey, device_id)
        if hk is None:
            return False
        s.delete(hk)
    return True
