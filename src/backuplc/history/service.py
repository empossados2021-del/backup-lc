"""Serviço de histórico de ciclos de coleta (Spec E7.1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from backuplc.core.db import Database

CYCLES_PER_PAGE = 20


@dataclass
class CycleSummary:
    cycle_key: str  # "2026-11-06T18:00" (UTC, agrupado por minuto)
    trigger: str
    started_at: datetime
    total: int
    ok_count: int
    fail_count: int
    running_count: int
    duration_seconds: int | None


@dataclass
class ExecutionRow:
    device_name: str
    device_id: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    failure_detail: str | None


_CYCLES_SQL = text(
    """
    SELECT
        strftime('%Y-%m-%dT%H:%M', started_at) AS cycle_key,
        trigger,
        MIN(started_at) AS started_at,
        COUNT(*) AS total,
        SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_count,
        SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running_count,
        SUM(CASE WHEN status NOT IN ('ok', 'running') THEN 1 ELSE 0 END) AS fail_count,
        CAST(
            (julianday(MAX(ended_at)) - julianday(MIN(started_at))) * 86400
            AS INTEGER
        ) AS duration_seconds
    FROM executions
    WHERE (:trigger IS NULL OR trigger = :trigger)
    GROUP BY cycle_key, trigger
    ORDER BY MIN(started_at) DESC
    LIMIT :limit OFFSET :offset
    """
)

_COUNT_SQL = text(
    """
    SELECT COUNT(*) FROM (
        SELECT 1
        FROM executions
        WHERE (:trigger IS NULL OR trigger = :trigger)
        GROUP BY strftime('%Y-%m-%dT%H:%M', started_at), trigger
    )
    """
)

_DETAIL_SQL = text(
    """
    SELECT
        d.name AS device_name,
        e.device_id,
        e.started_at,
        e.ended_at,
        e.status,
        e.failure_detail
    FROM executions e
    JOIN devices d ON d.id = e.device_id
    WHERE strftime('%Y-%m-%dT%H:%M', e.started_at) = :cycle_key
      AND e.trigger = :trigger
    ORDER BY e.started_at
    """
)


def _parse_dt(value: object) -> datetime:
    """Converte string ISO ou datetime para datetime."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _parse_dt_opt(value: object) -> datetime | None:
    if value is None:
        return None
    return _parse_dt(value)


def get_cycles(
    db: Database,
    page: int = 1,
    per_page: int = CYCLES_PER_PAGE,
    trigger_filter: str = "",
) -> list[CycleSummary]:
    """Retorna ciclos de coleta agrupados por minuto, paginados."""
    trigger_param = trigger_filter if trigger_filter else None
    offset = (page - 1) * per_page
    with db.session() as s:
        rows = s.execute(
            _CYCLES_SQL,
            {"trigger": trigger_param, "limit": per_page, "offset": offset},
        ).fetchall()
    return [
        CycleSummary(
            cycle_key=str(r.cycle_key),
            trigger=str(r.trigger),
            started_at=_parse_dt(r.started_at),
            total=int(r.total),
            ok_count=int(r.ok_count),
            fail_count=int(r.fail_count),
            running_count=int(r.running_count),
            duration_seconds=int(r.duration_seconds) if r.duration_seconds is not None else None,
        )
        for r in rows
    ]


def count_cycles(db: Database, trigger_filter: str = "") -> int:
    """Conta total de ciclos (para paginação)."""
    trigger_param = trigger_filter if trigger_filter else None
    with db.session() as s:
        result = s.execute(_COUNT_SQL, {"trigger": trigger_param}).scalar()
    return int(result) if result is not None else 0


def get_cycle_executions(
    db: Database,
    cycle_key: str,
    trigger: str,
) -> list[ExecutionRow]:
    """Retorna todas as execuções de um ciclo específico."""
    with db.session() as s:
        rows = s.execute(
            _DETAIL_SQL,
            {"cycle_key": cycle_key, "trigger": trigger},
        ).fetchall()
    return [
        ExecutionRow(
            device_name=str(r.device_name),
            device_id=str(r.device_id),
            started_at=_parse_dt(r.started_at),
            ended_at=_parse_dt_opt(r.ended_at),
            status=str(r.status),
            failure_detail=str(r.failure_detail) if r.failure_detail else None,
        )
        for r in rows
    ]
