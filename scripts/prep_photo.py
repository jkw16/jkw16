#!/usr/bin/env python3
"""Prepare a portrait for the ASCII converter.

Takes assets/source-photo.jpg (any square-ish photo), removes the
background (rembg, optional if not installed), enhances contrast with
CLAHE, composites onto white, and writes assets/source-prepped.png.

Usage: prep_photo.py [input]  (default: assets/source-photo.jpg)
If no input photo exists, run `make_ascii_svg.py` directly — it falls
back to rendering initials.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

DEFAULT_INPUT = REPO / "assets" / "source-photo.jpg"
OUT = REPO / "assets" / "source-prepped.png"


def main(argv):
    src = Path(argv[1]) if len(argv) > 1 else DEFAULT_INPUT
    if not src.exists():
        print(f"no photo at {src} — make_ascii_svg.py will fall back to initials")
        return 1

    import cv2
    import numpy as np
    from PIL import Image

    img = np.array(Image.open(src).convert("RGB"))

    # optional background removal: rembg if importable
    try:
        from rembg import remove

        cut = remove(img)
        alpha = cut[:, :, 3]
        subject = cut[:, :, :3][alpha > 0]
        if subject.size:
            mean = subject.reshape(-1, 3).mean(axis=0)
        else:
            mean = np.array([255, 255, 255])
        white = np.full_like(img, 255)
        mask = (alpha[:, :, None] / 255.0)
        img = (cut[:, :, :3] * mask + white * (1 - mask)).astype(np.uint8)
    except ImportError:
        print("rembg not installed — skipping background removal")

    # square-crop around the center, then downscale for the char grid
    h, w = img.shape[:2]
    side = min(h, w)
    y0, x0 = (h - side) // 2, (w - side) // 2
    img = img[y0:y0 + side, x0:x0 + side]

    # CLAHE on L channel — brings out facial contours for ASCII
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(OUT)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)