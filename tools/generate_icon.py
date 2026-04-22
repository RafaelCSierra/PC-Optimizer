"""Generate assets/icons/app.ico from scratch using Pillow.

Run once (or whenever the design changes); commit the resulting .ico.
  py tools/generate_icon.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "icons" / "app.ico"
SIZES = [256, 128, 64, 48, 32, 24, 16]

BG_TOP = (31, 111, 235)      # #1f6feb — matches design.PRIMARY
BG_BOTTOM = (26, 95, 211)    # #1a5fd3 — matches design.PRIMARY_HOVER
FG = (255, 255, 255)
ACCENT = (255, 213, 79)      # amber for the spark


def _linear_gradient(size: int) -> Image.Image:
    grad = Image.new("RGBA", (size, size))
    px = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        for x in range(size):
            px[x, y] = (r, g, b, 255)
    return grad


def _mask_rounded_square(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (size, size)], radius=radius, fill=255)
    return mask


def _spark_polygon(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    """Lightning bolt centered at (cx, cy)."""
    s = size / 2
    return [
        (cx - 0.15 * s, cy - s),
        (cx + 0.7 * s, cy - 0.2 * s),
        (cx + 0.15 * s, cy - 0.05 * s),
        (cx + 0.45 * s, cy + s),
        (cx - 0.7 * s, cy + 0.15 * s),
        (cx - 0.15 * s, cy),
    ]


def _font(size: int, px: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def render_one(size: int) -> Image.Image:
    bg = _linear_gradient(size)
    mask = _mask_rounded_square(size, radius=max(2, size // 5))
    bg.putalpha(mask)

    draw = ImageDraw.Draw(bg)

    # "PC" text, slightly above center to make room for the spark
    text = "PC"
    font_px = int(size * 0.46)
    font = _font(size, font_px)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1] - int(size * 0.07)
    draw.text((tx, ty), text, fill=FG, font=font)

    # Small underline accent
    line_w = int(size * 0.38)
    line_h = max(1, int(size * 0.035))
    line_y = int(size * 0.73)
    line_x = (size - line_w) // 2
    draw.rounded_rectangle(
        [(line_x, line_y), (line_x + line_w, line_y + line_h)],
        radius=line_h // 2, fill=ACCENT,
    )

    # Small spark badge at top-right (only visible from 32 px up)
    if size >= 32:
        badge_size = int(size * 0.35)
        bx = size - badge_size - int(size * 0.06)
        by = int(size * 0.06)
        # circle
        badge = Image.new("RGBA", (badge_size, badge_size), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge)
        bd.ellipse([(0, 0), (badge_size, badge_size)], fill=ACCENT)
        # spark inside
        poly = _spark_polygon(
            badge_size / 2, badge_size / 2, badge_size * 0.75,
        )
        bd.polygon(poly, fill=(60, 45, 0, 255))
        # drop-shadow-ish: paste twice
        shadow = badge.filter(ImageFilter.GaussianBlur(radius=max(1, size // 64)))
        bg.alpha_composite(shadow, (bx + 1, by + 1))
        bg.alpha_composite(badge, (bx, by))

    return bg


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [render_one(s) for s in SIZES]
    frames[0].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[1:],
    )
    print(f"wrote {OUT} with sizes {SIZES}")


if __name__ == "__main__":
    main()
