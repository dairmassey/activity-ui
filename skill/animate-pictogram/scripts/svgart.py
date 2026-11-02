#!/usr/bin/env python3
"""Read a flat SVG pictogram: parse its paths, rasterise them, and draw an inspection sheet.

usage: svgart.py inspect <source.svg> <sheet.png>
Needs only Python 3.9+ and Pillow.
"""
import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

SS = 6  # raster pixels per SVG unit when measuring overlap
PAD = 3  # SVG units of margin around the art in rasters


class Art:
    """The drawable paths of an SVG: each path is a list of flattened subpaths."""

    def __init__(self, path):
        text = Path(path).read_text()
        self.text = text
        visible = re.sub(r"<(mask|clipPath|defs)\b.*?</\1>", "", text, flags=re.S)
        match = re.search(r'viewBox="([-\d.\s]+)"', text)
        box = [float(v) for v in match.group(1).split()] if match else [0, 0, 0, 0]
        self.x, self.y, self.width, self.height = box
        self.d = re.findall(r'\sd="([^"]+)"', visible)
        if not self.d or re.search(r"<(circle|ellipse|rect|polygon|polyline)\b", visible):
            raise SystemExit("Convert every shape to outlined paths first (Figma: Outline stroke, Flatten).")
        self.paths = [flatten(d) for d in self.d]
        fill = re.search(r'fill="(#[0-9a-fA-F]{3,8}|white|black)"', visible)
        self.fill = fill.group(1) if fill else "#000"

    def size(self):
        return int(math.ceil(self.width) + 2 * PAD) * SS, int(math.ceil(self.height) + 2 * PAD) * SS

    def mask(self, skip=()):
        """1-bit raster of the art. Subpaths of one path combine even-odd, so rings keep their hole."""
        size = self.size()
        out = Image.new("1", size, 0)
        for i, subpaths in enumerate(self.paths):
            if i in skip:
                continue
            layer = Image.new("1", size, 0)
            for poly in subpaths:
                piece = Image.new("1", size, 0)
                ImageDraw.Draw(piece).polygon([raster_point(p) for p in poly], fill=1)
                layer = ImageChops.logical_xor(layer, piece)
            out = ImageChops.logical_or(out, layer)
        return out


def raster_point(p):
    return (p[0] + PAD) * SS, (p[1] + PAD) * SS


def flatten(d):
    """Flatten absolute or relative M L H V C S Q T Z commands into polygons."""
    tokens = re.findall(r"[A-Za-z]|-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)
    polys, pts, i, cmd = [], [], 0, None
    cur, start, ctrl = (0.0, 0.0), (0.0, 0.0), None
    counts = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2)

    def curve(points):
        nonlocal cur
        for k in range(1, 25):
            t = k / 24
            u = 1 - t
            if len(points) == 4:
                w = (u**3, 3 * u * u * t, 3 * u * t * t, t**3)
            else:
                w = (u * u, 2 * u * t, t * t)
            pts.append(tuple(sum(a * p[n] for a, p in zip(w, points)) for n in (0, 1)))
        cur = points[-1]

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                polys.append(pts)
                pts, cur = [], start
                continue
        upper = cmd.upper()
        if upper not in counts:
            raise SystemExit(f"Path command {cmd} is not supported; export without arcs.")
        v = [float(t) for t in tokens[i:i + counts[upper]]]
        i += counts[upper]
        rel = cmd.islower()
        bx, by = cur if rel else (0.0, 0.0)
        if upper == "H":
            cur = (v[0] + bx, cur[1])
            pts.append(cur)
        elif upper == "V":
            cur = (cur[0], v[0] + by)
            pts.append(cur)
        elif upper in "ML":
            cur = (v[0] + bx, v[1] + by)
            if upper == "M":
                if pts:
                    polys.append(pts)
                pts, start = [], cur
                cmd = "l" if rel else "L"
            pts.append(cur)
        elif upper == "C":
            p1, p2, p3 = (v[0] + bx, v[1] + by), (v[2] + bx, v[3] + by), (v[4] + bx, v[5] + by)
            ctrl = p2
            curve([cur, p1, p2, p3])
        elif upper == "S":
            p1 = (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl else cur
            p2, p3 = (v[0] + bx, v[1] + by), (v[2] + bx, v[3] + by)
            ctrl = p2
            curve([cur, p1, p2, p3])
        elif upper == "Q":
            p1, p2 = (v[0] + bx, v[1] + by), (v[2] + bx, v[3] + by)
            ctrl = p1
            curve([cur, p1, p2])
        else:
            p1 = (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl else cur
            ctrl = p1
            curve([cur, p1, (v[0] + bx, v[1] + by)])
        if upper not in "CSQT":
            ctrl = None
    if pts:
        polys.append(pts)
    return polys


def describe(poly):
    """Bounding box, centre, radius and how circular a subpath is (1.0 is a true circle)."""
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    r = (w + h) / 4
    return {
        "box": (min(xs), min(ys), max(xs), max(ys)),
        "centre": ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2),
        "radius": r,
        "circular": area / (math.pi * r * r) if r else 0,
    }


def is_ring(subpaths):
    """True when a path is one outline with another nested inside it."""
    if len(subpaths) != 2:
        return False
    outer, inner = describe(subpaths[0])["box"], describe(subpaths[1])["box"]
    return outer[0] < inner[0] and outer[1] < inner[1] and outer[2] > inner[2] and outer[3] > inner[3]


def find_head(art):
    """The topmost near-circular solid subpath, as (path index, subpath index, description)."""
    best = None
    for i, subpaths in enumerate(art.paths):
        if is_ring(subpaths):
            continue  # a wheel or hoop, not a head
        for j, poly in enumerate(subpaths):
            info = describe(poly)
            if info["circular"] > 0.93 and (best is None or info["centre"][1] < best[2]["centre"][1]):
                best = (i, j, info)
    return best


def head_gap(art, head, props=()):
    """Clear space between the head and the nearest part of the body in the source art."""
    cx, cy = head[2]["centre"]
    nearest = min(
        math.dist((cx, cy), q)
        for i, subpaths in enumerate(art.paths) if i not in props
        for j, poly in enumerate(subpaths) if (i, j) != head[:2]
        for q in poly
    )
    return nearest - head[2]["radius"]


def inspect(source, out):
    art = Art(source)
    scale = 9
    w, h = int((art.width + 8) * scale), int((art.height + 8) * scale)
    img = Image.new("RGB", (w, h), (24, 35, 47))
    draw = ImageDraw.Draw(img)
    place = lambda p: ((p[0] + 4) * scale, (p[1] + 4) * scale)
    solid = art.mask().resize((int((math.ceil(art.width) + 2 * PAD) * scale), int((math.ceil(art.height) + 2 * PAD) * scale)))
    img.paste((225, 230, 235), (int((4 - PAD) * scale), int((4 - PAD) * scale)), solid.convert("L"))
    for v in range(0, int(art.width) + 10, 10):
        draw.line([place((v, -4)), place((v, art.height + 4))], fill=(255, 90, 90), width=1)
        draw.text((place((v, 0))[0] + 2, 2), str(v), fill=(255, 200, 120))
    for v in range(0, int(art.height) + 10, 10):
        draw.line([place((-4, v)), place((art.width + 4, v))], fill=(70, 150, 255), width=1)
        draw.text((2, place((0, v))[1] + 2), str(v), fill=(255, 200, 120))
    img.save(out)
    print(f"viewBox {art.x} {art.y} {art.width} {art.height}  fill {art.fill}")
    for i, subpaths in enumerate(art.paths):
        for j, poly in enumerate(subpaths):
            info = describe(poly)
            box = ", ".join(f"{v:.1f}" for v in info["box"])
            print(f"path {i}.{j}: box {box}  radius {info['radius']:.2f}  circular {info['circular']:.3f}")
    head = find_head(art)
    print("head:", f"path {head[0]}.{head[1]} at {head[2]['centre']}" if head else "none found")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "inspect":
        raise SystemExit(__doc__)
    inspect(sys.argv[2], sys.argv[3])
