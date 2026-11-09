"""Gráficos SVG gerados no servidor (Spec E5, sem JavaScript)."""

from __future__ import annotations

import math


def render_donut(pct: float) -> str:
    """Anel de saúde geral. pct = 0.0–100.0."""
    r = 52
    circumference = 2 * math.pi * r  # ≈ 326.73
    filled = pct / 100.0 * circumference

    if pct >= 80:
        color = "var(--ok)"
    elif pct >= 50:
        color = "var(--warn)"
    else:
        color = "var(--crit)"

    return (
        f'<svg class="chart-donut" viewBox="0 0 140 140"'
        f' aria-label="Saúde: {int(pct)}% de switches saudáveis">'
        f'<circle cx="70" cy="70" r="{r}" fill="none"'
        f' stroke="var(--surface-2)" stroke-width="14"/>'
        f'<circle cx="70" cy="70" r="{r}" fill="none"'
        f' stroke="{color}" stroke-width="14"'
        f' stroke-dasharray="{filled:.1f} {circumference:.1f}"'
        f' stroke-linecap="round"'
        f' transform="rotate(-90 70 70)"/>'
        f'<text x="70" y="63" text-anchor="middle"'
        f' class="chart-donut__pct">{int(pct)}%</text>'
        f'<text x="70" y="82" text-anchor="middle"'
        f' class="chart-donut__label">saud&#225;veis</text>'
        f"</svg>"
    )


def render_trend_bars(days: list[tuple[int, int]]) -> str:
    """Barras empilhadas 30 dias. days[0]=hoje, days[29]=há 29 dias.
    Cada tupla: (ok_count, fail_count)."""
    max_count = max((ok + fail for ok, fail in days), default=0)
    if max_count < 1:
        max_count = 1
    max_bar_height = 70

    parts = [
        '<svg class="chart-trend" viewBox="0 0 450 90" width="100%" preserveAspectRatio="none">'
    ]

    for j in range(30):
        # j=0 → oldest (day[29]), j=29 → today (day[0])
        ok, fail = days[29 - j]
        x = j * 15
        total = ok + fail

        if total == 0:
            parts.append(f'<rect x="{x}" y="77" width="12" height="3" class="chart-bar--none"/>')
        else:
            ok_h = int(ok / max_count * max_bar_height)
            fail_h = int(fail / max_count * max_bar_height)
            if ok_h == 0 and fail_h == 0:
                parts.append(
                    f'<rect x="{x}" y="77" width="12" height="3" class="chart-bar--none"/>'
                )
            else:
                if ok_h > 0:
                    parts.append(
                        f'<rect x="{x}" y="{80 - ok_h - fail_h}"'
                        f' width="12" height="{ok_h}" class="chart-bar--ok"/>'
                    )
                if fail_h > 0:
                    parts.append(
                        f'<rect x="{x}" y="{80 - fail_h}"'
                        f' width="12" height="{fail_h}" class="chart-bar--fail"/>'
                    )

    # Day labels: j=29 (today), j=22 (-7d), j=15 (-14d), j=8 (-21d), j=1 (-28d)
    label_positions = [
        (29, "hoje"),
        (22, "-7d"),
        (15, "-14d"),
        (8, "-21d"),
        (1, "-28d"),
    ]
    for j, label in label_positions:
        tx = j * 15 + 6
        parts.append(
            f'<text x="{tx}" y="89" text-anchor="middle" class="chart-axis-label">{label}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def render_hbars(items: list[tuple[str, int]]) -> str:
    """Barras horizontais para falhas por motivo.
    items = [("CONEXAO", 5), ("AUTENTICACAO", 2), ...]"""
    if not items:
        return '<p class="muted">Sem falhas registradas.</p>'

    sorted_items = sorted(items, key=lambda x: x[1], reverse=True)[:6]
    max_val = sorted_items[0][1] if sorted_items else 1
    if max_val < 1:
        max_val = 1

    bar_max_width = 180
    row_height = 28
    row_gap = 6
    height = len(sorted_items) * (row_height + row_gap)

    parts = [f'<svg class="chart-hbar" viewBox="0 0 300 {height}">']

    for i, (label, count) in enumerate(sorted_items):
        y_top = i * (row_height + row_gap)
        bar_width = max(2, int(count / max_val * bar_max_width))
        parts.append(
            f'<rect x="0" y="{y_top + 6}" width="{bar_width}" height="22"'
            f' class="chart-bar--fail" rx="3"/>'
        )
        parts.append(
            f'<text x="{bar_width + 6}" y="{y_top + 21}" class="chart-hbar__label">{label}</text>'
        )
        parts.append(
            f'<text x="295" y="{y_top + 21}" text-anchor="end"'
            f' class="chart-hbar__count">{count}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
