"""Rotas da interface web (E2 a E7)."""

from __future__ import annotations

import asyncio
import math
from datetime import UTC, datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from backuplc.core.health import readiness
from backuplc.web.templating import templates

router = APIRouter()

PAGE_SIZE = 20
DEVICE_TYPES = [("generic", "Genérico (SSH padrão)"), ("mikrotik_routeros", "MikroTik RouterOS")]
ROLES = [("admin", "Administrador"), ("operator", "Operador"), ("reader", "Leitor")]
ROLE_LABELS = {"admin": "Administrador", "operator": "Operador", "reader": "Leitor"}
EXECUTION_STATUSES = [
    "ok",
    "running",
    "CONEXAO",
    "AUTENTICACAO",
    "TIMEOUT",
    "SAIDA_INVALIDA",
    "CHAVE_HOST",
    "ERRO_INTERNO",
]
CHECK_LABELS = {
    "database": "Banco de dados",
    "schema": "Migrações em dia",
    "storage": "Armazenamento gravável",
}

# Mantém referências a tasks fire-and-forget para evitar coleta pelo GC.
_background_tasks: set[asyncio.Task[None]] = set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf(request: Request, csrf_token: str) -> None:
    """Valida CSRF; levanta 403 se inválido."""
    from backuplc.auth.service import verify_csrf_token

    session_id = request.cookies.get("session_id", "")
    if not verify_csrf_token(csrf_token, session_id, request.app.state.secrets.session_secret):
        raise HTTPException(status_code=403)


def _admin(request: Request) -> None:
    if request.state.user.role != "admin":
        raise HTTPException(status_code=403)


def _admin_or_operator(request: Request) -> None:
    if request.state.user.role not in ("admin", "operator"):
        raise HTTPException(status_code=403)


def _t(
    request: Request, template: str, ctx: dict[str, object], status_code: int = 200
) -> HTMLResponse:
    return templates.TemplateResponse(request, template, ctx, status_code=status_code)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready(request: Request) -> JSONResponse:
    checks = readiness(request.app.state.db, request.app.state.settings.data_dir)
    ok = all(checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "fail", "checks": checks},
        status_code=200 if ok else 503,
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request, next: str = "/") -> HTMLResponse:
    return _t(request, "login.html", {"next": next})


@router.post("/login")
async def login_post(
    request: Request,
    username: str = Form(),
    password: str = Form(),
    next: str = Form(default="/"),
) -> Response:
    from backuplc.auth.service import create_session, login, safe_next

    db = request.app.state.db
    settings = request.app.state.settings
    result, user = login(db, username, password)

    if result == "account_locked":
        return _t(
            request,
            "login.html",
            {"next": next, "error": "Conta bloqueada. Tente novamente em alguns minutos."},
        )
    if result != "ok" or user is None:
        return _t(request, "login.html", {"next": next, "error": "Credenciais inválidas."})

    session_id = create_session(db, user.id)
    secure = settings.environment == "production"
    redirect_to = safe_next(next)
    response = RedirectResponse(redirect_to, status_code=303)
    response.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        samesite="lax",
        secure=secure,
    )
    return response


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form()) -> Response:
    _csrf(request, csrf_token)
    from backuplc.auth.service import delete_session

    session_id = request.cookies.get("session_id", "")
    if session_id:
        delete_session(request.app.state.db, session_id)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_id")
    return response


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
def dashboard_redirect(request: Request) -> Response:
    return RedirectResponse("/", status_code=302)


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    from backuplc.core.db import utcnow
    from backuplc.dashboard.charts import render_donut, render_hbars, render_trend_bars
    from backuplc.dashboard.health import compute_health

    db = request.app.state.db
    settings = request.app.state.settings
    now = utcnow()
    dash = compute_health(db, now)
    checks_raw = readiness(db, settings.data_dir)
    checks = [{"label": CHECK_LABELS[k], "ok": v} for k, v in checks_raw.items()]
    failures_items = sorted(dash.failures_by_class.items(), key=lambda x: -x[1])
    return _t(
        request,
        "home.html",
        {
            "active": "dashboard",
            "dash": dash,
            "donut_svg": render_donut(dash.pct_healthy),
            "trend_bars_svg": render_trend_bars(dash.trend_days),
            "hbars_svg": render_hbars(failures_items) if failures_items else "",
            "checks": checks,
            "platform_ok": all(checks_raw.values()),
        },
    )


# ---------------------------------------------------------------------------
# Users (admin only)
# ---------------------------------------------------------------------------


@router.get("/users", response_class=HTMLResponse)
def users_list(request: Request, msg: str = "") -> HTMLResponse:
    _admin(request)
    from backuplc.auth.service import list_users

    users = list_users(request.app.state.db)
    return _t(
        request,
        "users/list.html",
        {"active": "users", "users": users, "msg": msg, "role_labels": ROLE_LABELS},
    )


@router.get("/users/new", response_class=HTMLResponse)
def users_new_get(request: Request) -> HTMLResponse:
    _admin(request)
    return _t(
        request,
        "users/form.html",
        {"active": "users", "editing": False, "user": None, "roles": ROLES, "errors": []},
    )


@router.post("/users/new")
def users_new_post(
    request: Request,
    csrf_token: str = Form(),
    username: str = Form(default=""),
    role: str = Form(),
    password: str = Form(default=""),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.auth.service import create_user, validate_password_policy
    from backuplc.core.errors import DuplicateError

    errors: list[str] = []
    if not username.strip():
        errors.append("Nome de usuário é obrigatório.")
    try:
        validate_password_policy(password)
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        return _t(
            request,
            "users/form.html",
            {"active": "users", "editing": False, "user": None, "roles": ROLES, "errors": errors},
        )

    try:
        create_user(request.app.state.db, username, password, role)
    except DuplicateError:
        errors.append(f"Já existe um usuário com o nome '{username}'.")
        return _t(
            request,
            "users/form.html",
            {"active": "users", "editing": False, "user": None, "roles": ROLES, "errors": errors},
        )
    return RedirectResponse("/users?msg=criado", status_code=303)


@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
def users_edit_get(user_id: str, request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.auth.service import get_user

    user = get_user(request.app.state.db, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    return _t(
        request,
        "users/form.html",
        {"active": "users", "editing": True, "user": user, "roles": ROLES, "errors": []},
    )


@router.post("/users/{user_id}/edit")
def users_edit_post(
    user_id: str,
    request: Request,
    csrf_token: str = Form(),
    username: str = Form(),
    role: str = Form(),
    is_active: str = Form(default=""),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.auth.service import get_user, update_user

    db = request.app.state.db
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    if user_id == request.state.user.id and is_active != "1":
        return _t(
            request,
            "users/form.html",
            {
                "active": "users",
                "editing": True,
                "user": user,
                "roles": ROLES,
                "errors": ["Você não pode desativar sua própria conta."],
            },
        )
    update_user(db, user_id, username, role, is_active == "1")
    return RedirectResponse("/users?msg=atualizado", status_code=303)


@router.get("/users/{user_id}/password", response_class=HTMLResponse)
def users_password_get(user_id: str, request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.auth.service import get_user

    user = get_user(request.app.state.db, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    return _t(request, "users/password.html", {"active": "users", "user": user, "errors": []})


@router.post("/users/{user_id}/password")
def users_password_post(
    user_id: str,
    request: Request,
    csrf_token: str = Form(),
    password: str = Form(),
    confirm: str = Form(),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.auth.service import change_password, get_user, validate_password_policy

    db = request.app.state.db
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404)

    errors: list[str] = []
    if password != confirm:
        errors.append("As senhas não coincidem.")
    else:
        try:
            validate_password_policy(password)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return _t(
            request, "users/password.html", {"active": "users", "user": user, "errors": errors}
        )

    change_password(db, user_id, password)
    return RedirectResponse("/users?msg=senha_alterada", status_code=303)


@router.get("/users/{user_id}/delete", response_class=HTMLResponse)
def users_delete_get(user_id: str, request: Request) -> Response:
    _admin(request)
    from backuplc.auth.service import get_user

    user = get_user(request.app.state.db, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    if user.id == request.state.user.id:
        return RedirectResponse("/users?msg=erro_self_delete", status_code=303)
    return _t(
        request,
        "confirm_delete.html",
        {
            "active": "users",
            "message": f"Excluir usuário '{user.username}'? Esta ação não pode ser desfeita.",
            "action": f"/users/{user_id}/delete",
            "cancel": "/users",
        },
    )


@router.post("/users/{user_id}/delete")
def users_delete_post(user_id: str, request: Request, csrf_token: str = Form()) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.auth.service import delete_user, get_user

    db = request.app.state.db
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404)
    if user.id == request.state.user.id:
        return RedirectResponse("/users?msg=erro_self_delete", status_code=303)
    delete_user(db, user_id)
    return RedirectResponse("/users?msg=excluido", status_code=303)


# ---------------------------------------------------------------------------
# Credentials (admin only)
# ---------------------------------------------------------------------------


@router.get("/credentials", response_class=HTMLResponse)
def creds_list(request: Request, msg: str = "") -> HTMLResponse:
    _admin(request)
    from backuplc.devices.service import count_devices_for_credential, list_credentials

    db = request.app.state.db
    creds = list_credentials(db)
    counts = {c.id: count_devices_for_credential(db, c.id) for c in creds}
    return _t(
        request,
        "credentials/list.html",
        {"active": "credentials", "creds": creds, "counts": counts, "msg": msg},
    )


@router.get("/credentials/new", response_class=HTMLResponse)
def creds_new_get(request: Request) -> HTMLResponse:
    _admin(request)
    return _t(
        request, "credentials/form.html", {"active": "credentials", "cred": None, "errors": []}
    )


@router.post("/credentials/new")
def creds_new_post(
    request: Request,
    csrf_token: str = Form(),
    name: str = Form(),
    username: str = Form(),
    password: str = Form(),
    description: str = Form(default=""),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.devices.service import create_credential

    db = request.app.state.db
    secrets = request.app.state.secrets
    errors: list[str] = []
    if not name.strip():
        errors.append("Nome é obrigatório.")
    if not username.strip():
        errors.append("Usuário SSH é obrigatório.")
    if not password:
        errors.append("Senha SSH é obrigatória.")
    if errors:
        return _t(
            request,
            "credentials/form.html",
            {
                "active": "credentials",
                "cred": None,
                "errors": errors,
                "form": {"name": name, "username": username, "description": description},
            },
        )

    create_credential(
        db, secrets.master_key, name.strip(), username.strip(), password, description.strip()
    )
    return RedirectResponse("/credentials?msg=criada", status_code=303)


@router.get("/credentials/{cred_id}/edit", response_class=HTMLResponse)
def creds_edit_get(cred_id: str, request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.devices.service import get_credential

    cred = get_credential(request.app.state.db, cred_id)
    if cred is None:
        raise HTTPException(status_code=404)
    return _t(
        request, "credentials/form.html", {"active": "credentials", "cred": cred, "errors": []}
    )


@router.post("/credentials/{cred_id}/edit")
def creds_edit_post(
    cred_id: str,
    request: Request,
    csrf_token: str = Form(),
    name: str = Form(),
    username: str = Form(),
    password: str = Form(default=""),
    description: str = Form(default=""),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.devices.service import get_credential, update_credential

    db = request.app.state.db
    cred = get_credential(db, cred_id)
    if cred is None:
        raise HTTPException(status_code=404)
    secrets = request.app.state.secrets
    update_credential(
        db,
        secrets.master_key,
        cred_id,
        name.strip(),
        username.strip(),
        password or None,
        description.strip(),
    )
    return RedirectResponse("/credentials?msg=atualizada", status_code=303)


@router.get("/credentials/{cred_id}/delete", response_class=HTMLResponse)
def creds_delete_get(cred_id: str, request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.devices.service import count_devices_for_credential, get_credential

    db = request.app.state.db
    cred = get_credential(db, cred_id)
    if cred is None:
        raise HTTPException(status_code=404)
    if count_devices_for_credential(db, cred_id) > 0:
        raise HTTPException(status_code=409)
    return _t(
        request,
        "confirm_delete.html",
        {
            "active": "credentials",
            "message": f"Excluir credencial '{cred.name}'? Esta ação não pode ser desfeita.",
            "action": f"/credentials/{cred_id}/delete",
            "cancel": "/credentials",
        },
    )


@router.post("/credentials/{cred_id}/delete")
def creds_delete_post(cred_id: str, request: Request, csrf_token: str = Form()) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.devices.service import (
        count_devices_for_credential,
        delete_credential,
        get_credential,
    )

    db = request.app.state.db
    cred = get_credential(db, cred_id)
    if cred is None:
        raise HTTPException(status_code=404)
    if count_devices_for_credential(db, cred_id) > 0:
        raise HTTPException(status_code=409)
    delete_credential(db, cred_id)
    return RedirectResponse("/credentials?msg=excluida", status_code=303)


# ---------------------------------------------------------------------------
# Devices — rota literal antes da parametrizada
# ---------------------------------------------------------------------------


@router.post("/devices/collect-all")
async def devices_collect_all(request: Request, csrf_token: str = Form()) -> Response:
    _csrf(request, csrf_token)
    _admin_or_operator(request)

    from backuplc.devices.service import list_devices
    from backuplc.scheduler.runner import run_all_devices

    db = request.app.state.db
    settings = request.app.state.settings
    secrets = request.app.state.secrets
    active_count = sum(1 for d in list_devices(db) if d.is_active)

    task = asyncio.create_task(
        run_all_devices(db, settings.data_dir, secrets.master_key, settings.max_concurrent)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return RedirectResponse(f"/devices?msg=coleta_iniciada_{active_count}", status_code=303)


@router.get("/devices/new", response_class=HTMLResponse)
def devices_new_get(request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.devices.service import list_credentials

    creds = list_credentials(request.app.state.db)
    return _t(
        request,
        "devices/form.html",
        {
            "active": "devices",
            "device": None,
            "creds": creds,
            "device_types": DEVICE_TYPES,
            "errors": [],
        },
    )


@router.post("/devices/new")
def devices_new_post(
    request: Request,
    csrf_token: str = Form(),
    name: str = Form(),
    ip_address: str = Form(),
    device_type: str = Form(),
    ssh_port: str = Form(default="22"),
    credential_id: str = Form(),
    is_active: str = Form(default=""),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.devices.service import create_device, list_credentials

    db = request.app.state.db
    errors: list[str] = []
    try:
        port = int(ssh_port)
    except ValueError:
        errors.append("Porta SSH inválida.")
        port = 22

    if errors:
        creds = list_credentials(db)
        return _t(
            request,
            "devices/form.html",
            {
                "active": "devices",
                "device": None,
                "creds": creds,
                "device_types": DEVICE_TYPES,
                "errors": errors,
                "form": {
                    "name": name,
                    "ip_address": ip_address,
                    "device_type": device_type,
                    "ssh_port": ssh_port,
                    "credential_id": credential_id,
                    "is_active": is_active,
                },
            },
        )

    create_device(
        db, name.strip(), ip_address.strip(), device_type, port, credential_id, is_active == "1"
    )
    return RedirectResponse("/devices?msg=criado", status_code=303)


@router.get("/devices", response_class=HTMLResponse)
def devices_list(request: Request, msg: str = "") -> HTMLResponse:
    from backuplc.devices.service import list_credentials, list_devices

    db = request.app.state.db
    devices = list_devices(db, device_type="generic")
    all_creds = list_credentials(db)
    creds = {c.id: c for c in all_creds}
    return _t(
        request,
        "devices/list.html",
        {"active": "devices", "devices": devices, "creds": creds, "msg": msg, "title": "Switches"},
    )


@router.get("/devices/{device_id}/edit", response_class=HTMLResponse)
def devices_edit_get(device_id: str, request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.devices.service import get_device, list_credentials

    db = request.app.state.db
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404)
    creds = list_credentials(db)
    return _t(
        request,
        "devices/form.html",
        {
            "active": "devices",
            "device": device,
            "creds": creds,
            "device_types": DEVICE_TYPES,
            "errors": [],
        },
    )


@router.post("/devices/{device_id}/edit")
def devices_edit_post(
    device_id: str,
    request: Request,
    csrf_token: str = Form(),
    name: str = Form(),
    ip_address: str = Form(),
    device_type: str = Form(),
    ssh_port: str = Form(default="22"),
    credential_id: str = Form(),
    is_active: str = Form(default=""),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.devices.service import get_device, list_credentials, update_device

    db = request.app.state.db
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404)

    errors: list[str] = []
    try:
        port = int(ssh_port)
    except ValueError:
        errors.append("Porta SSH inválida.")
        port = 22

    if errors:
        creds = list_credentials(db)
        return _t(
            request,
            "devices/form.html",
            {
                "active": "devices",
                "device": device,
                "creds": creds,
                "device_types": DEVICE_TYPES,
                "errors": errors,
            },
        )

    update_device(
        db,
        device_id,
        name.strip(),
        ip_address.strip(),
        device_type,
        port,
        credential_id,
        is_active == "1",
    )
    return RedirectResponse("/devices?msg=atualizado", status_code=303)


@router.get("/devices/{device_id}/delete", response_class=HTMLResponse)
def devices_delete_get(device_id: str, request: Request) -> HTMLResponse:
    _admin(request)
    from backuplc.devices.service import get_device

    device = get_device(request.app.state.db, device_id)
    if device is None:
        raise HTTPException(status_code=404)
    return _t(
        request,
        "confirm_delete.html",
        {
            "active": "devices",
            "message": f"Excluir switch '{device.name}'? As versões de configuração salvas serão mantidas.",
            "action": f"/devices/{device_id}/delete",
            "cancel": "/devices",
        },
    )


@router.post("/devices/{device_id}/delete")
def devices_delete_post(device_id: str, request: Request, csrf_token: str = Form()) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.devices.service import delete_device, get_device

    db = request.app.state.db
    if get_device(db, device_id) is None:
        raise HTTPException(status_code=404)
    delete_device(db, device_id)
    return RedirectResponse("/devices?msg=excluido", status_code=303)


@router.post("/devices/{device_id}/collect")
async def devices_collect(device_id: str, request: Request, csrf_token: str = Form()) -> Response:
    _csrf(request, csrf_token)
    _admin_or_operator(request)

    from backuplc.collector.runner import collect_device
    from backuplc.devices.service import get_device

    db = request.app.state.db
    settings = request.app.state.settings
    secrets = request.app.state.secrets
    actor = request.state.user.id

    if get_device(db, device_id) is None:
        raise HTTPException(status_code=404)

    loop = asyncio.get_running_loop()
    exe = await loop.run_in_executor(
        None, collect_device, db, settings.data_dir, device_id, secrets.master_key, actor, "manual"
    )

    if exe.status == "ok" and exe.version_id is None:
        msg = "coletado_sem_versao"
    elif exe.status == "ok":
        msg = "coletado_ok"
    else:
        msg = exe.status

    return RedirectResponse(f"/devices/{device_id}?msg={msg}", status_code=303)


@router.get("/devices/{device_id}/versions/{version_id}/download")
def devices_download(device_id: str, version_id: str, request: Request) -> Response:
    from backuplc.collector.service import get_version
    from backuplc.devices.service import get_device

    db = request.app.state.db
    settings = request.app.state.settings

    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404)

    version = get_version(db, version_id)
    if version is None or version.device_id != device_id:
        raise HTTPException(status_code=404)

    file_path = settings.data_dir / version.file_path
    try:
        content = file_path.read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404) from exc

    ts = version.collected_at.strftime("%Y%m%d_%H%M%S")
    filename = f"{device.name}_{ts}.txt"
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/devices/{device_id}/versions/{older_id}/diff/{newer_id}", response_class=HTMLResponse)
def devices_diff(device_id: str, older_id: str, newer_id: str, request: Request) -> HTMLResponse:
    from backuplc.collector.service import get_version
    from backuplc.devices.service import get_device
    from backuplc.storage.diff import compute_diff

    db = request.app.state.db
    settings = request.app.state.settings

    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404)

    ver_a = get_version(db, older_id)
    ver_b = get_version(db, newer_id)

    if ver_a is None or ver_a.device_id != device_id:
        raise HTTPException(status_code=404)
    if ver_b is None or ver_b.device_id != device_id:
        raise HTTPException(status_code=404)

    try:
        text_a = (settings.data_dir / ver_a.file_path).read_text(encoding="utf-8", errors="replace")
        text_b = (settings.data_dir / ver_b.file_path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404) from exc

    diff = compute_diff(text_a, text_b)
    return _t(
        request,
        "devices/diff.html",
        {"active": "devices", "device": device, "ver_a": ver_a, "ver_b": ver_b, "diff": diff},
    )


@router.get("/devices/{device_id}/restore", response_class=HTMLResponse)
def devices_restore(device_id: str, request: Request, date: str = "") -> HTMLResponse:
    from backuplc.collector.service import list_versions_by_date
    from backuplc.devices.service import get_device

    db = request.app.state.db
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    versions = []
    selected_date_fmt = ""
    if date:
        versions = list_versions_by_date(db, device_id, date)
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            selected_date_fmt = dt.strftime("%d/%m/%Y")
        except ValueError:
            date = ""

    return _t(
        request,
        "devices/restore.html",
        {
            "active": "devices",
            "device": device,
            "selected_date": date,
            "selected_date_fmt": selected_date_fmt,
            "today": today,
            "versions": versions,
        },
    )


@router.post("/devices/{device_id}/reset-host-key")
def devices_reset_host_key(device_id: str, request: Request, csrf_token: str = Form()) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.collector.service import delete_host_key
    from backuplc.devices.service import get_device

    db = request.app.state.db
    if get_device(db, device_id) is None:
        raise HTTPException(status_code=404)
    delete_host_key(db, device_id)
    return RedirectResponse(f"/devices/{device_id}", status_code=303)


@router.get("/devices/{device_id}", response_class=HTMLResponse)
def devices_detail(
    device_id: str,
    request: Request,
    page: int = 1,
    status: str = "",
    msg: str = "",
) -> HTMLResponse:
    from backuplc.collector.service import (
        count_executions,
        get_host_key,
        list_executions,
        list_versions,
    )
    from backuplc.devices.service import get_credential, get_device

    db = request.app.state.db
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404)

    cred = get_credential(db, device.credential_id) if device.credential_id else None
    cred_name = cred.name if cred else "—"
    host_key = get_host_key(db, device_id)
    versions = list_versions(db, device_id)
    status_filter = status or None
    total = count_executions(db, device_id, status_filter)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    executions = list_executions(
        db, device_id, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE, status_filter=status_filter
    )

    return _t(
        request,
        "devices/detail.html",
        {
            "active": "devices",
            "device": device,
            "cred_name": cred_name,
            "host_key": host_key,
            "versions": versions,
            "executions": executions,
            "execution_statuses": EXECUTION_STATUSES,
            "page": page,
            "total_pages": total_pages,
            "status_filter": status,
            "msg": msg,
        },
    )


# ---------------------------------------------------------------------------
# MikroTik
# ---------------------------------------------------------------------------


@router.post("/mikrotik/collect-all")
async def mikrotik_collect_all(request: Request, csrf_token: str = Form()) -> Response:
    _csrf(request, csrf_token)
    _admin_or_operator(request)

    from backuplc.devices.service import list_devices
    from backuplc.scheduler.runner import run_all_devices

    db = request.app.state.db
    settings = request.app.state.settings
    secrets = request.app.state.secrets
    active_count = sum(1 for d in list_devices(db, device_type="mikrotik_routeros") if d.is_active)

    task = asyncio.create_task(
        run_all_devices(db, settings.data_dir, secrets.master_key, settings.max_concurrent)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return RedirectResponse(f"/mikrotik?msg=coleta_iniciada_{active_count}", status_code=303)


@router.get("/mikrotik", response_class=HTMLResponse)
def mikrotik_list(request: Request, msg: str = "") -> HTMLResponse:
    from backuplc.devices.service import list_credentials, list_devices

    db = request.app.state.db
    devices = list_devices(db, device_type="mikrotik_routeros")
    all_creds = list_credentials(db)
    creds = {c.id: c for c in all_creds}
    return _t(
        request,
        "devices/list.html",
        {"active": "mikrotik", "devices": devices, "creds": creds, "msg": msg, "title": "MikroTik"},
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/history", response_class=HTMLResponse)
def history_list(request: Request, page: int = 1, trigger: str = "") -> HTMLResponse:
    from backuplc.history.service import count_cycles, get_cycles

    db = request.app.state.db
    trigger_filter = trigger
    total = count_cycles(db, trigger_filter)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    cycles = get_cycles(db, page=page, per_page=PAGE_SIZE, trigger_filter=trigger_filter)
    return _t(
        request,
        "history/index.html",
        {
            "active": "history",
            "cycles": cycles,
            "page": page,
            "total_pages": total_pages,
            "trigger_filter": trigger,
        },
    )


@router.get("/history/detail", response_class=HTMLResponse)
def history_detail(request: Request, key: str = "", trigger: str = "") -> HTMLResponse:
    from backuplc.history.service import get_cycle_executions

    db = request.app.state.db
    executions = get_cycle_executions(db, key, trigger)
    if not executions:
        raise HTTPException(status_code=404)

    started_at = executions[0].started_at
    return _t(
        request,
        "history/detail.html",
        {
            "active": "history",
            "executions": executions,
            "started_at": started_at,
            "trigger": trigger,
            "trigger_filter": trigger,
        },
    )


# ---------------------------------------------------------------------------
# Settings (admin only)
# ---------------------------------------------------------------------------


@router.get("/settings", response_class=HTMLResponse)
def settings_get(request: Request, msg: str = "") -> HTMLResponse:
    _admin(request)
    from backuplc.core.settings_store import get_schedule_cron

    db = request.app.state.db
    settings = request.app.state.settings
    cron = get_schedule_cron(db)

    # Extrai hora e minuto do cron "M H * * *"
    parts = cron.split()
    try:
        current_minute = int(parts[0])
        current_hour = int(parts[1])
    except (IndexError, ValueError):
        current_minute = 0
        current_hour = 2

    # Próxima execução via scheduler
    next_run = None
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        for job in scheduler.get_jobs():
            if job.id == "run_all_devices" and job.next_run_time is not None:
                next_run = job.next_run_time
                break

    return _t(
        request,
        "settings/index.html",
        {
            "active": "settings",
            "cron": cron,
            "current_hour": current_hour,
            "current_minute": current_minute,
            "next_run": next_run,
            "timezone": settings.timezone,
            "hours": list(range(24)),
            "minutes": [0, 15, 30, 45],
            "msg": msg,
        },
    )


@router.post("/settings")
def settings_post(
    request: Request,
    csrf_token: str = Form(),
    hour: str = Form(),
    minute: str = Form(),
) -> Response:
    _admin(request)
    _csrf(request, csrf_token)
    from backuplc.core.settings_store import set_schedule_cron

    db = request.app.state.db
    settings_obj = request.app.state.settings
    errors: list[str] = []

    try:
        h = int(hour)
    except ValueError:
        h = -1
    try:
        m = int(minute)
    except ValueError:
        m = -1

    if h < 0 or h > 23:
        errors.append("Hora deve ser entre 0 e 23.")
    if m not in (0, 15, 30, 45):
        errors.append("Minuto deve ser 0, 15, 30 ou 45.")

    if errors:
        from backuplc.core.settings_store import get_schedule_cron

        cron = get_schedule_cron(db)
        scheduler = getattr(request.app.state, "scheduler", None)
        next_run = None
        if scheduler is not None:
            for job in scheduler.get_jobs():
                if job.id == "run_all_devices" and job.next_run_time is not None:
                    next_run = job.next_run_time
                    break
        return _t(
            request,
            "settings/index.html",
            {
                "active": "settings",
                "cron": cron,
                "current_hour": h if 0 <= h <= 23 else 2,
                "current_minute": m if m in (0, 15, 30, 45) else 0,
                "next_run": next_run,
                "timezone": settings_obj.timezone,
                "hours": list(range(24)),
                "minutes": [0, 15, 30, 45],
                "errors": errors,
            },
            status_code=422,
        )

    new_cron = f"{m} {h} * * *"
    set_schedule_cron(db, new_cron)

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None:
        scheduler.reschedule_job(
            "run_all_devices",
            trigger="cron",
            hour=h,
            minute=m,
            timezone=settings_obj.timezone,
        )

    return RedirectResponse("/settings?msg=salvo", status_code=303)
