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
        if (alpha > 0).any():
            white = np.full_like(img, 255)
            mask = (alpha[:, :, None] / 255.0)
            img = (cut[:, :, :3] * mask + white * (1 - mask)).astype(np.uint8)
    except ImportError:
        print("rembg not installed — skipping background removal")

    # face-aware square crop: center on a detected face when one exists,
    # otherwise fall back to a crop anchored in the upper third (portrait bias)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    faces = []
    detector = None
    if hasattr(cv2, "CascadeClassifier"):
        detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if not detector.empty():
            faces = list(detector.detectMultiScale(gray, 1.1, 5, minSize=(60, 60)))
    cy_frac, side = 0.28, min(h, w)
    cy_int = None
    if len(faces):
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        cy_int = int(fy + fh / 2)
        # widen so head+shoulders fit inside the square
        side = min(w, h, int(fw * 2.8))
    if cy_int is not None:
        y0 = cy_int - side // 2
    else:
        y0 = int(cy_frac * h) - side // 2
    y0 = sorted((0, y0, h - side))[1]
    x0 = int((w - side) / 2)
    x0 = sorted((0, x0, w - side))[1]
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