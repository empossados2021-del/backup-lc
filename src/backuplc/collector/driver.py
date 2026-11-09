"""Protocolo e registro de drivers de coleta (Spec E3, item 2.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backuplc.core.errors import BackupLcError


class UnsupportedTypeError(BackupLcError):
    """Tipo de dispositivo sem driver registrado."""


@dataclass(frozen=True)
class DriverSpec:
    """Especificação de um driver de coleta."""

    netmiko_type: str
    commands: list[str]
    min_chars: int = 100
    volatile_patterns: list[re.Pattern[str]] = field(default_factory=list)
    end_marker: str | None = None
    error_patterns: list[str] = field(
        default_factory=lambda: ["% Error", "% Invalid", "% Ambiguous"]
    )
    # Parâmetros de conexão — podem ser ajustados por driver.
    conn_timeout: int = 30  # socket/TCP timeout (segundos)
    banner_timeout: int = 20  # tempo máximo para receber o banner SSH
    session_timeout: int = 60  # inatividade máxima da sessão
    global_delay_factor: float = 1.0  # multiplicador de delays do Netmiko
    read_timeout: int = 30  # timeout para leitura da resposta de cada comando
    # Comandos de setup executados antes dos comandos principais (saída descartada).
    pre_commands: list[str] = field(default_factory=list)


DRIVER_REGISTRY: dict[str, DriverSpec] = {
    "generic": DriverSpec(
        netmiko_type="linux",
        commands=["show running-config"],
        min_chars=100,
        volatile_patterns=[],
        end_marker=None,
        error_patterns=["% Error", "% Invalid", "% Ambiguous"],
    ),
    "mikrotik_routeros": DriverSpec(
        netmiko_type="mikrotik_routeros",
        commands=["/export"],
        min_chars=200,
        volatile_patterns=[],
        end_marker=None,
        error_patterns=["bad command", "syntax error", "failure:"],
        conn_timeout=60,
        banner_timeout=45,
        session_timeout=120,
        global_delay_factor=2.0,
        read_timeout=300,
        pre_commands=["/console set rows=0 columns=0"],
    ),
}


def get_driver_spec(device_type: str) -> DriverSpec:
    """Retorna o DriverSpec para o tipo; levanta UnsupportedTypeError se não registrado."""
    spec = DRIVER_REGISTRY.get(device_type)
    if spec is None:
        raise UnsupportedTypeError(f"Tipo de dispositivo não suportado: {device_type}")
    return spec
