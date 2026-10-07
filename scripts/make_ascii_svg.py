#!/usr/bin/env python3
"""Photo-to-ASCII "typing" portrait SVG in the style of avi-ascii.svg
(https://www.avivashishta.com/blog/build-animated-github-profile-readme).

Reads assets/source-prepped.png (from prep_photo.py). If it doesn't
exist, renders user initials with Pillow as the portrait subject so the
repo works before you add a photo.

Animation: rows of characters reveal left-to-right like a typewriter
(clip-path wipe, CSS keyframes, staggered per row), plays once and
freezes. STATIC=1 emits the finished frame for local previews.

Output: assets/ascii-portrait.svg
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PREPPED = REPO / "assets" / "source-prepped.png"
OUT = REPO / "assets" / "ascii-portrait.svg"

USER = os.environ.get("GITHUB_USER", "jkw16")
INITIALS = "JW"

COLS = 110                      # characters per row
RAMP = " .`:-=+*cs#%@"          # dark pixel → dense char
FONT_SIZE = 13
LINE_H = 12                     # tighter than font size → portrait look
CHAR_W = 6.6
CHAR_COLOR = "#c9d1d9"
BG = "#0d1117"
BORDER = "#30363d"
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

INITIAL_FONT_CANDIDATES = (
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def load_source():
    """Return a grayscale PIL image for the portrait subject."""
    if PREPPED.exists():
        return Image.open(PREPPED).convert("L")
    # initials fallback — always available, works on CI too
    h = COLS  # square portrait
    img = Image.new("L", (h, h), 255)
    draw = ImageDraw.Draw(img)
    font = None
    for path in INITIAL_FONT_CANDIDATES:
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, int(h * 0.55))
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), INITIALS, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((h - tw) / 2 - bbox[0], (h - th) / 2 - bbox[1]), INITIALS,
              fill=0, font=font)
    return img


def to_ascii(img):
    w, h = img.size
    rows_count = max(1, int(h / w * COLS * 0.5))  # 0.5 corrects for char aspect
    small = img.resize((COLS, rows_count))
    px = small.load()
    ramp_len = len(RAMP)
    rows = []
    for y in range(rows_count):
        row = "".join(
            RAMP[min(ramp_len - 1, int((255 - px[x, y]) / 256 * ramp_len))]
            for x in range(COLS)
        )
        rows.append(row)
    return rows


def trim_blank(rows, pad=2):
    """Drop all-blank edge rows/cols so the figure fills the frame."""
    def blank(line):
        return set(line.strip()) == set() or line.strip() == ""
    top = 0
    while top < len(rows) - 1 and blank(rows[top]):
        top += 1
    bottom = len(rows)
    while bottom > top + 1 and blank(rows[bottom - 1]):
        bottom -= 1
    rows = rows[max(0, top - pad):bottom + pad]
    cols = [0, len(rows[0])]
    while cols[0] < cols[1] - 1 and all(r[cols[0]] == " " for r in rows):
        cols[0] += 1
    while cols[1] > cols[0] + 1 and all(r[cols[1] - 1] == " " for r in rows):
        cols[1] -= 1
    return [r[max(0, cols[0] - pad):cols[1] + pad] for r in rows]


def svg(rows, static_mode):
    height = len(rows)
    W = COLS * CHAR_W + 2 * 16
    H = height * LINE_H + 2 * 16

    texts, anims = [], []
    for i, line in enumerate(rows):
        escaped = (line.replace("&", "&amp;").replace("<", "&lt;")
                   .replace(">", "&gt;"))
        if static_mode:
            texts.append(
                f'<text x="16" y="{16 + i * LINE_H}" font-family="{FONT}" '
                f'font-size="{FONT_SIZE}" xml:space="preserve" '
                f'fill="{CHAR_COLOR}">{escaped}</text>'
            )
            continue
        cls = f"r{i}"
        anims.append(f".{cls}{{animation:wipe .3s linear {i * 0.028:.3f}s both;}}")
        texts.append(
            f'<g class="{cls}">'
            f'<text x="16" y="{16 + i * LINE_H}" font-family="{FONT}" '
            f'font-size="{FONT_SIZE}" xml:space="preserve" '
            f'fill="{CHAR_COLOR}">{escaped}</text>'
            f"</g>"
        )

    anim_block = (
        ""
        if static_mode
        else (
            "  <style>\n    "
            + "\n    ".join(anims)
            + "\n    @keyframes wipe { from { clip-path: inset(0 100% 0 0); }"
            " to { clip-path: inset(0 -1px 0 0); } }\n  </style>"
        )
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}"
     viewBox="0 0 {W:.0f} {H:.0f}" role="img"
     aria-label="ASCII portrait for {USER} (animated)">
{anim_block}
  <rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" fill="{BG}" rx="12" stroke="{BORDER}" stroke-width="1.5"/>
  <g>
    {"".join(texts)}
  </g>
</svg>'''


def main():
    static_mode = os.environ.get("STATIC") == "1"
    img = load_source()
    rows = trim_blank(to_ascii(img))
    # normalize lengths (trim may leave ragged edges)
    width = max(len(r) for r in rows)
    rows = [r.ljust(width) for r in rows]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg(rows, static_mode))
    print(f"wrote {OUT} ({len(rows)} rows × {width} cols, "
          f"source={'photo' if PREPPED.exists() else 'initials fallback'})")


if __name__ == "__main__":
    main()