"""Verificações de prontidão (Spec E1, item 6)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from backuplc.core.db import Database
from backuplc.core.migrate import schema_is_current


def storage_writable(data_dir: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=data_dir, prefix=".ready-") as fh:
            fh.write(b"ok")
            fh.flush()
    except OSError:
        return False
    return True


def readiness(db: Database, data_dir: Path) -> dict[str, bool]:
    database = db.ping()
    return {
        "database": database,
        "schema": database and schema_is_current(db),
        "storage": storage_writable(data_dir),
    }
