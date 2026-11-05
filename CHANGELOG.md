# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem SemVer.

## [0.1.0] — 2026-11-04 — E1 Fundação e base visual

### Adicionado
- Pacote `backuplc` com comandos `serve`, `migrate`, `check-config` e `init-secrets`.
- Configuração por variáveis `BLC_*`; segredos lidos de arquivo e validados na subida, sem expor valores.
- Logs JSON com identificador de requisição e máscara central de segredos (chaves sensíveis, `chave=valor` e valores registrados).
- SQLite em modo WAL com SQLAlchemy 2 e Alembic; migração inicial com a tabela `events`.
- `/health/live` e `/health/ready` (banco, migrações, armazenamento).
- Base visual sem JavaScript: layout, tema claro/escuro, cores de estado e página inicial com o estado da plataforma.
- Cabeçalhos de segurança (CSP `script-src 'none'`, `X-Frame-Options`, `nosniff`, `no-referrer`).
- Dockerfile multiestágio (uid 10001, raiz somente leitura) e `compose.yaml` publicado em `0.0.0.0:8080` (ADR-012, substitui a ADR-011; configurável por `BLC_BIND`/`BLC_PORT`). Sem TLS e sem login até a E2.
- `scripts/init.sh`, `check.sh`, `fmt.sh`, `lock.sh`; 31 testes (unit, integration, security).
- Runbook de instalação.

### Dependências (travadas em `uv.lock`)
fastapi 0.156.4, starlette 1.9.0, uvicorn 0.54.0, jinja2 3.1.6, python-multipart 0.0.32, sqlalchemy 2.1.5, alembic 1.20.0, pydantic 2.14.1, pydantic-settings 2.16.1, argon2-cffi 25.1.0, cryptography 50.0.2 · dev: pytest 9.1.1, httpx 0.28.1, ruff 0.17.1, mypy 2.4.0 · uv 0.13.7.

## [E0] — 2026-11-04

### Adicionado
- PRD v2.0 simplificado, plano SDD com portões de aprovação, ADR-001 a ADR-011 e spec da E1.
