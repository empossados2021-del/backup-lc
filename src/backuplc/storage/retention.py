"""Retenção automática de backups por período configurável (Spec E7.3)."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

from backuplc.core.db import Database, utcnow
from backuplc.devices.models import Device
from backuplc.storage.models import ConfigVersion

log = logging.getLogger("backuplc.storage")


def run_retention_cleanup(
    db: Database,
    data_dir: Path,
    retention_days: int,
) -> dict[str, int]:
    """Remove ConfigVersions com mais de *retention_days* dias.

    Regras:
    - Preserva sempre a versão mais recente por dispositivo (nunca fica sem histórico).
    - Remove o arquivo físico somente quando nenhuma outra ConfigVersion referencia
      o mesmo ``sha256_raw`` (deduplicação reversa).
    - ``retention_days=0`` desativa a limpeza — todas as versões são preservadas.

    Retorna ``{"versions_removed": int, "bytes_freed": int}``.
    """
    if retention_days <= 0:
        log.info("retenção desabilitada", extra={"retention_days": retention_days})
        return {"versions_removed": 0, "bytes_freed": 0}

    cutoff = utcnow() - timedelta(days=retention_days)
    versions_removed = 0
    bytes_freed = 0

    with db.session() as s:
        devices = s.query(Device).all()

        for device in devices:
            # ID da versão mais recente — nunca pode ser removida.
            latest = (
                s.query(ConfigVersion)
                .filter_by(device_id=device.id)
                .order_by(ConfigVersion.collected_at.desc())
                .first()
            )
            latest_id = latest.id if latest is not None else None

            # Versões candidatas: coletadas antes do corte e que não são a mais recente.
            query = s.query(ConfigVersion).filter(
                ConfigVersion.device_id == device.id,
                ConfigVersion.collected_at < cutoff,
            )
            if latest_id is not None:
                query = query.filter(ConfigVersion.id != latest_id)

            for version in query.all():
                # Deduplicação reversa: arquivo só é removido quando nenhuma outra
                # ConfigVersion (de qualquer dispositivo) referencia o mesmo sha256_raw.
                other_refs = (
                    s.query(ConfigVersion)
                    .filter(
                        ConfigVersion.sha256_raw == version.sha256_raw,
                        ConfigVersion.id != version.id,
                    )
                    .count()
                )
                if other_refs == 0:
                    file_path = data_dir / version.file_path
                    if file_path.exists():
                        bytes_freed += version.size_bytes
                        file_path.unlink(missing_ok=True)

                s.delete(version)
                versions_removed += 1

    log.info(
        "retenção concluída",
        extra={
            "retention_days": retention_days,
            "versions_removed": versions_removed,
            "bytes_freed": bytes_freed,
        },
    )
    return {"versions_removed": versions_removed, "bytes_freed": bytes_freed}
