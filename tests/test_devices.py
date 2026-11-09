"""Testes unitários de credenciais e switches."""

from __future__ import annotations

import pytest

from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.devices.service import (
    count_devices_for_credential,
    create_credential,
    create_device,
    decrypt_password,
    delete_credential,
    delete_device,
    encrypt_password,
    get_credential,
    get_device,
    list_credentials,
    list_devices,
    update_credential,
    update_device,
)
from conftest import CANARY_MASTER

pytestmark = pytest.mark.unit

MASTER = CANARY_MASTER.encode()


# ---------------------------------------------------------------------------
# Fernet
# ---------------------------------------------------------------------------


def test_encrypt_decrypt() -> None:
    ct = encrypt_password(MASTER, "minhasenha")
    assert ct != "minhasenha"
    assert decrypt_password(MASTER, ct) == "minhasenha"


def test_ciphertext_diferente_a_cada_vez() -> None:
    ct1 = encrypt_password(MASTER, "s")
    ct2 = encrypt_password(MASTER, "s")
    assert ct1 != ct2  # Fernet usa IV aleatório


# ---------------------------------------------------------------------------
# Credenciais
# ---------------------------------------------------------------------------


def test_crud_credencial(db: Database) -> None:
    upgrade(db)

    cred = create_credential(db, MASTER, "acme", "admin", "Senha123!", "teste")
    assert cred.id
    assert cred.encrypted_password != "Senha123!"

    found = get_credential(db, cred.id)
    assert found is not None
    assert found.name == "acme"

    all_creds = list_credentials(db)
    assert any(c.id == cred.id for c in all_creds)

    update_credential(db, MASTER, cred.id, "acme2", "admin2", "NovaSenha1!", "atualizada")
    updated = get_credential(db, cred.id)
    assert updated is not None
    assert updated.name == "acme2"
    assert decrypt_password(MASTER, updated.encrypted_password) == "NovaSenha1!"

    # Atualização sem mudar senha
    update_credential(db, MASTER, cred.id, "acme2", "admin2", None, "sem troca")
    sem_troca = get_credential(db, cred.id)
    assert sem_troca is not None
    assert decrypt_password(MASTER, sem_troca.encrypted_password) == "NovaSenha1!"

    delete_credential(db, cred.id)
    assert get_credential(db, cred.id) is None


# ---------------------------------------------------------------------------
# Switches
# ---------------------------------------------------------------------------


def test_crud_switch(db: Database) -> None:
    upgrade(db)

    cred = create_credential(db, MASTER, "cred1", "usr", "Pass123!", "")
    dev = create_device(db, "sw-01", "192.168.1.1", "generic", 22, cred.id, True)
    assert dev.id

    found = get_device(db, dev.id)
    assert found is not None
    assert found.name == "sw-01"

    devs = list_devices(db)
    assert any(d.id == dev.id for d in devs)

    update_device(db, dev.id, "sw-02", "192.168.1.2", "generic", 2222, cred.id, False)
    updated = get_device(db, dev.id)
    assert updated is not None
    assert updated.name == "sw-02"
    assert not updated.is_active

    assert count_devices_for_credential(db, cred.id) == 1

    delete_device(db, dev.id)
    assert get_device(db, dev.id) is None


def test_credencial_em_uso_nao_exclui(db: Database) -> None:
    """delete_credential levanta se FK RESTRICT impedir (via IntegrityError → não tratado aqui)."""
    upgrade(db)
    from sqlalchemy.exc import IntegrityError

    cred = create_credential(db, MASTER, "cred-uso", "usr", "Pass123!", "")
    create_device(db, "sw-em-uso", "10.0.0.1", "generic", 22, cred.id, True)

    # delete_credential não trata o IntegrityError; a web verifica count antes de deletar.
    with pytest.raises(IntegrityError):
        delete_credential(db, cred.id)
