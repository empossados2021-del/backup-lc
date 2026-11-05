"""E1-02: configuração inválida impede a subida, citando a variável e nunca o valor."""

from __future__ import annotations

from pathlib import Path

import pytest

from backuplc.cli import main
from backuplc.core.config import load_secrets, load_settings
from backuplc.core.errors import ConfigError
from conftest import CANARY_SESSION

pytestmark = pytest.mark.unit


def test_configuracao_valida(env: Path) -> None:
    secrets = load_secrets(load_settings())
    assert secrets.session_secret == CANARY_SESSION
    assert CANARY_SESSION not in repr(secrets)


def test_variavel_obrigatoria_ausente(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLC_SESSION_SECRET_FILE")
    with pytest.raises(ConfigError, match="BLC_SESSION_SECRET_FILE"):
        load_settings()


def test_porta_invalida(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLC_PORT", "99999")
    with pytest.raises(ConfigError, match="BLC_PORT"):
        load_settings()


def test_arquivo_de_segredo_ausente(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLC_MASTER_KEY_FILE", str(env / "nao-existe"))
    with pytest.raises(ConfigError, match="BLC_MASTER_KEY_FILE: arquivo não encontrado"):
        load_secrets(load_settings())


def test_arquivo_de_segredo_vazio(env: Path) -> None:
    (env / "secrets" / "session_secret").write_text("   \n")
    with pytest.raises(ConfigError, match="BLC_SESSION_SECRET_FILE: arquivo vazio"):
        load_secrets(load_settings())


@pytest.mark.parametrize(
    ("arquivo", "conteudo", "variavel"),
    [
        ("session_secret", "segredo-curto-CANARIO", "BLC_SESSION_SECRET_FILE"),
        ("master_key", "chave-invalida-CANARIO-xyz", "BLC_MASTER_KEY_FILE"),
    ],
)
def test_segredo_invalido_nao_vaza(env: Path, arquivo: str, conteudo: str, variavel: str) -> None:
    (env / "secrets" / arquivo).write_text(conteudo)
    with pytest.raises(ConfigError) as excinfo:
        load_secrets(load_settings())
    assert variavel in str(excinfo.value)
    assert conteudo not in str(excinfo.value)


@pytest.mark.security
def test_check_config_falha_sem_vazar(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    valor = "valor-secreto-invalido-CANARIO"
    (env / "secrets" / "master_key").write_text(valor)
    assert main(["check-config"]) == 2
    saida = capsys.readouterr().out
    assert "BLC_MASTER_KEY_FILE" in saida
    assert valor not in saida
