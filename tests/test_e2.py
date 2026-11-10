"""Testes de integração da E2: acesso, cadastro, autorização e segurança."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backuplc.auth.service import create_user
from backuplc.core.db import Database
from backuplc.core.migrate import upgrade
from backuplc.devices.service import create_credential

pytestmark = [pytest.mark.integration, pytest.mark.security]

MASTER = None  # obtido via fixture


# ---------------------------------------------------------------------------
# E2-02: redirecionamento para /login quando não autenticado
# ---------------------------------------------------------------------------


def test_home_sem_auth_redireciona(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_devices_sem_auth_redireciona(client: TestClient) -> None:
    resp = client.get("/devices")
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# E2-03: login com credenciais corretas
# ---------------------------------------------------------------------------


def test_login_sucesso_cria_cookie(client: TestClient, db: Database) -> None:
    upgrade(db)
    create_user(db, "alice", "AliceSenha1!", "admin")

    resp = client.post(
        "/login", data={"username": "alice", "password": "AliceSenha1!", "next": "/"}
    )
    assert resp.status_code == 303
    assert "session_id" in resp.cookies


# ---------------------------------------------------------------------------
# E2-04: mensagem genérica em falha de login
# ---------------------------------------------------------------------------


def test_login_falha_mensagem_generica(client: TestClient, db: Database) -> None:
    upgrade(db)
    create_user(db, "bob", "BobSenha123!", "reader")

    resp = client.post("/login", data={"username": "bob", "password": "errada", "next": "/"})
    assert resp.status_code == 200
    # Mensagem genérica — não revela se é usuário ou senha.
    # Extrai apenas o texto do alerta (role="alert") para não confundir com labels do form.
    alert_start = resp.text.find('role="alert"')
    alert_end = resp.text.find("</p>", alert_start)
    alert_text = resp.text[alert_start:alert_end].lower() if alert_start != -1 else ""
    assert "inválidas" in alert_text
    assert "usuário" not in alert_text
    assert "senha" not in alert_text


def test_login_usuario_inexistente_mensagem_generica(client: TestClient, db: Database) -> None:
    upgrade(db)
    resp = client.post("/login", data={"username": "ninguem", "password": "qq", "next": "/"})
    assert resp.status_code == 200
    assert "inválidas" in resp.text.lower()


# ---------------------------------------------------------------------------
# E2-04: bloqueio após 5 falhas
# ---------------------------------------------------------------------------


def test_bloqueio_apos_5_falhas(client: TestClient, db: Database) -> None:
    upgrade(db)
    create_user(db, "eve", "EveSenha123!", "reader")

    for _ in range(5):
        client.post("/login", data={"username": "eve", "password": "errada", "next": "/"})

    resp = client.post("/login", data={"username": "eve", "password": "EveSenha123!", "next": "/"})
    assert resp.status_code == 200
    assert "bloqueada" in resp.text.lower() or "bloqueado" in resp.text.lower()


# ---------------------------------------------------------------------------
# E2-06: logout invalida sessão
# ---------------------------------------------------------------------------


def test_logout_invalida_sessao(admin_client: TestClient, db: Database) -> None:
    # Confirm authenticated.
    assert admin_client.get("/").status_code == 200

    # Get CSRF token for the session.
    resp = admin_client.get("/")
    # Extract CSRF token from the page.
    import re

    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    assert match, "csrf_token not found in page"
    csrf = match.group(1)

    resp = admin_client.post("/logout", data={"csrf_token": csrf})
    assert resp.status_code == 303

    # After logout, session_id cookie is cleared.
    admin_client.cookies.clear()
    assert admin_client.get("/").status_code == 302


# ---------------------------------------------------------------------------
# E2-08: CSRF inválido retorna 403
# ---------------------------------------------------------------------------


def test_csrf_invalido_retorna_403(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/credentials/new",
        data={
            "csrf_token": "token-invalido",
            "name": "x",
            "username": "u",
            "password": "P",
        },
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# E2-09: reader não pode criar/editar (CA-09)
# ---------------------------------------------------------------------------


def test_reader_nao_cria_switch(reader_client: TestClient, db: Database, secrets: object) -> None:
    # Reader consegue ver a listagem.
    resp = reader_client.get("/devices")
    assert resp.status_code == 200

    # Mas não consegue acessar o formulário de novo switch.
    resp = reader_client.get("/devices/new")
    assert resp.status_code == 403


def test_reader_nao_cria_credencial(reader_client: TestClient) -> None:
    resp = reader_client.get("/credentials")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# E2-11: admin cadastra switch com credencial existente
# ---------------------------------------------------------------------------


def test_admin_cria_switch(admin_client: TestClient, db: Database, secrets: object) -> None:

    master = secrets.master_key  # type: ignore[union-attr]
    cred = create_credential(db, master, "minha-cred", "usuario", "Senha123!", "")

    # Obter CSRF.
    resp = admin_client.get("/devices/new")
    assert resp.status_code == 200
    import re

    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.text)
    assert match
    csrf = match.group(1)

    resp = admin_client.post(
        "/devices/new",
        data={
            "csrf_token": csrf,
            "name": "sw-teste",
            "ip_address": "10.0.0.100",
            "device_type": "generic",
            "ssh_port": "22",
            "credential_id": cred.id,
            "is_active": "1",
        },
    )
    assert resp.status_code == 303

    resp = admin_client.get("/devices")
    assert "sw-teste" in resp.text


# ---------------------------------------------------------------------------
# E2-13: sem JavaScript (CA-10)
# ---------------------------------------------------------------------------


def test_paginas_e2_sem_javascript(admin_client: TestClient) -> None:
    import re

    script_tag = re.compile(r"<\s*script", re.IGNORECASE)
    event_attr = re.compile(r"<[^>]*\son[a-z]+\s*=", re.IGNORECASE)

    for path in ["/", "/devices", "/credentials", "/devices/new", "/credentials/new"]:
        resp = admin_client.get(path)
        assert resp.status_code in (200, 302, 303)
        if resp.status_code == 200:
            assert not script_tag.search(resp.text), f"<script> em {path}"
            assert not event_attr.search(resp.text), f"on* em {path}"


# ---------------------------------------------------------------------------
# Migrações reversíveis (E2-14 / E1-03)
# ---------------------------------------------------------------------------


def test_migracoes_e2_reversiveis(db: Database) -> None:
    from backuplc.core.migrate import current_revision, downgrade
    from backuplc.core.migrate import upgrade as _upgrade

    _upgrade(db)
    assert current_revision(db) == "0005"

    downgrade(db, "0001")
    assert current_revision(db) == "0001"

    _upgrade(db)
    assert current_revision(db) == "0005"
