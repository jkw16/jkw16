#!/usr/bin/env python3
"""Render the 53-week contribution calendar as an animated SVG.

Reads data/contributions.json (from fetch_contributions.py), draws the
rounded-box calendar with GitHub's palette, a diagonal slide-down reveal
(CSS keyframes — plays once and freezes), a Less→More legend, and a
stats footer. Writes assets/contrib-heatmap.svg.

STATIC=1 emits a frozen frame (no <style>) for local previews.
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = REPO / "data" / "contributions.json"
OUT = REPO / "assets" / "contrib-heatmap.svg"

WIDTH = 860
PAD_LEFT = 40
PAD_RIGHT = 14
GRID_TOP = 30          # gutter for month labels
PITCH = 14.0           # cell pitch (cell + gap)
CELL = PITCH * 0.76
CELL_R = 2.6

PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
BG = "#0d1117"
MUTED = "#8b949e"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

DEFAULT_THRESHOLDS = (1, 3, 6, 9, 12)


def pick_thresholds(active):
    nonz = sorted(active)
    if not nonz:
        return DEFAULT_THRESHOLDS
    def at(frac, fallback):
        idx = min(len(nonz) - 1, max(0, int(frac * (len(nonz) - 1))))
        return max(1, nonz[idx] or fallback)
    t = [at(0.15, 1), at(0.35, 2), at(0.55, 4), at(0.78, 8), at(0.94, 12)]
    for i in range(1, len(t)):
        t[i] = max(t[i], t[i - 1] + 1)
    return tuple(t)


def level(count, thresholds):
    if count <= 0:
        return 0
    for i, bound in enumerate(thresholds, start=1):
        if count <= bound:
            return i
    return len(PALETTE) - 1


def grid_positions(days):
    """Map each day to (col,row) on a Sunday-start 7-row calendar."""
    first = date.fromisoformat(days[0]["date"])
    sunday0 = first
    while (sunday0.weekday() + 1) % 7 != 0:
        sunday0 -= timedelta(days=1)
    positions = []
    for day in days:
        dt = date.fromisoformat(day["date"])
        col = (dt - sunday0).days // 7
        row = (dt.weekday() + 1) % 7
        positions.append((col, row, day["count"], day["date"]))
    return positions


def month_labels(days):
    labels = []
    last = None
    first_date = date.fromisoformat(days[0]["date"])
    sunday0 = first_date
    while (sunday0.weekday() + 1) % 7 != 0:
        sunday0 -= timedelta(days=1)
    for day in days:
        dt = date.fromisoformat(day["date"])
        month = dt.strftime("%Y-%m")
        if month != last:
            idx = (dt - sunday0).days // 7
            # skip labels that would collide with the previous one
            if not labels or idx - labels[-1][1] >= 3:
                labels.append((dt.strftime("%b"), idx))
            last = month
    return labels


def main():
    static_mode = os.environ.get("STATIC") == "1"
    payload = json.loads(DATA.read_text())
    days = [d for d in payload["days"] if d["date"]]

    positions = grid_positions(days)
    max_col = max(c for c, _, _, _ in positions) + 1
    thresholds = pick_thresholds([c for _, _, c, _ in positions if c > 0])

    total_width = PAD_LEFT + PAD_RIGHT + max_col * PITCH
    y_leg = GRID_TOP + 7 * PITCH + 14
    height = y_leg + 44

    anim_defs = "" if static_mode else """
  <style>
    .cell { opacity: 0; transform: translate(-12px, 16px);
            animation: drop 0.45s ease-out both; }
    @keyframes drop { to { opacity: 1; transform: translate(0, 0); } }
    .stats { opacity: 0; animation: fadein 0.6s ease-out 1.5s forwards; }
    @keyframes fadein { to { opacity: 1; } }
  </style>"""

    rects = []
    for col, row, count, day in positions:
        delay = f'animation-delay:{(0.02 * col + 0.01 * row):.2f}s'
        cls = f'class="cell" style="{delay}"\n          ' if not static_mode else ""
        x = PAD_LEFT + col * PITCH
        y = GRID_TOP + row * PITCH
        rects.append(
            f'<rect {cls}x="{x:.1f}" y="{y:.1f}" width="{CELL:.1f}" height="{CELL:.1f}" '
            f'rx="{CELL_R}" fill="{PALETTE[level(count, thresholds)]}">'
            f'<title>{day}: {count} contribution{"s" if count != 1 else ""}</title></rect>'
        )

    labels = "".join(
        f'<text x="{PAD_LEFT + idx * PITCH + PITCH / 2:.1f}" y="{GRID_TOP - 10}" '
        f'fill="{MUTED}" text-anchor="middle">{label}</text>'
        for label, idx in month_labels(days) if idx <= max_col - 3
    )

    # day-of-week gutter: Mon, Wed, Fri
    gutter = "".join(
        f'<text x="{PAD_LEFT - 12}" y="{GRID_TOP + row * PITCH + PITCH / 2 + 2:.1f}" '
        f'fill="{MUTED}" text-anchor="end">{name}</text>'
        for name, row in (("Mon", 1), ("Wed", 3), ("Fri", 5))
    )

    legend_x = total_width - (6 * PITCH + 46)
    legend = (
        f'<text x="{legend_x - 8}" y="{y_leg + CELL:.0f}" fill="{MUTED}" '
        f'text-anchor="end">Less</text>'
        + "".join(
            f'<rect x="{legend_x + i * PITCH:.1f}" y="{y_leg:.1f}" width="{CELL:.1f}" '
            f'height="{CELL:.1f}" rx="{CELL_R}" fill="{PALETTE[i]}"/>'
            for i in range(6)
        )
        + f'<text x="{legend_x + 6 * PITCH + 4:.1f}" y="{y_leg + CELL:.0f}" '
        f'fill="{MUTED}">More</text>'
    )

    stats = (
        f'<text x="{PAD_LEFT}" y="{y_leg + 30}" fill="{MUTED}" class="stats">'
        f'{payload["total"]} contributions · best day {payload["best_day"]["count"]} '
        f'({payload["best_day"]["date"]}) · longest streak {payload["longest_streak"]}d '
        f'· current streak {payload["current_streak"]}d</text>'
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height:.0f}"
     viewBox="0 0 {WIDTH} {height:.0f}" role="img" aria-label="Contribution calendar for {payload['user']}">
{anim_defs}
  <rect width="100%" height="100%" fill="{BG}" rx="10"/>
  <g font-family="{FONT}" font-size="10">
    {labels}
    {gutter}
    {"".join(rects)}
    {legend}
    {stats}
  </g>
</svg>'''

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.fromstring(svg)  # fail loudly on malformed SVG before it ships
    OUT.write_text(svg)
    print(f"wrote {OUT} ({len(positions)} cells, weeks={max_col}, h={height:.0f})")


if __name__ == "__main__":
    main()