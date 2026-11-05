"""SQLite em modo WAL com SQLAlchemy 2 (ADR-003)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, MetaData, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_FILENAME = "backuplc.db"

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _on_connect(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class Database:
    """Acesso ao banco. Camadas web e de domínio usam esta classe, nunca o engine direto."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / DB_FILENAME
        self.engine: Engine = create_engine(
            f"sqlite:///{self.path}", connect_args={"check_same_thread": False}
        )
        event.listen(self.engine, "connect", _on_connect)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Sessão com transação: confirma ao sair, desfaz em caso de erro."""
        with self._sessions() as session, session.begin():
            yield session

    def ping(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return False
        return True

    def dispose(self) -> None:
        self.engine.dispose()
