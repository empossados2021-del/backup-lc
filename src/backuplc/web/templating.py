from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from backuplc import __version__

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _filesize(value: int) -> str:
    """Converte bytes em string legível (B / KB / MB)."""
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["app_version"] = __version__
templates.env.filters["filesize"] = _filesize
