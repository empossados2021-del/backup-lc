"""Diff unificado entre duas versões de configuração (Spec E3, item 2.2)."""

from __future__ import annotations

import difflib


def compute_diff(text_a: str, text_b: str) -> str:
    """Retorna diff unificado entre text_a (anterior) e text_b (atual)."""
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    return "".join(difflib.unified_diff(lines_a, lines_b, fromfile="anterior", tofile="atual"))
