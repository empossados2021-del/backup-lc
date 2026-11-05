"""Ambiente Alembic: recebe a conexão de backuplc.core.migrate."""

from alembic import context
from sqlalchemy.engine import Connection

from backuplc.core import events as _events  # noqa: F401  (registra os modelos)
from backuplc.core.db import Base


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


_connection = context.config.attributes.get("connection")
if _connection is None:
    raise RuntimeError("Execute as migrações por 'python -m backuplc migrate'.")
_run(_connection)
