"""Testes unitários de autenticação (hash, política, sessão, CSRF, bloqueio)."""

from __future__ import annotations

import pytest

from backuplc.auth.service import (
    create_session,
    create_user,
    delete_session,
    get_session_user,
    hash_password,
    login,
    make_csrf_token,
    safe_next,
    touch_session,
    validate_password_policy,
    verify_csrf_token,
    verify_password,
)
from backuplc.core.db import Database
from backuplc.core.migrate import upgrade

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Hash de senha
# ---------------------------------------------------------------------------


def test_hash_e_verificacao_corretos() -> None:
    h = hash_password("MinhaSenh4Segura")
    assert verify_password(h, "MinhaSenh4Segura")


def test_senha_errada_nao_verifica() -> None:
    h = hash_password("MinhaSenh4Segura")
    assert not verify_password(h, "outra")


# ---------------------------------------------------------------------------
# Política de senha
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "senha",
    [
        "curta1A",  # menos de 12 caracteres
        "semdigito_aqui_A",  # sem dígito
        "SEMLOWER123456",  # sem minúscula
        "semupper123456",  # sem maiúscula
    ],
)
def test_politica_rejeita_senha_fraca(senha: str) -> None:
    with pytest.raises(ValueError):
        validate_password_policy(senha)


def test_politica_aceita_senha_valida() -> None:
    validate_password_policy("SenhaValida123")  # não deve levantar


# ---------------------------------------------------------------------------
# Sessão
# ---------------------------------------------------------------------------


def test_sessao_criada_e_recuperada(db: Database) -> None:
    upgrade(db)
    user = create_user(db, "alice", "AliceSenha1!", "admin")
    sid = create_session(db, user.id)
    assert sid
    found = get_session_user(db, sid)
    assert found is not None
    assert found.id == user.id


def test_sessao_invalida_retorna_none(db: Database) -> None:
    upgrade(db)
    assert get_session_user(db, "nao-existe") is None


def test_delete_sessao(db: Database) -> None:
    upgrade(db)
    user = create_user(db, "bob", "BobSenha123!", "reader")
    sid = create_session(db, user.id)
    delete_session(db, sid)
    assert get_session_user(db, sid) is None


def test_touch_session_renova(db: Database) -> None:
    upgrade(db)
    user = create_user(db, "carol", "CarolSenha1!", "reader")
    sid = create_session(db, user.id)
    # Deve funcionar sem erro.
    touch_session(db, sid)
    assert get_session_user(db, sid) is not None


# ---------------------------------------------------------------------------
# Login e bloqueio
# ---------------------------------------------------------------------------


def test_login_sucesso(db: Database) -> None:
    upgrade(db)
    create_user(db, "dave", "DaveSenha12!", "admin")
    result, user = login(db, "dave", "DaveSenha12!")
    assert result == "ok"
    assert user is not None


def test_login_senha_errada(db: Database) -> None:
    upgrade(db)
    create_user(db, "eve", "EveSenha123!", "reader")
    result, user = login(db, "eve", "errada")
    assert result == "invalid_credentials"
    assert user is None


def test_login_usuario_inexistente(db: Database) -> None:
    upgrade(db)
    result, user = login(db, "ninguem", "qualquer")
    assert result == "invalid_credentials"
    assert user is None


def test_bloqueio_apos_5_falhas(db: Database) -> None:
    upgrade(db)
    create_user(db, "frank", "FrankSenha1!", "reader")
    for _ in range(5):
        login(db, "frank", "errada")
    result, user = login(db, "frank", "FrankSenha1!")
    assert result == "account_locked"
    assert user is None


def test_reset_contador_apos_sucesso(db: Database) -> None:
    upgrade(db)
    create_user(db, "grace", "GraceSenha1!", "reader")
    for _ in range(3):
        login(db, "grace", "errada")
    login(db, "grace", "GraceSenha1!")  # sucesso zera contador
    # Mais 4 falhas não devem bloquear ainda (contador zerou).
    for _ in range(4):
        login(db, "grace", "errada")
    result, _ = login(db, "grace", "GraceSenha1!")
    assert result == "ok"


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------


def test_csrf_token_valido() -> None:
    sid = "abc123"
    secret = "meu-segredo-de-sessao"
    token = make_csrf_token(sid, secret)
    assert verify_csrf_token(token, sid, secret)


def test_csrf_token_invalido() -> None:
    assert not verify_csrf_token("token-errado", "sid", "secret")


def test_csrf_token_session_diferente() -> None:
    token = make_csrf_token("sid-a", "secret")
    assert not verify_csrf_token(token, "sid-b", "secret")


# ---------------------------------------------------------------------------
# safe_next
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("/dashboard", "/dashboard"),
        ("//evil.com", "/"),
        ("http://evil.com", "/"),
        ("https://evil.com/path", "/"),
        (None, "/"),
        ("", "/"),
        ("/path/with?query=1", "/path/with?query=1"),
    ],
)
def test_safe_next(value: str | None, expected: str) -> None:
    assert safe_next(value) == expected
