"""Migrações Alembic executadas pela aplicação (sem alembic.ini)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.exc import SQLAlchemyError

from backuplc.core.db import Database

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def upgrade(db: Database, revision: str = "head") -> None:
    cfg = _config()
    with db.engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, revision)


def downgrade(db: Database, revision: str) -> None:
    cfg = _config()
    with db.engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, revision)


def head_revision() -> str | None:
    return ScriptDirectory.from_config(_config()).get_current_head()


def current_revision(db: Database) -> str | None:
    with db.engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def schema_is_current(db: Database) -> bool:
    try:
        return current_revision(db) == head_revision()
    except SQLAlchemyError:
        return False
