"""Renderização de sparkline SVG para o dashboard (Spec E5)."""

from __future__ import annotations

from backuplc.dashboard.health import DayStatus


def render_sparkline(days: list[DayStatus], labels: list[str] | None = None) -> str:
    """Retorna string SVG com 14 quadrados (days[0]=hoje à direita).

    Cada retângulo usa uma classe CSS (spark-ok, spark-fail, spark-none)
    sem nenhum atributo style= inline.
    """
    # 14 rects, cada 10×16px, gap de 2px → width=166, height=16
    rect_w = 10
    rect_h = 16
    gap = 2
    total_width = 14 * rect_w + 13 * gap  # 166

    parts = [
        f'<svg class="sparkline" viewBox="0 0 {total_width} {rect_h}"'
        f' width="{total_width}" height="{rect_h}" aria-hidden="true">'
    ]

    for i, status in enumerate(days):
        # days[0] é hoje (direita), days[13] é o mais antigo (esquerda)
        # posição x: index 13 é leftmost (x=0), index 0 é rightmost
        col = 13 - i
        x = col * (rect_w + gap)
        css_class = f"spark-{status}"
        label = labels[i] if labels is not None else f"Dia -{i}"
        parts.append(
            f'<rect class="{css_class}" x="{x}" y="0"'
            f' width="{rect_w}" height="{rect_h}" rx="2">'
            f"<title>{label}</title></rect>"
        )

    parts.append("</svg>")
    return "".join(parts)
