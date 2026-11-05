from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backuplc import __version__
from backuplc.core.config import AppSecrets, Settings
from backuplc.core.db import Database
from backuplc.web.middleware import RequestContextMiddleware
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


def create_app(settings: Settings, secrets: AppSecrets, db: Database) -> FastAPI:
    # Sem Swagger/ReDoc: carregariam JavaScript no navegador (R-03).
    app = FastAPI(
        title="backup-lc", version=__version__, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.settings = settings
    app.state.secrets = secrets
    app.state.db = db
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)
    return app
