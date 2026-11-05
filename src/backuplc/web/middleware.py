"""Identificador de requisição, log de acesso e cabeçalhos de segurança (Spec E1, item 8)."""

from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backuplc.core.logging import request_id_var

log = logging.getLogger("backuplc.http")

# Regra R-03: o navegador não executa script algum.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'none'",
        "script-src 'none'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid4().hex[:16]
        token = request_id_var.set(request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
            response.headers.update(SECURITY_HEADERS)
            response.headers["X-Request-ID"] = request_id
            if response.headers.get("content-type", "").startswith("text/html"):
                response.headers["Cache-Control"] = "no-store"
            # Somente o caminho: a query string pode carregar dados sensíveis.
            log.info(
                "http",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((perf_counter() - started) * 1000, 1),
                },
            )
            return response
        finally:
            request_id_var.reset(token)
