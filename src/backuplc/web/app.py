from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backuplc import __version__
from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database
from backuplc.web.middleware import AuthMiddleware, RequestContextMiddleware
from backuplc.web.routes import router
from backuplc.web.templating import STATIC_DIR, templates

ERROR_TITLES = {404: "Página não encontrada", 405: "Método não permitido"}


async def _http_error(request: Request, exc: Exception) -> Response:
    status = exc.status_code if isinstance(exc, StarletteHTTPException) else 500
    if request.url.path.startswith("/health"):
        return JSONResponse({"status": "error"}, status_code=status)
    response: HTMLResponse = templates.TemplateResponse(
        request,
        "error.html",
        {"status": status, "title": ERROR_TITLES.get(status, "Erro")},
        status_code=status,
    )
    return response


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    secrets: AppSecrets = app.state.secrets
    db: Database = app.state.db

    from backuplc.scheduler.service import recover_running_executions

    recover_running_executions(db)

    # APScheduler é opcional: ausente no container de testes (sem rede).
    try:
        import apscheduler as _apscheduler_check  # noqa: F401

        _has_scheduler = True
    except ImportError:
        _has_scheduler = False

    if _has_scheduler:
        from backuplc.core.settings_store import get_schedule_cron
        from backuplc.scheduler.service import scheduler_lifespan

        cron = get_schedule_cron(db)
        async with scheduler_lifespan(
            db,
            settings.data_dir,
            secrets.master_key,
            cron,
            settings.max_concurrent,
            settings.timezone,
            settings.retention_days,
        ) as scheduler:
            app.state.scheduler = scheduler
            yield
    else:
        app.state.scheduler = None
        yield


def create_app(settings: Settings, secrets: AppSecrets, db: Database) -> FastAPI:
    # Sem Swagger/ReDoc: carregariam JavaScript no navegador (R-03).
    app = FastAPI(
        title="backup-lc",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.secrets = secrets
    app.state.db = db
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)
    return app
