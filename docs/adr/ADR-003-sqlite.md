# ADR-003 — SQLite (WAL) + SQLAlchemy + Alembic

**Status:** Aceita · 2026-11-04

**Contexto:** Um servidor, um processo, até cerca de 200 switches e poucas escritas por minuto. O servidor tem 3,8 GiB de RAM.

**Decisão:** SQLite em modo WAL, `foreign_keys=ON`, acessado por SQLAlchemy 2. Migrações Alembic reversíveis.

**Alternativas:** PostgreSQL (mais um serviço para operar, sem ganho no volume previsto).

**Consequências:** O banco é um arquivo no diretório de dados, copiado junto com os backups. Se o volume crescer muito ou surgirem vários processos escritores, migrar para PostgreSQL por nova ADR; o SQLAlchemy facilita a troca.
