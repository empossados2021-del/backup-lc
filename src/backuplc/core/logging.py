"""Logs estruturados em JSON com redação central de segredos (PRD N-05, R-05)."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import threading
from datetime import UTC, datetime
from typing import Any, TextIO

MASK = "***"
LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_SENSITIVE_KEY = re.compile(
    r"pass(word|wd)?|secret|token|api[_-]?key|private[_-]?key|master[_-]?key"
    r"|authorization|cookie|credential",
    re.IGNORECASE,
)
_SENSITIVE_KV = re.compile(
    r"\b(pass(?:word|wd)?|secret|token|api[_-]?key|authorization|cookie)"
    r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)",
    re.IGNORECASE,
)

_registered: set[str] = set()
_lock = threading.Lock()


def register_secret(value: str) -> None:
    """Registra um valor secreto para que nunca apareça literalmente em logs."""
    if len(value) >= 8:
        with _lock:
            _registered.add(value)


def is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY.search(key))


def _mask_registered(text: str) -> str:
    with _lock:
        values = sorted(_registered, key=len, reverse=True)
    for value in values:
        if value in text:
            text = text.replace(value, MASK)
    return text


def _redact_text(text: str) -> str:
    text = _SENSITIVE_KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)
    return _mask_registered(text)


def redact(value: Any) -> Any:
    """Remove segredos de strings, dicionários e listas (recursivo)."""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {str(k): (MASK if is_sensitive_key(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [redact(v) for v in value]
    return value


_STD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
    "color_message",  # cópia com códigos de cor que o uvicorn anexa
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        text = json.dumps(redact(payload), ensure_ascii=False, default=str)
        # Segunda passada: objetos convertidos por default=str também são filtrados.
        return _mask_registered(text)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Configura o logger raiz com saída JSON; logs do uvicorn passam pelo mesmo filtro."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level if level in LEVELS else "INFO")
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    # A verificação de esquema roda a cada health check; o Alembic só fala se houver problema.
    logging.getLogger("alembic").setLevel(logging.WARNING)
