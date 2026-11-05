"""Configuração por ambiente e segredos lidos de arquivo (Spec E1, item 2)."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from backuplc.core.errors import ConfigError
from backuplc.core.logging import register_secret

ENV_PREFIX = "BLC_"
MIN_SESSION_SECRET_LEN = 32
FERNET_KEY_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore", frozen=True)

    data_dir: Path = Path("/data")
    session_secret_file: Path
    master_key_file: Path
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Dentro do container; a publicação na rede é controlada pelo compose (ADR-011).
    host: str = "0.0.0.0"  # noqa: S104
    port: int = Field(default=8080, ge=1, le=65535)


@dataclass(frozen=True)
class AppSecrets:
    """Segredos em memória; nunca aparecem em repr, logs ou telas."""

    session_secret: str = field(repr=False)
    master_key: bytes = field(repr=False)


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        problems = []
        for err in exc.errors(include_url=False, include_input=False, include_context=False):
            name = ENV_PREFIX + "_".join(str(part) for part in err["loc"]).upper()
            problems.append(f"{name}: {err['msg']}")
        raise ConfigError("; ".join(problems)) from None


def _read_secret(path: Path, var: str) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise ConfigError(f"{var}: arquivo não encontrado ({path})") from None
    except PermissionError:
        raise ConfigError(f"{var}: sem permissão de leitura ({path})") from None
    except (OSError, UnicodeDecodeError):
        raise ConfigError(f"{var}: arquivo ilegível ({path})") from None
    if not text:
        raise ConfigError(f"{var}: arquivo vazio ({path})")
    return text


def load_secrets(settings: Settings) -> AppSecrets:
    session = _read_secret(settings.session_secret_file, "BLC_SESSION_SECRET_FILE")
    master = _read_secret(settings.master_key_file, "BLC_MASTER_KEY_FILE")
    # Registra antes de validar: nem mesmo um valor inválido pode vazar em log.
    register_secret(session)
    register_secret(master)
    if len(session) < MIN_SESSION_SECRET_LEN:
        raise ConfigError(
            f"BLC_SESSION_SECRET_FILE: segredo muito curto (mínimo {MIN_SESSION_SECRET_LEN} caracteres)"
        )
    try:
        raw = base64.urlsafe_b64decode(master.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError, ValueError):
        raw = b""
    if len(raw) != FERNET_KEY_BYTES:
        raise ConfigError("BLC_MASTER_KEY_FILE: formato inválido (esperada chave Fernet)")
    return AppSecrets(session_secret=session, master_key=master.encode("ascii"))
