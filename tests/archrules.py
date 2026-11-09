"""Regras de dependência entre módulos (E1-09)."""

from __future__ import annotations

import ast
from pathlib import Path

DOMAIN = (
    "backuplc.web",
    "backuplc.auth",
    "backuplc.devices",
    "backuplc.collector",
    "backuplc.storage",
    "backuplc.scheduler",
    "backuplc.dashboard",
    "backuplc.cli",
)

# módulo -> importações proibidas
RULES: dict[str, tuple[str, ...]] = {
    # O núcleo não conhece o domínio nem a web.
    "backuplc.core": DOMAIN,
    # Coletores não acessam web, auth, agendador, dashboard nem CLI.
    # Podem usar SQLAlchemy (modelos ORM) e backuplc.storage (persistência de config).
    "backuplc.collector": (
        "backuplc.web",
        "backuplc.auth",
        "backuplc.scheduler",
        "backuplc.dashboard",
        "backuplc.cli",
    ),
    # Rotas não acessam o banco diretamente.
    "backuplc.web": ("sqlalchemy", "backuplc.cli"),
}


def _module_name(path: Path, src_root: Path) -> str:
    parts = list(path.relative_to(src_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path, module: str) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                name = ".".join([*base, node.module] if node.module else base)
            else:
                name = node.module or ""
            found.append((node.lineno, name))
    return found


def _matches(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def violations(src_root: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(src_root.rglob("*.py")):
        module = _module_name(path, src_root)
        for owner, forbidden in RULES.items():
            if not _matches(module, owner):
                continue
            for lineno, imported in _imports(path, module):
                if any(_matches(imported, f) for f in forbidden):
                    rel = path.relative_to(src_root)
                    problems.append(f"{rel}:{lineno}: {module} não pode importar {imported}")
    return problems
