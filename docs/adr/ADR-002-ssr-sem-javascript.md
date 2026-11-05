# ADR-002 — HTML renderizado no servidor, sem JavaScript

**Status:** Aceita · 2026-11-04

**Contexto:** Regra R-03: nenhum processamento no frontend. O dashboard precisa ser bonito e se atualizar sozinho.

**Decisão:** Páginas Jinja2 com CSS próprio. Gráficos em SVG gerado no servidor. Atualização por `<meta http-equiv="refresh">`. Formulários HTML comuns (POST + redirecionamento). CSP com `script-src 'none'`. Nenhuma biblioteca JavaScript, nem HTMX.

**Alternativas:** HTMX (pequeno, mas ainda é JavaScript no navegador); SPA (contraria R-03).

**Consequências:** Toda interação recarrega a página ou um trecho via formulário. Um teste garante que nenhum HTML contém `<script>` ou atributos `on*`. Interações ricas (arrastar, gráficos interativos) ficam fora.
