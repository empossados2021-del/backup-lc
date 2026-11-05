"""Comandos: serve, migrate, check-config, init-secrets."""

from __future__ import annotations

import argparse
import logging
import os
import secrets as pysecrets
from collections.abc import Sequence
from pathlib import Path

from backuplc import __version__
from backuplc.core.config import load_secrets, load_settings
from backuplc.core.errors import ConfigError
from backuplc.core.logging import configure_logging

log = logging.getLogger("backuplc.cli")


def _cmd_check_config(_args: argparse.Namespace) -> int:
    settings = load_settings()
    load_secrets(settings)
    log.info("configuração válida", extra={"data_dir": str(settings.data_dir)})
    return 0


def _cmd_migrate(args: argparse.Namespace) -> int:
    from backuplc.core.db import Database
    from backuplc.core.migrate import current_revision, downgrade, upgrade

    settings = load_settings()
    load_secrets(settings)
    db = Database(settings.data_dir)
    try:
        if args.down:
            downgrade(db, args.down)
        else:
            upgrade(db)
        log.info("migrações aplicadas", extra={"revision": current_revision(db)})
    finally:
        db.dispose()
    return 0


def _cmd_serve(_args: argparse.Namespace) -> int:
    import uvicorn

    from backuplc.core.db import Database
    from backuplc.core.migrate import upgrade
    from backuplc.web.app import create_app

    # Arquivos criados pela aplicação (banco, configurações) só legíveis por ela (N-08).
    os.umask(0o077)
    settings = load_settings()
    secrets = load_secrets(settings)
    configure_logging(settings.log_level)
    db = Database(settings.data_dir)
    upgrade(db)
    app = create_app(settings, secrets, db)
    log.info("iniciando servidor", extra={"version": __version__, "port": settings.port})
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
        server_header=False,
        proxy_headers=False,
    )
    return 0


def _cmd_init_secrets(args: argparse.Namespace) -> int:
    from cryptography.fernet import Fernet

    target = Path(args.dir)
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    values = {
        "session_secret": pysecrets.token_urlsafe(48),
        "master_key": Fernet.generate_key().decode("ascii"),
    }
    for name, value in values.items():
        path = target / name
        if path.exists() and not args.force:
            log.info("segredo mantido", extra={"file": str(path)})
            continue
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(value + "\n")
        path.chmod(0o600)
        log.info("segredo criado", extra={"file": str(path)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backuplc", description="backup-lc")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="aplica migrações e inicia o servidor web").set_defaults(
        func=_cmd_serve
    )
    p_migrate = sub.add_parser("migrate", help="aplica (ou reverte) migrações")
    p_migrate.add_argument("--down", metavar="REVISAO", help="reverte até a revisão indicada")
    p_migrate.set_defaults(func=_cmd_migrate)
    sub.add_parser("check-config", help="valida configuração e segredos").set_defaults(
        func=_cmd_check_config
    )
    p_init = sub.add_parser("init-secrets", help="gera arquivos de segredo (permissão 600)")
    p_init.add_argument("--dir", required=True, help="diretório de destino")
    p_init.add_argument("--force", action="store_true", help="sobrescreve segredos existentes")
    p_init.set_defaults(func=_cmd_init_secrets)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(os.environ.get("BLC_LOG_LEVEL", "INFO"))
    try:
        result: int = args.func(args)
    except ConfigError as exc:
        log.error("configuração inválida", extra={"detail": str(exc)})
        return 2
    return result
