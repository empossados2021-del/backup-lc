"""Cálculo de saúde dos dispositivos para o dashboard (Spec E5)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from backuplc.core.db import Database


def _as_utc(dt: datetime) -> datetime:
    """Garante que um datetime é timezone-aware (UTC).

    SQLite retorna datetimes sem tzinfo; esta função os marca como UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _naive(dt: datetime) -> datetime:
    """Converte datetime para naive (UTC), para comparações com SQLite."""
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


DayStatus = Literal["ok", "fail", "none"]
DeviceState = Literal["healthy", "attention", "critical", "inactive"]


@dataclass
class DeviceHealth:
    device_id: str
    name: str
    ip_address: str
    device_type: str
    state: DeviceState
    last_ok_at: datetime | None
    last_failure_class: str | None
    age_hours: float | None  # horas desde last_ok_at, None se nunca
    days14: list[DayStatus]  # índice 0 = hoje, índice 13 = 13 dias atrás
    sparkline_svg: str = ""


@dataclass
class LastCycle:
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    successes: int
    failures: int


@dataclass
class RecentChange:
    device_id: str
    device_name: str
    collected_at: datetime
    version_id: str


@dataclass
class DashboardData:
    devices: list[DeviceHealth]
    pct_healthy: float  # 0.0–100.0, exclui inativos
    counts: dict[str, int]  # keys: healthy, attention, critical, inactive
    last_cycle: LastCycle | None
    failures_by_class: dict[str, int]  # e.g. {"CONEXAO": 2, "AUTENTICACAO": 1}
    recent_changes: list[RecentChange]  # versões criadas nos últimos 7 dias
    generated_at: datetime
    trend_days: list[tuple[int, int]]  # (ok_count, fail_count) por dia, índice 0=hoje, len=30


def compute_health(db: Database, now: datetime) -> DashboardData:
    """Computa dados do dashboard a partir do banco de dados."""
    from sqlalchemy import select

    from backuplc.collector.models import Execution
    from backuplc.devices.models import Device
    from backuplc.storage.models import ConfigVersion

    with db.session() as session:
        devices = list(session.execute(select(Device)).scalars().all())

        device_healths: list[DeviceHealth] = []

        for device in devices:
            # Carregar todas as execuções ordenadas por started_at DESC
            execs = list(
                session.execute(
                    select(Execution)
                    .where(Execution.device_id == device.id)
                    .order_by(Execution.started_at.desc())
                )
                .scalars()
                .all()
            )

            # last_ok_at: execução mais recente com status="ok"
            last_ok_at: datetime | None = None
            for ex in execs:
                if ex.status == "ok":
                    raw = ex.ended_at if ex.ended_at is not None else ex.started_at
                    last_ok_at = _as_utc(raw)
                    break

            # last_failure_class: execução mais recente com status não em ("ok", "running")
            last_failure_class: str | None = None
            for ex in execs:
                if ex.status not in ("ok", "running"):
                    last_failure_class = ex.status
                    break

            # age_hours
            age_hours: float | None = None
            if last_ok_at is not None:
                age_hours = (now - last_ok_at).total_seconds() / 3600.0

            # Estado
            state: DeviceState
            if not device.is_active:
                state = "inactive"
            elif (
                age_hours is not None
                and age_hours < 26
                and len(execs) > 0
                and execs[0].status == "ok"
            ):
                state = "healthy"
            elif (
                len(execs) > 0
                and execs[0].status not in ("ok", "running")
                and last_ok_at is not None
                and age_hours is not None
                and age_hours < 48
            ) or (age_hours is not None and 26 <= age_hours < 48):
                state = "attention"
            else:
                state = "critical"

            # days14[i]: i=0 é hoje, i=13 é 13 dias atrás
            days14: list[DayStatus] = []
            for i in range(14):
                day_start = (now - timedelta(days=i)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_end = day_start + timedelta(days=1)
                day_execs = [ex for ex in execs if day_start <= _as_utc(ex.started_at) < day_end]
                day_status: DayStatus
                if any(ex.status == "ok" for ex in day_execs):
                    day_status = "ok"
                elif day_execs:
                    day_status = "fail"
                else:
                    day_status = "none"
                days14.append(day_status)

            device_healths.append(
                DeviceHealth(
                    device_id=device.id,
                    name=device.name,
                    ip_address=device.ip_address,
                    device_type=device.device_type,
                    state=state,
                    last_ok_at=last_ok_at,
                    last_failure_class=last_failure_class,
                    age_hours=age_hours,
                    days14=days14,
                )
            )

        # last_cycle: execuções agendadas nas últimas 25 horas
        since_25h = _naive(now - timedelta(hours=25))
        recent_sched = list(
            session.execute(
                select(Execution)
                .where(
                    Execution.trigger == "scheduled",
                    Execution.started_at >= since_25h,
                )
                .order_by(Execution.started_at.desc())
            )
            .scalars()
            .all()
        )

        last_cycle: LastCycle | None = None
        if recent_sched:
            # Referência: execução mais recente; agrupar por dentro de 60 min
            ref_time = _as_utc(recent_sched[0].started_at)
            group = [
                ex
                for ex in recent_sched
                if abs((_as_utc(ex.started_at) - ref_time).total_seconds()) <= 3600
            ]
            cycle_start = min(_as_utc(ex.started_at) for ex in group)
            ended_list = [_as_utc(ex.ended_at) for ex in group if ex.ended_at is not None]
            cycle_ended: datetime | None = (
                max(ended_list) if len(ended_list) == len(group) else None
            )
            duration_seconds: int | None = None
            if cycle_ended is not None:
                duration_seconds = int((cycle_ended - cycle_start).total_seconds())
            successes = sum(1 for ex in group if ex.status == "ok")
            failures = sum(1 for ex in group if ex.status not in ("ok", "running"))
            last_cycle = LastCycle(
                started_at=cycle_start,
                ended_at=cycle_ended,
                duration_seconds=duration_seconds,
                successes=successes,
                failures=failures,
            )

        # failures_by_class: últimos 30 dias
        since_30d = _naive(now - timedelta(days=30))
        all_failures = list(
            session.execute(
                select(Execution).where(
                    Execution.started_at >= since_30d,
                    Execution.status.not_in(["ok", "running"]),
                )
            )
            .scalars()
            .all()
        )
        failures_by_class: dict[str, int] = {}
        for ex in all_failures:
            failures_by_class[ex.status] = failures_by_class.get(ex.status, 0) + 1

        # recent_changes: versões nos últimos 7 dias
        since_7d = _naive(now - timedelta(days=7))
        recent_versions = list(
            session.execute(
                select(ConfigVersion)
                .where(ConfigVersion.collected_at >= since_7d)
                .order_by(ConfigVersion.collected_at.desc())
                .limit(20)
            )
            .scalars()
            .all()
        )

        # Mapa de device_id → device name
        device_name_map = {d.device_id: d.name for d in device_healths}

        recent_changes: list[RecentChange] = [
            RecentChange(
                device_id=ver.device_id,
                device_name=device_name_map.get(ver.device_id, ver.device_id),
                collected_at=_as_utc(ver.collected_at),
                version_id=ver.id,
            )
            for ver in recent_versions
        ]

        # trend_days: últimos 30 dias (todos os dispositivos)
        all_execs_30d = list(
            session.execute(select(Execution).where(Execution.started_at >= since_30d))
            .scalars()
            .all()
        )
        trend_days: list[tuple[int, int]] = []
        for i in range(30):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_execs = [
                ex for ex in all_execs_30d if day_start <= _as_utc(ex.started_at) < day_end
            ]
            ok_count = sum(1 for ex in day_execs if ex.status == "ok")
            fail_count = sum(1 for ex in day_execs if ex.status not in ("ok", "running"))
            trend_days.append((ok_count, fail_count))

        # counts e pct_healthy
        counts: dict[str, int] = {"healthy": 0, "attention": 0, "critical": 0, "inactive": 0}
        for dh in device_healths:
            counts[dh.state] = counts.get(dh.state, 0) + 1

        active_total = counts["healthy"] + counts["attention"] + counts["critical"]
        pct_healthy = (counts["healthy"] / active_total * 100.0) if active_total > 0 else 0.0

        return DashboardData(
            devices=device_healths,
            pct_healthy=pct_healthy,
            counts=counts,
            last_cycle=last_cycle,
            failures_by_class=failures_by_class,
            recent_changes=recent_changes,
            generated_at=now,
            trend_days=trend_days,
        )
