"""Função principal de coleta de configuração (Spec E3, item 2.1)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backuplc.collector.driver import DriverSpec, get_driver_spec
from backuplc.collector.models import DeviceHostKey, Execution
from backuplc.core.db import Database, utcnow
from backuplc.devices.models import Credential, Device
from backuplc.devices.service import decrypt_password
from backuplc.storage.store import save_config

log = logging.getLogger("backuplc.collector")


def _validate_output(output: str, spec: DriverSpec) -> str | None:
    """Retorna None se a saída é válida; caso contrário, a mensagem de erro."""
    stripped = output.strip()
    if len(stripped) == 0:
        return "saída vazia"
    if len(output) < spec.min_chars:
        return "saída muito curta"
    for line in output.splitlines():
        for pattern in spec.error_patterns:
            if pattern in line:
                return "saída contém erro"
    if spec.end_marker is not None and spec.end_marker not in output:
        return "marcador de fim ausente"
    return None


def _check_host_key(db: Database, device_id: str, key_type: str, key_b64: str) -> str | None:
    """Verifica ou registra a chave do host. Retorna classe de falha ou None."""
    with db.session() as s:
        existing = s.get(DeviceHostKey, device_id)
        if existing is None:
            s.add(
                DeviceHostKey(
                    device_id=device_id,
                    key_type=key_type,
                    key_b64=key_b64,
                    registered_at=utcnow(),
                )
            )
            return None
        if existing.key_b64 != key_b64 or existing.key_type != key_type:
            return "CHAVE_HOST"
        return None


def _connect_and_collect(
    device: Device, username: str, password: str, spec: DriverSpec
) -> tuple[str | None, str, str, str]:
    """Conecta via Netmiko e coleta. Retorna (failure_class, output, key_type, key_b64).

    Em caso de falha de conexão, failure_class é preenchido e output fica vazio.
    """
    from netmiko import ConnectHandler
    from netmiko.exceptions import (
        NetmikoAuthenticationException,
        NetmikoTimeoutException,
        ReadTimeout,
    )

    try:
        net_connect = ConnectHandler(
            device_type=spec.netmiko_type,
            host=device.ip_address,
            port=device.ssh_port,
            username=username,
            password=password,
            timeout=spec.conn_timeout,
            banner_timeout=spec.banner_timeout,
            session_timeout=spec.session_timeout,
            global_delay_factor=spec.global_delay_factor,
            ssh_strict=False,
            allow_auto_change=False,
        )
    except NetmikoTimeoutException:
        return "TEMPO_ESGOTADO", "", "", ""
    except NetmikoAuthenticationException:
        return "AUTENTICACAO", "", "", ""
    except OSError:
        return "CONEXAO", "", "", ""

    try:
        # Captura chave do host do transport Paramiko.
        remote_conn = net_connect.remote_conn
        if remote_conn is None:  # pragma: no cover
            return "CONEXAO", "", "", ""
        transport = remote_conn.get_transport()  # type: ignore[union-attr]
        remote_key = transport.get_remote_server_key()
        key_type = remote_key.get_name()
        key_b64 = remote_key.get_base64()

        try:
            # Comandos de setup (ex.: desabilitar paginação); saída descartada.
            for pre_cmd in spec.pre_commands:
                net_connect.send_command(pre_cmd, read_timeout=15)
            outputs: list[str] = []
            for cmd in spec.commands:
                outputs.append(str(net_connect.send_command(cmd, read_timeout=spec.read_timeout)))
        except ReadTimeout:
            return "TEMPO_ESGOTADO", "", "", ""
        output = "\n".join(outputs)
    finally:
        net_connect.disconnect()

    return None, output, key_type, key_b64


def _finish_execution(
    db: Database,
    execution_id: str,
    status: str,
    version_id: str | None = None,
    failure_detail: str | None = None,
) -> Execution:
    """Atualiza a execução com o resultado final."""
    with db.session() as s:
        exe = s.get(Execution, execution_id)
        assert exe is not None  # noqa: S101
        exe.ended_at = utcnow()
        exe.status = status
        exe.version_id = version_id
        exe.failure_detail = failure_detail
        # Precisamos retornar uma cópia desanexada.
        result = Execution(
            id=exe.id,
            device_id=exe.device_id,
            started_at=exe.started_at,
            ended_at=exe.ended_at,
            status=exe.status,
            version_id=exe.version_id,
            failure_detail=exe.failure_detail,
            trigger=exe.trigger,
            triggered_by=exe.triggered_by,
        )
    return result


def collect_device(
    db: Database,
    data_dir: Path,
    device_id: str,
    master_key: bytes,
    actor: str | None = None,
    trigger: str = "manual",
) -> Execution:
    """Coleta a configuração de um dispositivo. Retorna a Execution com o resultado."""
    # 1. Carrega dispositivo e credencial.
    with db.session() as s:
        device = s.get(Device, device_id)
        if device is None:
            raise ValueError(f"Dispositivo não encontrado: {device_id}")
        credential = s.get(Credential, device.credential_id)
        if credential is None:
            raise ValueError(f"Credencial não encontrada: {device.credential_id}")
        # Copiar valores antes de sair da sessão.
        dev_ip = device.ip_address
        dev_port = device.ssh_port
        dev_type = device.device_type
        cred_username = credential.username
        cred_encrypted = credential.encrypted_password

    # 2. Obtém driver spec.
    try:
        spec = get_driver_spec(dev_type)
    except Exception:
        log.exception("Tipo de dispositivo sem suporte: %s", dev_type)
        # Cria execução com erro interno.
        exe = Execution(
            device_id=device_id,
            started_at=utcnow(),
            ended_at=utcnow(),
            status="ERRO_INTERNO",
            trigger=trigger,
            triggered_by=actor,
            failure_detail=json.dumps({"reason": "tipo não suportado"}),
        )
        with db.session() as s:
            s.add(exe)
        return exe

    # 3. Cria execução no banco com status running.
    exe = Execution(
        device_id=device_id,
        started_at=utcnow(),
        status="running",
        trigger=trigger,
        triggered_by=actor,
    )
    with db.session() as s:
        s.add(exe)
    execution_id = exe.id

    # 4. Decifra senha.
    plain_password = decrypt_password(master_key, cred_encrypted)

    # 5. Conecta e coleta.
    # Construímos um Device-like para passar ao _connect_and_collect.
    device_proxy = Device(
        id=device_id,
        name="",
        ip_address=dev_ip,
        device_type=dev_type,
        ssh_port=dev_port,
        credential_id="",
    )

    failure, output, key_type, key_b64 = _connect_and_collect(
        device_proxy, cred_username, plain_password, spec
    )

    if failure:
        return _finish_execution(
            db, execution_id, failure, failure_detail=json.dumps({"reason": failure})
        )

    # 6. Verifica chave do host.
    host_key_failure = _check_host_key(db, device_id, key_type, key_b64)
    if host_key_failure:
        return _finish_execution(
            db,
            execution_id,
            host_key_failure,
            failure_detail=json.dumps({"reason": "chave do host diferente da registrada"}),
        )

    # 7. Valida saída.
    validation_error = _validate_output(output, spec)
    if validation_error:
        return _finish_execution(
            db,
            execution_id,
            "SAIDA_INCOMPLETA",
            failure_detail=json.dumps({"reason": validation_error}),
        )

    # 8. Salva versão.
    version = save_config(db, data_dir, device_id, output, spec.volatile_patterns)
    version_id = version.id if version is not None else None

    return _finish_execution(db, execution_id, "ok", version_id=version_id)
