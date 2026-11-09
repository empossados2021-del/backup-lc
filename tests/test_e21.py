"""Testes E2.1 — Gestão de usuários e perfis."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_csrf(client: TestClient, secrets: AppSecrets) -> str:
    from backuplc.auth.service import make_csrf_token

    sid = client.cookies.get("session_id", "")
    return make_csrf_token(sid, secrets.session_secret)


# ---------------------------------------------------------------------------
# Testes unitários dos novos serviços
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_create_user_operator(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user
    from backuplc.core.migrate import upgrade

    upgrade(db)
    u = create_user(db, "op1", "OperSenha12!", "operator")
    assert u.role == "operator"


@pytest.mark.unit
def test_create_user_invalid_role(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user
    from backuplc.core.migrate import upgrade

    upgrade(db)
    with pytest.raises(ValueError, match="Perfil inválido"):
        create_user(db, "bad", "SenhaValida12!", "superuser")


@pytest.mark.unit
def test_list_users(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user, list_users
    from backuplc.core.migrate import upgrade

    upgrade(db)
    create_user(db, "u1", "Senha11111A!", "reader")
    create_user(db, "u2", "Senha22222B!", "admin")
    users = list_users(db)
    assert len(users) == 2
    names = {u.username for u in users}
    assert "u1" in names and "u2" in names


@pytest.mark.unit
def test_update_user(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user, get_user, update_user
    from backuplc.core.migrate import upgrade

    upgrade(db)
    u = create_user(db, "alice", "AliceSenha12!", "reader")
    update_user(db, u.id, "alice-updated", "operator", True)
    updated = get_user(db, u.id)
    assert updated is not None
    assert updated.username == "alice-updated"
    assert updated.role == "operator"


@pytest.mark.unit
def test_change_password(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import change_password, create_user, login
    from backuplc.core.migrate import upgrade

    upgrade(db)
    u = create_user(db, "bob", "BobSenha1234!", "reader")
    change_password(db, u.id, "NewSenha5678!")
    result, _ = login(db, "bob", "NewSenha5678!")
    assert result == "ok"


@pytest.mark.unit
def test_delete_user(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user, delete_user, get_user
    from backuplc.core.migrate import upgrade

    upgrade(db)
    u = create_user(db, "del-user", "DelSenha1234!", "reader")
    delete_user(db, u.id)
    assert get_user(db, u.id) is None


@pytest.mark.unit
def test_update_user_invalid_role(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user, update_user
    from backuplc.core.migrate import upgrade

    upgrade(db)
    u = create_user(db, "roletest", "RoleTest123!", "reader")
    with pytest.raises(ValueError, match="Perfil inválido"):
        update_user(db, u.id, "roletest", "superuser", True)


@pytest.mark.unit
def test_change_password_weak(db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import change_password, create_user
    from backuplc.core.migrate import upgrade

    upgrade(db)
    u = create_user(db, "weakpw", "WeakPw12345!", "reader")
    with pytest.raises(ValueError):
        change_password(db, u.id, "short")


# ---------------------------------------------------------------------------
# Testes de integração — /users routes
# ---------------------------------------------------------------------------


def test_users_list_admin(admin_client: TestClient) -> None:
    resp = admin_client.get("/users")
    assert resp.status_code == 200
    assert "Usuários" in resp.text


def test_users_list_reader_403(reader_client: TestClient) -> None:
    resp = reader_client.get("/users")
    assert resp.status_code == 403


def test_users_new_get_admin(admin_client: TestClient) -> None:
    resp = admin_client.get("/users/new")
    assert resp.status_code == 200
    assert "Novo usuário" in resp.text


def test_users_new_get_reader_403(reader_client: TestClient) -> None:
    resp = reader_client.get("/users/new")
    assert resp.status_code == 403


def test_create_user_via_web(admin_client: TestClient, db: Database, secrets: AppSecrets) -> None:
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        "/users/new",
        data={
            "csrf_token": csrf,
            "username": "newop",
            "password": "NewOp12345!X",
            "role": "operator",
        },
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/users?msg=criado"


def test_create_user_duplicate_name(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    from backuplc.auth.service import create_user

    create_user(db, "dupuser", "DupUser1234!", "reader")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        "/users/new",
        data={
            "csrf_token": csrf,
            "username": "dupuser",
            "password": "DupUser5678!Y",
            "role": "reader",
        },
    )
    assert resp.status_code == 200
    assert "Já existe" in resp.text


def test_create_user_missing_username(admin_client: TestClient, secrets: AppSecrets) -> None:
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        "/users/new",
        data={
            "csrf_token": csrf,
            "username": "",
            "password": "SomePass1234!",
            "role": "reader",
        },
    )
    assert resp.status_code == 200
    assert "obrigatório" in resp.text


def test_operator_can_collect(
    admin_client: TestClient,
    db: Database,
    settings: Settings,
    secrets: AppSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perfil operador pode disparar coleta manual."""
    from backuplc.auth.service import create_session, create_user, make_csrf_token
    from backuplc.core.migrate import upgrade
    from backuplc.devices.service import create_credential, create_device
    from backuplc.web.app import create_app

    upgrade(db)
    cred = create_credential(db, secrets.master_key, "cred-op", "u", "SenhaOp12!", "")
    dev = create_device(db, "sw-op", "10.9.9.1", "generic", 22, cred.id, True)

    monkeypatch.setattr(
        "backuplc.collector.runner._connect_and_collect",
        lambda *a, **kw: (None, "config ok\nconfig ok\n" * 10, "ssh-rsa", "AAAA"),
    )

    op = create_user(db, "operator1", "OperSenha12!X", "operator")
    sid = create_session(db, op.id)
    csrf = make_csrf_token(sid, secrets.session_secret)

    with TestClient(create_app(settings, secrets, db), follow_redirects=False) as c:
        c.cookies.set("session_id", sid)
        resp = c.post(f"/devices/{dev.id}/collect", data={"csrf_token": csrf})
    assert resp.status_code == 303


def test_reader_cannot_collect_403(
    reader_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    from backuplc.devices.service import create_credential, create_device

    cred = create_credential(db, secrets.master_key, "cred-rd", "u", "SenhaRd12!", "")
    dev = create_device(db, "sw-rd", "10.8.8.1", "generic", 22, cred.id, True)
    csrf = _get_csrf(reader_client, secrets)
    resp = reader_client.post(f"/devices/{dev.id}/collect", data={"csrf_token": csrf})
    assert resp.status_code == 403


def test_reader_cannot_collect_all_403(reader_client: TestClient, secrets: AppSecrets) -> None:
    csrf = _get_csrf(reader_client, secrets)
    resp = reader_client.post("/devices/collect-all", data={"csrf_token": csrf})
    assert resp.status_code == 403


def test_edit_user_role(admin_client: TestClient, db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user, get_user

    u = create_user(db, "edit-me", "EditMe1234!X", "reader")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        f"/users/{u.id}/edit",
        data={
            "csrf_token": csrf,
            "username": "edit-me",
            "role": "operator",
            "is_active": "1",
        },
    )
    assert resp.status_code == 303
    updated = get_user(db, u.id)
    assert updated is not None
    assert updated.role == "operator"


def test_cannot_delete_self(admin_client: TestClient, db: Database) -> None:
    from backuplc.auth.service import list_users

    users = list_users(db)
    admin = next(u for u in users if u.username == "admin")
    resp = admin_client.get(f"/users/{admin.id}/delete")
    assert resp.status_code in (302, 303)


def test_change_password_via_web(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    from backuplc.auth.service import create_user

    u = create_user(db, "pw-user", "PwUser1234!X", "reader")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        f"/users/{u.id}/password",
        data={
            "csrf_token": csrf,
            "password": "NewPwUser5678!Y",
            "confirm": "NewPwUser5678!Y",
        },
    )
    assert resp.status_code == 303


def test_password_mismatch(admin_client: TestClient, db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user

    u = create_user(db, "mismatch-u", "Mismatch12!X", "reader")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        f"/users/{u.id}/password",
        data={
            "csrf_token": csrf,
            "password": "NewSenha1234!",
            "confirm": "DifferentXXX1!",
        },
    )
    assert resp.status_code == 200
    assert "não coincidem" in resp.text


def test_delete_user_via_web(admin_client: TestClient, db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import create_user, get_user

    u = create_user(db, "to-delete", "ToDelete1234!X", "reader")
    # GET shows confirm page
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.get(f"/users/{u.id}/delete")
    assert resp.status_code == 200
    assert "Confirmar" in resp.text
    # POST deletes
    resp2 = admin_client.post(f"/users/{u.id}/delete", data={"csrf_token": csrf})
    assert resp2.status_code == 303
    assert get_user(db, u.id) is None


def test_edit_user_404(admin_client: TestClient, secrets: AppSecrets) -> None:
    resp = admin_client.get("/users/nonexistent-id/edit")
    assert resp.status_code == 404


def test_password_change_404(admin_client: TestClient, secrets: AppSecrets) -> None:
    resp = admin_client.get("/users/nonexistent-id/password")
    assert resp.status_code == 404


def test_users_nav_shown_for_admin(admin_client: TestClient) -> None:
    resp = admin_client.get("/")
    assert resp.status_code == 200
    assert "/users" in resp.text


def test_users_nav_not_shown_for_reader(reader_client: TestClient) -> None:
    resp = reader_client.get("/devices")
    assert resp.status_code == 200
    # Nav link to /users should not appear for reader
    # The reader should NOT see the Usuários nav item
    import re

    nav_links = re.findall(r'href="/users"', resp.text)
    assert len(nav_links) == 0


def test_role_labels_on_list(admin_client: TestClient, db: Database, secrets: AppSecrets) -> None:
    from backuplc.auth.service import list_users

    users = list_users(db)
    admin = next(u for u in users if u.username == "admin")
    _ = admin  # used to verify admin exists
    resp = admin_client.get("/users")
    assert resp.status_code == 200
    assert "Administrador" in resp.text


def test_cannot_self_deactivate(
    admin_client: TestClient, db: Database, secrets: AppSecrets
) -> None:
    from backuplc.auth.service import list_users

    users = list_users(db)
    admin = next(u for u in users if u.username == "admin")
    csrf = _get_csrf(admin_client, secrets)
    resp = admin_client.post(
        f"/users/{admin.id}/edit",
        data={
            "csrf_token": csrf,
            "username": "admin",
            "role": "admin",
            "is_active": "",  # not "1" means False
        },
    )
    assert resp.status_code == 200
    assert "desativar" in resp.text
