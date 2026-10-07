#!/usr/bin/env python3
"""Neofetch-style info card SVG — hand-authored rows that fade in line by line.

STATIC=1 emits a frozen frame (no animations) for local previews.
Content lives in the CARD dict below — edit it when your focus changes.
"""

import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "info-card.svg"


def esc(text):
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )

W, H = 490, 300
BG = "#0d1117"
BORDER = "#30363d"
MUTED = "#8b949e"
FG = "#c9d1d9"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

CARD_HEADER = "joshua@mac"
CARD_PROMPT = "~ $ neofetch"

# key -> (color, value). Keep values complementary to the heatmap stats
# (which already show activity totals/streaks) — don't duplicate totals here.
ROWS = [
    ("Role", "#79c0ff", "App builder & security researcher"),
    ("Now", "#a5d6ff", "Push bridges · bug hunting · tooling"),
    ("Stack", "#7ee787", "Python · Swift · JavaScript · Go"),
    ("Highlights", "#f778ba", "iOS apps · self-hosted infra · automation"),
]


def main():
    static_mode = os.environ.get("STATIC") == "1"

    anims = []
    x_key = 30
    delay = 0.15
    lines = []
    lines.append(
        f'<text x="30" y="40" font-family="{FONT}" font-size="13" fill="{FG}" '
        f'font-weight="bold">{CARD_HEADER}</text>'
    )
    delay += 0.1
    lines.append(
        f'<text x="30" y="62" font-family="{FONT}" font-size="12" fill="{MUTED}">'
        f'{"─" * 38}</text>'
    )

    y = 88
    for key, color, value in ROWS:
        if static_mode:
            anim = ""
        else:
            cls = f"row{len(lines):02d}"
            anims.append(
                f".{cls}{{opacity:0;transform:translateY(8px);"
                f"animation:in .4s ease-out {delay:.2f}s forwards;}}"
            )
            anim = f'class="{cls}"'
        lines.append(
            f'<text x="{x_key}" y="{y:.0f}" font-family="{FONT}" font-size="13" '
            f'fill="{color}" font-weight="bold"{anim}>{esc(key)}:</text>'
        )
        lines.append(
            f'<text x="{x_key + 110}" y="{y:.0f}" font-family="{FONT}" font-size="13" '
            f'fill="{FG}"{anim}>{esc(value)}</text>'
        )
        y += 26
        delay += 0.15

    y += 6
    ps_cls = "" if static_mode else "ps1"
    lines.append(
        f'<text x="30" y="{y:.0f}" font-family="{FONT}" font-size="12" '
        f'fill="{MUTED}" class="{ps_cls}">PS1</text>'
    )
    if not static_mode:
        anims.append(f".ps1{{opacity:0;animation:in .4s ease-out {delay:.2f}s forwards;}}")

    footer_x = x_key + 44
    lines.append(
        f'<text x="{footer_x}" y="{y:.0f}" font-family="{FONT}" font-size="13" '
        f'fill="{FG}" class="{"" if static_mode else "ps2"}">{CARD_PROMPT}</text>'
    )
    if not static_mode:
        anims.append(
            f".ps2{{opacity:0;animation:in .4s ease-out {delay + 0.25:.2f}s forwards;}}"
        )

    style_block = (
        "" if static_mode else (
            "  <style>\n    " + "\n    ".join(anims) + "\n    "
            "@keyframes in{to{opacity:1;transform:translateY(0);}}\n  </style>"
        )
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
     viewBox="0 0 {W} {H}" role="img" aria-label="Terminal info card for Joshua Wittenburg (jkw16)">
{style_block}
  <rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>
  <circle cx="26" cy="22" r="6" fill="#ff5f57"/>
  <circle cx="46" cy="22" r="6" fill="#febc2e"/>
  <circle cx="66" cy="22" r="6" fill="#28c840"/>
{chr(10).join(lines)}
</svg>'''

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg)
    print(f"wrote {OUT} (static={static_mode})")


if __name__ == "__main__":
    main()