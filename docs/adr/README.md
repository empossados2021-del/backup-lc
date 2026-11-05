# Decisões de arquitetura (ADR)

Formato: contexto, decisão, alternativas e consequências. Uma decisão muda por uma nova ADR que substitui a anterior.

| ADR | Decisão | Status |
| --- | --- | --- |
| [001](ADR-001-python-fastapi.md) | Python 3.13 + FastAPI | Aceita |
| [002](ADR-002-ssr-sem-javascript.md) | HTML renderizado no servidor, sem JavaScript | Aceita |
| [003](ADR-003-sqlite.md) | SQLite (WAL) + SQLAlchemy + Alembic | Aceita |
| [004](ADR-004-netmiko.md) | Netmiko para coleta SSH | Aceita |
| [005](ADR-005-processo-unico.md) | Agendador e coletor no mesmo processo | Aceita |
| [006](ADR-006-credenciais-fernet.md) | Credenciais cifradas com chave em arquivo | Aceita |
| [007](ADR-007-arquivos-sha256.md) | Configurações em arquivos endereçados por SHA-256 | Aceita |
| [008](ADR-008-docker-compose.md) | Docker Compose, container não root | Aceita |
| [009](ADR-009-ferramentas.md) | uv, Ruff, mypy, pytest e switch simulado local | Aceita |
| [010](ADR-010-verificacao-local.md) | Verificação no servidor, sem CI externo | Aceita |
| [011](ADR-011-bind-localhost.md) | Dashboard só em 127.0.0.1 até a definição de acesso | Substituída pela 012 |
| [012](ADR-012-publicacao-0-0-0-0.md) | Dashboard publicado em 0.0.0.0:8080 (sem TLS e sem login até a E2) | Aceita |
