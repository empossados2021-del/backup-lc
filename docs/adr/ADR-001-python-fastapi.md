# ADR-001 — Python 3.13 + FastAPI

**Status:** Aceita · 2026-11-04

**Contexto:** O PRD exige Python e validação de tudo no servidor.

**Decisão:** Python 3.13 com FastAPI, servido por Uvicorn com um único worker.

**Alternativas:** Django (mais pesado do que o escopo pede); Flask (menos validação e tipagem prontas).

**Consequências:** Validação por Pydantic e injeção de dependências para autorização. Um worker evita agendamento duplicado (ADR-005).
