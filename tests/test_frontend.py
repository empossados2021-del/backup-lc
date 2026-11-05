"""E1-05: zero JavaScript no navegador (R-03) e cabeçalhos de segurança."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from backuplc.web.templating import STATIC_DIR, TEMPLATES_DIR

pytestmark = [pytest.mark.integration, pytest.mark.security]

SCRIPT_TAG = re.compile(r"<\s*script", re.IGNORECASE)
EVENT_ATTR = re.compile(r"<[^>]*\son[a-z]+\s*=", re.IGNORECASE)
JS_URL = re.compile(r"javascript:", re.IGNORECASE)
HTML_PAGES = ["/", "/pagina-inexistente"]


def _assert_sem_js(html: str, origem: str) -> None:
    assert not SCRIPT_TAG.search(html), f"<script> em {origem}"
    assert not EVENT_ATTR.search(html), f"atributo on* em {origem}"
    assert not JS_URL.search(html), f"javascript: em {origem}"


@pytest.mark.parametrize("caminho", HTML_PAGES)
def test_paginas_sem_javascript(client: TestClient, caminho: str) -> None:
    resposta = client.get(caminho)
    assert resposta.headers["content-type"].startswith("text/html")
    _assert_sem_js(resposta.text, caminho)


def test_templates_sem_javascript() -> None:
    for arquivo in TEMPLATES_DIR.rglob("*.html"):
        _assert_sem_js(arquivo.read_text(encoding="utf-8"), arquivo.name)


def test_nenhum_arquivo_js_estatico() -> None:
    assert not list(STATIC_DIR.rglob("*.js"))


def test_estilos_sem_atributo_style(client: TestClient) -> None:
    # A CSP só permite CSS do próprio servidor; style="" inline seria bloqueado.
    assert not re.search(r"\sstyle\s*=", client.get("/").text)


def test_cabecalhos_de_seguranca(client: TestClient) -> None:
    cabecalhos = client.get("/").headers
    csp = cabecalhos["content-security-policy"]
    assert "script-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert cabecalhos["x-frame-options"] == "DENY"
    assert cabecalhos["x-content-type-options"] == "nosniff"
    assert cabecalhos["cache-control"] == "no-store"
    assert "server" not in cabecalhos


def test_dashboard_renderiza_estados(client: TestClient) -> None:
    html = client.get("/").text
    for rotulo in ("Saudável", "Atenção", "Crítico", "Inativo", "Estado da plataforma"):
        assert rotulo in html
    assert 'http-equiv="refresh"' in html


def test_head_na_pagina_inicial(client: TestClient) -> None:
    assert client.head("/").status_code == 200


def test_css_servido(client: TestClient) -> None:
    resposta = client.get("/static/css/app.css")
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/css")


def test_sem_documentacao_interativa(client: TestClient) -> None:
    for caminho in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(caminho).status_code == 404
