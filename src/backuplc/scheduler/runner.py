"""Execução com retentativas e coleta em lote (Spec E4, item 2.1)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backuplc.collector.models import Execution
from backuplc.collector.runner import collect_device
from backuplc.core.db import Database

log = logging.getLogger("backuplc.scheduler")

# Classes de falha que NÃO devem ser retentadas (PRD F-07).
_NO_RETRY = frozenset({"AUTENTICACAO", "CHAVE_HOST"})

RETRY_INTERVAL = 300  # 5 minutos (PRD F-07)


async def run_device_with_retry(
    db: Database,
    data_dir: Path,
    device_id: str,
    master_key: bytes,
    actor: str | None = None,
    *,
    retry_interval: float = RETRY_INTERVAL,
) -> Execution:
    """Coleta com até 1 retentativa. Falhas AUTENTICACAO e CHAVE_HOST não retentam."""
    loop = asyncio.get_running_loop()

    execution = await loop.run_in_executor(
        None, collect_device, db, data_dir, device_id, master_key, actor, "scheduled"
    )
    if execution.status == "ok" or execution.status in _NO_RETRY:
        return execution

    log.info(
        "retentativa agendada",
        extra={"device_id": device_id, "status": execution.status, "intervalo_s": retry_interval},
    )
    await asyncio.sleep(retry_interval)

    execution = await loop.run_in_executor(
        None, collect_device, db, data_dir, device_id, master_key, actor, "scheduled"
    )
    return execution


async def run_all_devices(
    db: Database,
    data_dir: Path,
    master_key: bytes,
    max_concurrent: int = 5,
) -> None:
    """Coleta todos os dispositivos ativos respeitando o semáforo de concorrência."""
    from backuplc.devices.service import list_devices

    devices = list_devices(db)
    active = [d for d in devices if d.is_active]
    if not active:
        log.info("nenhum dispositivo ativo para coletar")
        return

    log.info("iniciando ciclo de coleta", extra={"total": len(active)})
    sem = asyncio.Semaphore(max_concurrent)

    async def _collect_one(device_id: str) -> None:
        async with sem:
            try:
                exe = await run_device_with_retry(db, data_dir, device_id, master_key)
                log.info(
                    "coleta concluída",
                    extra={"device_id": device_id, "status": exe.status},
                )
            except Exception:
                log.exception("erro inesperado na coleta", extra={"device_id": device_id})

    await asyncio.gather(*[_collect_one(d.id) for d in active])
    log.info("ciclo de coleta encerrado", extra={"total": len(active)})
