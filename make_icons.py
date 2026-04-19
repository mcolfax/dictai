#!/usr/bin/env python3
"""
make_icons.py — Generate premium waveform icons for Dictate app
Creates: icon_menubar.png, icon_menubar_on.png, icon_menubar_anim_N.png,
         icon_dock.png, icon.icns
"""

import os, sys, struct, zlib, math
from pathlib import Path

# Allow --outdir to write icons somewhere other than the script's directory
if "--outdir" in sys.argv:
    idx = sys.argv.index("--outdir")
    APP_DIR = Path(sys.argv[idx + 1])
else:
    APP_DIR = Path(__file__).parent


# ── PNG writer ──────────────────────────────────────────────────────────────

def write_png(path, width, height, pixels):
    """Write a minimal RGBA PNG from a list-of-rows pixel array."""
    def chunk(name, data):
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''
    for row in pixels:
        raw += b'\x00'
        for px in row:
            raw += bytes(px)
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6))
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


# ── Menu bar icon helpers ────────────────────────────────────────────────────

def make_menubar_pixels(width, height, bar_heights, bar_color):
    """Render a waveform icon suitable for the macOS menu bar (transparent bg)."""
    pixels = [[[0, 0, 0, 0] for _ in range(width)] for _ in range(height)]
    n = len(bar_heights)
    bar_w = max(1, width // (n * 2 + 1))
    gap   = bar_w
    total = n * bar_w + (n - 1) * gap
    sx    = (width - total) // 2
    r, g, b, a = bar_color

    for i, frac in enumerate(bar_heights):
        bh = max(1, int(height * frac))
        x0 = sx + i * (bar_w + gap)
        y0 = (height - bh) // 2
        for py in range(y0, y0 + bh):
            for px in range(x0, x0 + bar_w):
                if 0 <= py < height and 0 <= px < width:
                    pixels[py][px] = [r, g, b, a]
    return pixels


WAVEFORM = [0.40, 0.70, 1.00, 0.70, 0.40]

# Off (idle) — white for template rendering
pixels = make_menubar_pixels(22, 22, WAVEFORM, (255, 255, 255, 220))
write_png(APP_DIR / "icon_menubar.png", 22, 22, pixels)
print("✅ icon_menubar.png")

# On state — amber
pixels = make_menubar_pixels(22, 22, WAVEFORM, (245, 158, 11, 255))
write_png(APP_DIR / "icon_menubar_on.png", 22, 22, pixels)
print("✅ icon_menubar_on.png")

# Animation frames
ANIM_FRAMES = 6
for frame in range(ANIM_FRAMES):
    phase = (2 * math.pi * frame) / ANIM_FRAMES
    bars = [0.22 + 0.60 * (0.5 + 0.5 * math.sin(phase + i * 0.9))
            for i in range(len(WAVEFORM))]
    pixels = make_menubar_pixels(22, 22, bars, (245, 158, 11, 255))
    write_png(APP_DIR / f"icon_menubar_anim_{frame}.png", 22, 22, pixels)
print(f"✅ icon_menubar_anim_0..{ANIM_FRAMES - 1}.png")


# ── Dock icon (512×512, premium dark bg + refined amber waveform) ────────────

def make_dock_icon(size=512):
    """Premium dock icon: deep dark bg with radial vignette, rounded waveform bars."""
    half = size / 2.0
    max_r = math.sqrt(half * half * 2)

    # Background: deep charcoal #0d0d11 center → #07070a edges
    BG_C = (14, 13, 18)
    BG_E = (6, 6, 9)
    corner_r = int(size * 0.185)  # ~95px at 512 — matches macOS icon rounding

    pixels = [[[0, 0, 0, 0] for _ in range(size)] for _ in range(size)]

    for y in range(size):
        for x in range(size):
            # Rounded-corner mask
            ax = x if x >= corner_r else corner_r
            ay = y if y >= corner_r else corner_r
            ax = ax if ax <= size - corner_r else size - corner_r
            ay = ay if ay <= size - corner_r else size - corner_r
            # Only reject actual corner pixels
            in_corner = (
                (x < corner_r or x >= size - corner_r) and
                (y < corner_r or y >= size - corner_r)
            )
            if in_corner:
                cx = corner_r if x < corner_r else size - corner_r
                cy = corner_r if y < corner_r else size - corner_r
                if (x - cx) ** 2 + (y - cy) ** 2 > corner_r ** 2:
                    continue  # outside rounded corner → transparent

            # Radial gradient from center
            d = math.sqrt((x - half) ** 2 + (y - half) ** 2) / max_r
            t = min(1.0, d * 1.6)
            r = int(BG_C[0] + (BG_E[0] - BG_C[0]) * t)
            g = int(BG_C[1] + (BG_E[1] - BG_C[1]) * t)
            b = int(BG_C[2] + (BG_E[2] - BG_C[2]) * t)
            pixels[y][x] = [r, g, b, 255]

    # Waveform: 9 bars, musical contour, centered slightly above midpoint
    BAR_HEIGHTS = [0.20, 0.42, 0.66, 0.88, 1.0, 0.88, 0.66, 0.42, 0.20]
    n_bars   = len(BAR_HEIGHTS)
    bar_w    = int(size * 0.048)   # ~24px
    bar_gap  = int(size * 0.022)   # ~11px
    bar_r    = bar_w // 2
    total_w  = n_bars * bar_w + (n_bars - 1) * bar_gap
    sx       = (size - total_w) // 2
    max_bh   = int(size * 0.60)
    cy       = size // 2           # bars centered vertically

    # Amber palette
    AMBER_TOP = (252, 169, 22)     # warm highlight
    AMBER_BOT = (220, 128, 8)      # deeper at bottom

    for i, frac in enumerate(BAR_HEIGHTS):
        bh  = max(bar_w + 2, int(max_bh * frac))
        bx  = sx + i * (bar_w + bar_gap)
        by0 = cy - bh // 2
        by1 = by0 + bh

        for py in range(max(0, by0), min(size, by1)):
            for px in range(max(0, bx), min(size, bx + bar_w)):
                # Rounded top cap
                if py < by0 + bar_r:
                    if (px - (bx + bar_r)) ** 2 + (py - (by0 + bar_r)) ** 2 > bar_r ** 2:
                        continue
                # Rounded bottom cap
                if py >= by1 - bar_r:
                    if (px - (bx + bar_r)) ** 2 + (py - (by1 - bar_r)) ** 2 > bar_r ** 2:
                        continue

                # Vertical gradient: lighter top → deeper amber bottom
                t  = (py - by0) / max(1, bh - 1)
                cr = int(AMBER_TOP[0] + (AMBER_BOT[0] - AMBER_TOP[0]) * t)
                cg = int(AMBER_TOP[1] + (AMBER_BOT[1] - AMBER_TOP[1]) * t)
                cb = int(AMBER_TOP[2] + (AMBER_BOT[2] - AMBER_TOP[2]) * t)
                pixels[py][px] = [cr, cg, cb, 255]

    return pixels


pixels = make_dock_icon()
write_png(APP_DIR / "icon_dock.png", 512, 512, pixels)
print("✅ icon_dock.png")


# ── .icns bundle ─────────────────────────────────────────────────────────────

def make_icns(output_path, png_512):
    with open(png_512, 'rb') as f:
        png = f.read()
    chunks = b''
    for ostype in [b'ic09', b'ic10']:   # 512px + 512@2x (reuse same PNG)
        chunks += ostype + struct.pack('>I', len(png) + 8) + png
    with open(output_path, 'wb') as f:
        f.write(b'icns' + struct.pack('>I', len(chunks) + 8) + chunks)


make_icns(APP_DIR / "icon.icns", APP_DIR / "icon_dock.png")
print("✅ icon.icns")
print("\nAll icons generated!")
