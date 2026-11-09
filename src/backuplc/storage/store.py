"""Armazenamento e deduplicação de configurações (Spec E3, item 2.2)."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from backuplc.core.db import Database, utcnow
from backuplc.storage.models import ConfigVersion


def _normalize(raw: str, volatile_patterns: list[re.Pattern[str]]) -> str:
    """Remove linhas que casam com padrões voláteis."""
    if not volatile_patterns:
        return raw
    lines: list[str] = []
    for line in raw.splitlines(keepends=True):
        if not any(p.search(line) for p in volatile_patterns):
            lines.append(line)
    return "".join(lines)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def save_config(
    db: Database,
    data_dir: Path,
    device_id: str,
    raw_output: str,
    volatile_patterns: list[re.Pattern[str]],
) -> ConfigVersion | None:
    """Salva a configuração; retorna None se o conteúdo normalizado é idêntico à última versão."""
    normalized = _normalize(raw_output, volatile_patterns)
    sha256_norm = _sha256(normalized)

    # Deduplicação: verifica se a última versão do dispositivo tem o mesmo hash normalizado.
    with db.session() as s:
        last: ConfigVersion | None = (
            s.query(ConfigVersion)
            .filter_by(device_id=device_id)
            .order_by(ConfigVersion.collected_at.desc())
            .first()
        )
        if last is not None and last.sha256_norm == sha256_norm:
            return None

    sha256_raw = _sha256(raw_output)
    raw_bytes = raw_output.encode("utf-8")
    size_bytes = len(raw_bytes)

    # Diretório: <data_dir>/configs/<2 primeiros hex>/<sha256_raw>
    prefix = sha256_raw[:2]
    config_dir = data_dir / "configs" / prefix
    config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = config_dir / sha256_raw

    # Gravação atômica com arquivo temporário + rename.
    if not target.exists():
        fd, tmp_path = tempfile.mkstemp(dir=str(config_dir))
        try:
            os.write(fd, raw_bytes)
            os.close(fd)
            os.chmod(tmp_path, 0o600)
            os.rename(tmp_path, str(target))
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None  # pragma: no cover
            if os.path.exists(tmp_path):  # pragma: no cover
                os.unlink(tmp_path)
            raise

    # Caminho relativo a data_dir para gravar no banco.
    rel_path = str(target.relative_to(data_dir))

    now = utcnow()
    version = ConfigVersion(
        device_id=device_id,
        collected_at=now,
        sha256_raw=sha256_raw,
        sha256_norm=sha256_norm,
        file_path=rel_path,
        size_bytes=size_bytes,
    )
    with db.session() as s:
        s.add(version)

    return version
