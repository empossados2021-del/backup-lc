"""Serviços de credencial e switch (Spec E2, ADR-006)."""

from __future__ import annotations

from cryptography.fernet import Fernet
from sqlalchemy.exc import IntegrityError

from backuplc.core.db import Database
from backuplc.core.errors import DuplicateError
from backuplc.devices.models import Credential, Device


def _fernet(master_key: bytes) -> Fernet:
    return Fernet(master_key)


def encrypt_password(master_key: bytes, plaintext: str) -> str:
    return _fernet(master_key).encrypt(plaintext.encode()).decode()


def decrypt_password(master_key: bytes, ciphertext: str) -> str:
    return _fernet(master_key).decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Credenciais
# ---------------------------------------------------------------------------


def list_credentials(db: Database) -> list[Credential]:
    with db.session() as s:
        return s.query(Credential).order_by(Credential.name).all()


def get_credential(db: Database, cred_id: str) -> Credential | None:
    with db.session() as s:
        return s.get(Credential, cred_id)


def create_credential(
    db: Database, master_key: bytes, name: str, username: str, password: str, description: str
) -> Credential:
    cred = Credential(
        name=name,
        username=username,
        encrypted_password=encrypt_password(master_key, password),
        description=description,
    )
    try:
        with db.session() as s:
            s.add(cred)
    except IntegrityError:
        raise DuplicateError(f"Credencial '{name}' já existe") from None
    return cred


def update_credential(
    db: Database,
    master_key: bytes,
    cred_id: str,
    name: str,
    username: str,
    password: str | None,
    description: str,
) -> bool:
    """Atualiza a credencial. Se password for None, mantém a senha atual. Retorna False se não achar."""
    try:
        with db.session() as s:
            cred = s.get(Credential, cred_id)
            if cred is None:
                return False
            cred.name = name
            cred.username = username
            cred.description = description
            if password:
                cred.encrypted_password = encrypt_password(master_key, password)
    except IntegrityError:
        raise DuplicateError(f"Credencial '{name}' já existe") from None
    return True


def delete_credential(db: Database, cred_id: str) -> bool:
    with db.session() as s:
        cred = s.get(Credential, cred_id)
        if cred is None:
            return False
        s.delete(cred)
    return True


def count_devices_for_credential(db: Database, cred_id: str) -> int:
    with db.session() as s:
        return s.query(Device).filter_by(credential_id=cred_id).count()


# ---------------------------------------------------------------------------
# Switches
# ---------------------------------------------------------------------------


def list_devices(db: Database, device_type: str | None = None) -> list[Device]:
    with db.session() as s:
        q = s.query(Device).order_by(Device.name)
        if device_type is not None:
            q = q.filter_by(device_type=device_type)
        return q.all()


def get_device(db: Database, device_id: str) -> Device | None:
    with db.session() as s:
        return s.get(Device, device_id)


def create_device(
    db: Database,
    name: str,
    ip_address: str,
    device_type: str,
    ssh_port: int,
    credential_id: str,
    is_active: bool,
) -> Device:
    device = Device(
        name=name,
        ip_address=ip_address,
        device_type=device_type,
        ssh_port=ssh_port,
        credential_id=credential_id,
        is_active=is_active,
    )
    try:
        with db.session() as s:
            s.add(device)
    except IntegrityError:
        raise DuplicateError(f"Switch '{name}' ou IP '{ip_address}' já existe") from None
    return device


def update_device(
    db: Database,
    device_id: str,
    name: str,
    ip_address: str,
    device_type: str,
    ssh_port: int,
    credential_id: str,
    is_active: bool,
) -> bool:
    try:
        with db.session() as s:
            device = s.get(Device, device_id)
            if device is None:
                return False
            device.name = name
            device.ip_address = ip_address
            device.device_type = device_type
            device.ssh_port = ssh_port
            device.credential_id = credential_id
            device.is_active = is_active
    except IntegrityError:
        raise DuplicateError(f"Switch '{name}' ou IP '{ip_address}' já existe") from None
    return True


def delete_device(db: Database, device_id: str) -> bool:
    with db.session() as s:
        device = s.get(Device, device_id)
        if device is None:
            return False
        s.delete(device)
    return True
