from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from backuplc import __version__

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["app_version"] = __version__
