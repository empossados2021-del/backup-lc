# ADR-009 — uv, Ruff, mypy, pytest e switch simulado local

**Status:** Aceita · 2026-11-04

**Contexto:** Qualidade sem risco à rede de produção.

**Decisão:** `uv` com `uv.lock` para dependências; Ruff para lint e formatação; mypy em modo estrito no código novo; pytest com marcadores `unit`, `integration` e `security`. A coleta é testada contra um servidor SSH simulado que roda dentro do servidor, em rede Docker interna sem saída.

**Alternativas:** pip + requirements (sem lock confiável); testar em switch real (impacto na rede).

**Consequências:** Testes nunca tocam equipamentos reais. A validação em switch real acontece só no piloto (E6), com aprovação G-4.
