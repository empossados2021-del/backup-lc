"""Ciclo de vida do agendador: recovery e start/stop (Spec E4, item 2.1)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from backuplc.core.db import Database, utcnow

log = logging.getLogger("backuplc.scheduler")

# Mantém referências fortes às tasks de coleta para evitar que o GC as colete. (RUF006)
_active_tasks: set[asyncio.Task[None]] = set()


def recover_running_executions(db: Database) -> int:
    """Marca execuções com status 'running' como ERRO_INTERNO (CA-07).

    Chamado na subida do processo antes de iniciar o agendador.
    Retorna a quantidade de execuções recuperadas.
    Retorna 0 silenciosamente se a tabela ainda não existir (antes das migrações).
    """
    import json

    from sqlalchemy.exc import OperationalError

    from backuplc.collector.models import Execution

    try:
        with db.session() as s:
            stuck = s.query(Execution).filter_by(status="running").all()
            for exe in stuck:
                exe.status = "ERRO_INTERNO"
                exe.ended_at = utcnow()
                exe.failure_detail = json.dumps({"reason": "reinício inesperado"})
            return len(stuck)
    except OperationalError:
        return 0  # Tabela ainda não existe (antes das migrações).


@asynccontextmanager
async def scheduler_lifespan(
    db: Database,
    data_dir: Path,
    master_key: bytes,
    cron: str,
    max_concurrent: int,
    timezone: str = "America/Sao_Paulo",
) -> AsyncIterator[object]:
    """Contexto de vida do agendador: recovery + APScheduler."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
    from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

    from backuplc.scheduler.runner import run_all_devices

    count = recover_running_executions(db)
    if count:
        log.warning("execuções recuperadas após reinício", extra={"count": count})

    scheduler: AsyncIOScheduler = AsyncIOScheduler()

    async def _trigger_collection() -> None:
        task = asyncio.create_task(run_all_devices(db, data_dir, master_key, max_concurrent))
        _active_tasks.add(task)
        task.add_done_callback(_active_tasks.discard)

    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone)
    scheduler.add_job(
        _trigger_collection,
        CronTrigger.from_crontab(cron, timezone=tz),
        id="run_all_devices",
        replace_existing=True,
    )
    scheduler.start()
    log.info(
        "agendador iniciado",
        extra={"cron": cron, "timezone": timezone, "max_concurrent": max_concurrent},
    )

    try:
        yield scheduler
    finally:
        scheduler.shutdown(wait=False)
        log.info("agendador encerrado")
