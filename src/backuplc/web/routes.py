from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from backuplc.core.health import readiness
from backuplc.web.templating import templates

router = APIRouter()

# Estados de saúde do PRD v2.0, seção 5.1 (valores reais chegam na E5).
HEALTH_STATES = [
    {"key": "ok", "label": "Saudável", "hint": "Backup válido em menos de 26 h"},
    {"key": "warn", "label": "Atenção", "hint": "Última falhou ou 26 a 48 h"},
    {"key": "crit", "label": "Crítico", "hint": "Mais de 48 h ou nunca"},
    {"key": "idle", "label": "Inativo", "hint": "Fora da coleta"},
]

CHECK_LABELS = {
    "database": "Banco de dados",
    "schema": "Migrações em dia",
    "storage": "Armazenamento gravável",
}

ROADMAP = [
    ("E2", "Login, usuários e cadastro de switches"),
    ("E3", "Coleta das configurações por SSH"),
    ("E4", "Agendamento, histórico e diferenças"),
    ("E5", "Dashboard de saúde completo"),
]


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


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    checks = readiness(request.app.state.db, request.app.state.settings.data_dir)
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "active": "dashboard",
            "states": HEALTH_STATES,
            "checks": [{"label": CHECK_LABELS[k], "ok": v} for k, v in checks.items()],
            "platform_ok": all(checks.values()),
            "roadmap": ROADMAP,
        },
    )
