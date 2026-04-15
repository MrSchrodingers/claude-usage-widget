#!/usr/bin/env python3
"""Generate pixel art sprite frames for Claude Widget mascot states."""

from PIL import Image, ImageDraw
import math
import os

PX = 4  # pixel block size
W, H = 16, 16  # grid
IMG = (W * PX, H * PX)  # 64x64
T = (0, 0, 0, 0)  # transparent

ICON_DIR = os.path.join(os.path.dirname(__file__), "..", "plasmoid", "contents", "icons")


def px(draw, gx, gy, color):
    if 0 <= gx < W and 0 <= gy < H:
        draw.rectangle([gx * PX, gy * PX, gx * PX + PX - 1, gy * PX + PX - 1], fill=color)


# ═══════════════════════════════════════
# GENIUS — Golden crown + sparkles
# ═══════════════════════════════════════
def gen_halo():
    GOLD = (255, 215, 0, 240)
    GOLD_DARK = (184, 134, 11, 220)
    GOLD_LIGHT = (255, 235, 100, 230)
    JEWEL_RED = (220, 40, 40, 230)
    JEWEL_BLUE = (60, 100, 220, 230)
    SPARKLE = (255, 255, 220, 200)

    # Crown shape — 3-point crown sitting on top
    crown_base = [
        # Base band (wide)
        (4, 4), (5, 4), (6, 4), (7, 4), (8, 4), (9, 4), (10, 4), (11, 4),
        # Second row
        (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3), (11, 3),
        # Inner fill
        (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2),
    ]
    crown_points = [
        # Left point
        (4, 2), (4, 1), (5, 0),
        # Center point (tallest)
        (7, 1), (8, 1), (7, 0), (8, 0),
        # Right point
        (11, 2), (11, 1), (10, 0),
    ]
    jewel_positions = [(5, 3, JEWEL_RED), (8, 3, JEWEL_BLUE), (10, 3, JEWEL_RED)]

    for frame in range(6):
        img = Image.new("RGBA", IMG, T)
        draw = ImageDraw.Draw(img)

        # Crown base
        for gx, gy in crown_base:
            px(draw, gx, gy, GOLD)

        # Crown points
        for gx, gy in crown_points:
            px(draw, gx, gy, GOLD_LIGHT)

        # Dark outline bottom
        for gx in range(4, 12):
            px(draw, gx, 5, GOLD_DARK)

        # Jewels
        for gx, gy, color in jewel_positions:
            px(draw, gx, gy, color)

        # Sparkles rotating
        sparkle_sets = [
            [(2, 1), (13, 0), (1, 6), (14, 5)],
            [(3, 0), (14, 1), (0, 5), (13, 6)],
            [(1, 0), (14, 2), (2, 7), (12, 5)],
            [(3, 2), (12, 0), (0, 6), (15, 4)],
            [(2, 0), (13, 2), (1, 5), (14, 6)],
            [(0, 1), (15, 1), (2, 6), (13, 4)],
        ]
        for sx, sy in sparkle_sets[frame]:
            px(draw, sx, sy, SPARKLE)
            px(draw, sx + 1, sy, (255, 255, 255, 100))
            px(draw, sx - 1, sy, (255, 255, 255, 100))
            px(draw, sx, sy + 1, (255, 255, 255, 100))
            px(draw, sx, sy - 1, (255, 255, 255, 100))

        img.save(os.path.join(ICON_DIR, f"halo-{frame}.png"))
    print("  crown: 6 frames")


# ═══════════════════════════════════════
# SLOW — Rain cloud + falling drops
# ═══════════════════════════════════════
def gen_rain():
    CLOUD_DARK = (105, 105, 105, 220)
    CLOUD_LIGHT = (140, 140, 140, 200)
    DROP = (77, 166, 255, 210)
    DROP_LIGHT = (120, 190, 255, 150)

    # Cloud shape — wider, spanning almost full width
    cloud_pixels = [
        # Row 0 (top bumps)
        (4, 0), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (11, 0),
        # Row 1
        (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (8, 1), (9, 1), (10, 1), (11, 1), (12, 1), (13, 1),
        # Row 2
        (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2), (13, 2), (14, 2),
        # Row 3 (bottom of cloud)
        (2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 3), (13, 3),
    ]

    # Rain drop columns — more drops spread wider
    drop_cols = [
        {"x": 3,  "phase": 0},
        {"x": 5,  "phase": 2},
        {"x": 7,  "phase": 4},
        {"x": 9,  "phase": 1},
        {"x": 11, "phase": 3},
        {"x": 13, "phase": 5},
        {"x": 4,  "phase": 1},
        {"x": 8,  "phase": 3},
        {"x": 12, "phase": 0},
    ]

    for frame in range(6):
        img = Image.new("RGBA", IMG, T)
        draw = ImageDraw.Draw(img)

        # Draw cloud
        for gx, gy in cloud_pixels:
            c = CLOUD_LIGHT if gy <= 1 else CLOUD_DARK
            px(draw, gx, gy, c)

        # Draw raindrops falling
        for dcol in drop_cols:
            # Each drop is 1px wide, 2px tall, falling from y=4 to y=15
            y_offset = (frame + dcol["phase"]) % 6
            drop_y = 4 + y_offset * 2
            if drop_y < 15:
                px(draw, dcol["x"], drop_y, DROP)
                px(draw, dcol["x"], drop_y + 1, DROP_LIGHT)

        # Splash at bottom (alternating)
        if frame % 2 == 0:
            px(draw, 5, 15, DROP_LIGHT)
            px(draw, 9, 15, DROP_LIGHT)
        else:
            px(draw, 7, 15, DROP_LIGHT)
            px(draw, 11, 15, DROP_LIGHT)

        img.save(os.path.join(ICON_DIR, f"rain-{frame}.png"))
    print("  rain: 6 frames")


# ═══════════════════════════════════════
# BRAINDEAD — Skull + rising smoke
# ═══════════════════════════════════════
def gen_skull():
    BONE = (224, 224, 224, 230)
    BONE_SHADOW = (180, 180, 180, 200)
    EYE = (30, 30, 30, 255)
    TEETH = (200, 200, 200, 220)
    SMOKE1 = (169, 169, 169, 140)
    SMOKE2 = (102, 102, 102, 100)
    SMOKE3 = (80, 80, 80, 60)

    # Skull shape (centered at bottom half, y=7-14)
    skull_body = [
        # Top of skull
        (6, 7), (7, 7), (8, 7), (9, 7),
        # Row 2
        (5, 8), (6, 8), (7, 8), (8, 8), (9, 8), (10, 8),
        # Row 3
        (5, 9), (6, 9), (7, 9), (8, 9), (9, 9), (10, 9),
        # Row 4 (eye level)
        (5, 10), (6, 10), (7, 10), (8, 10), (9, 10), (10, 10),
        # Row 5
        (5, 11), (6, 11), (7, 11), (8, 11), (9, 11), (10, 11),
        # Jaw
        (6, 12), (7, 12), (8, 12), (9, 12),
        (6, 13), (7, 13), (8, 13), (9, 13),
    ]
    eyes = [(6, 10), (6, 11), (9, 10), (9, 11)]
    teeth = [(6, 13), (7, 13), (8, 13), (9, 13)]

    # Smoke puff positions per frame (rising)
    smoke_patterns = [
        [(4, 5), (8, 4), (12, 5), (6, 3), (10, 2)],
        [(3, 4), (7, 3), (11, 4), (5, 2), (9, 1)],
        [(4, 3), (8, 2), (12, 3), (6, 1), (10, 0)],
        [(3, 2), (7, 1), (11, 2), (5, 0), (9, 4)],
        [(4, 1), (8, 0), (12, 1), (6, 4), (10, 3)],
        [(3, 0), (7, 4), (11, 0), (5, 3), (9, 2)],
    ]

    for frame in range(6):
        img = Image.new("RGBA", IMG, T)
        draw = ImageDraw.Draw(img)

        # Draw smoke puffs (behind skull)
        for sx, sy in smoke_patterns[frame]:
            c = SMOKE1 if sy > 2 else SMOKE2 if sy > 0 else SMOKE3
            px(draw, sx, sy, c)
            px(draw, sx + 1, sy, c)
            if sy > 1:
                px(draw, sx, sy - 1, SMOKE3)

        # Draw skull
        for gx, gy in skull_body:
            c = BONE_SHADOW if gy >= 12 else BONE
            px(draw, gx, gy, c)

        # Eyes (dark)
        for gx, gy in eyes:
            px(draw, gx, gy, EYE)

        # X in eyes (red, alternating)
        RED = (239, 68, 68, 200) if frame % 2 == 0 else (200, 50, 50, 180)
        px(draw, 6, 10, RED)
        px(draw, 6, 11, RED)
        px(draw, 9, 10, RED)
        px(draw, 9, 11, RED)

        # Teeth
        for gx, gy in teeth:
            px(draw, gx, gy, TEETH if (gx + frame) % 2 == 0 else BONE_SHADOW)

        img.save(os.path.join(ICON_DIR, f"skull-{frame}.png"))
    print("  skull: 6 frames")


if __name__ == "__main__":
    os.makedirs(ICON_DIR, exist_ok=True)
    print("Generating sprites...")
    gen_halo()
    gen_rain()
    gen_skull()
    print("Done! 18 PNGs generated.")
