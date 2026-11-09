from __future__ import annotations

import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from backuplc.cli import main

pytestmark = pytest.mark.unit


def test_init_secrets_cria_arquivos_privados(tmp_path: Path) -> None:
    destino = tmp_path / "s"
    assert main(["init-secrets", "--dir", str(destino)]) == 0
    for nome in ("session_secret", "master_key"):
        arquivo = destino / nome
        assert stat.S_IMODE(arquivo.stat().st_mode) == 0o600
        assert len(arquivo.read_text().strip()) >= 32


def test_init_secrets_nao_sobrescreve(tmp_path: Path) -> None:
    destino = tmp_path / "s"
    main(["init-secrets", "--dir", str(destino)])
    antes = (destino / "master_key").read_text()
    main(["init-secrets", "--dir", str(destino)])
    assert (destino / "master_key").read_text() == antes


def test_migrate_e_check_config(env: Path) -> None:
    assert main(["check-config"]) == 0
    assert main(["migrate"]) == 0
    assert main(["migrate", "--down", "base"]) == 0
    assert main(["migrate"]) == 0


def test_create_admin_cria_usuario(env: Path) -> None:
    with patch("getpass.getpass", return_value="AdminPass12!"):
        result = main(["create-admin", "--username", "admin"])
    assert result == 0


def test_create_admin_senhas_diferentes(env: Path) -> None:
    passwords = iter(["AdminPass12!", "OutraSenha12!"])
    with patch("getpass.getpass", side_effect=lambda _: next(passwords)):
        result = main(["create-admin", "--username", "admin"])
    assert result == 1


def test_create_admin_senha_fraca(env: Path) -> None:
    with patch("getpass.getpass", return_value="fraca"):
        result = main(["create-admin", "--username", "admin"])
    assert result == 1


def test_create_admin_usuario_duplicado(env: Path) -> None:
    with patch("getpass.getpass", return_value="AdminPass12!"):
        main(["create-admin", "--username", "admin"])
    with patch("getpass.getpass", return_value="AdminPass12!"):
        result = main(["create-admin", "--username", "admin"])
    assert result == 1
