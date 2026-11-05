"""E1-09: importações proibidas entre módulos fazem a verificação falhar."""

from __future__ import annotations

from pathlib import Path

import pytest

from archrules import violations

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parent.parent / "src"


def test_codigo_respeita_regras_de_dependencia() -> None:
    assert violations(SRC) == []


def test_regra_detecta_importacao_proibida(tmp_path: Path) -> None:
    core = tmp_path / "backuplc" / "core"
    core.mkdir(parents=True)
    (tmp_path / "backuplc" / "__init__.py").write_text("")
    (core / "__init__.py").write_text("")
    (core / "ruim.py").write_text("from backuplc.web.app import create_app\n")
    web = tmp_path / "backuplc" / "web"
    web.mkdir()
    (web / "__init__.py").write_text("")
    (web / "rota.py").write_text("import os\nfrom sqlalchemy import text\n")

    problemas = violations(tmp_path)
    assert len(problemas) == 2
    assert any("core/ruim.py:1" in p and "backuplc.web.app" in p for p in problemas)
    assert any("web/rota.py:2" in p and "sqlalchemy" in p for p in problemas)
