#!/usr/bin/env python3
"""Fit a capsule skeleton to a pictogram and bake a motion to a self-contained animated SVG.

usage:
  rig.py fit  <spec.json>                 writes <spec>.rig.json and <spec>.fit.png
  rig.py bake <spec.json> <out.svg>       writes out.svg and out.preview.html
  rig.py bake <spec.json> <out.svg> --lottie <base>   also writes <base>.dark.json and .light.json

The spec format is documented in ../references/spec.md. Needs Python 3.9+ and Pillow.
"""
import base64
import json
import math
import random
import re
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from svgart import Art, describe, find_head, head_gap, raster_point  # noqa: E402
import motions  # noqa: E402
import lottie  # noqa: E402

ANNEAL = 12000
HEAD_LAG = 0.035  # the head trails the shoulders by this fraction of a cycle
HALO = 1.3  # gap cut around near limbs where they cross something behind them


def along(p, angle, length):
    """Point `length` along a bone whose rest vector (0, 1) is rotated by `angle` degrees."""
    r = math.radians(angle)
    return p[0] - length * math.sin(r), p[1] + length * math.cos(r)


def angle_of(a, b):
    return math.degrees(math.atan2(-(b[0] - a[0]), b[1] - a[1]))


def ik(root, end, l1, l2, bend=1):
    """Middle joint of a two-bone limb. bend=1 puts it forward (+x) of the root-to-end line."""
    dx, dy = end[0] - root[0], end[1] - root[1]
    dist = math.hypot(dx, dy) or 1e-6
    reach = (l1 + l2) * 0.9995
    if dist > reach:
        end = (root[0] + dx * reach / dist, root[1] + dy * reach / dist)
        dx, dy, dist = end[0] - root[0], end[1] - root[1], reach
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0, l1 * l1 - a * a)) * bend
    ux, uy = dx / dist, dy / dist
    return (root[0] + a * ux + h * uy, root[1] + a * uy - h * ux), end


def peel(hip, foot, length, reach):
    """Raise a foot that would stretch the leg past reach, as a heel peels off the ground.

    A leg driven to full stretch makes the knee snap, because the knee moves fastest there.
    """
    if not reach:
        return foot
    dist = math.dist(hip, foot) / length
    start = reach - 0.03
    if dist <= start:
        return foot
    capped = start + (reach - start) * math.tanh((dist - start) / (reach - start))
    dx = foot[0] - hip[0]
    return foot[0], hip[1] + math.sqrt(max(0, (capped * length) ** 2 - dx * dx))


def capsule(a, b, ra, rb, steps=16):
    """Outline of the tapered capsule joining circle (a, ra) to circle (b, rb)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1e-6
    base = math.atan2(dy, dx)
    tilt = math.acos(max(-1, min(1, (ra - rb) / length)))
    out = []
    for k in range(steps + 1):
        t = base + tilt + (2 * math.pi - 2 * tilt) * k / steps
        out.append((a[0] + ra * math.cos(t), a[1] + ra * math.sin(t)))
    for k in range(steps + 1):
        t = base - tilt + 2 * tilt * k / steps
        out.append((b[0] + rb * math.cos(t), b[1] + rb * math.sin(t)))
    return out


def rolled_root(p, upper_angle):
    """Arm root that rolls inside the chest, keeping the arm's outer edge tangent to it.

    The shoulder line stays one smooth curve at every arm angle, with no hump or dimple.
    """
    if abs(upper_angle) > 90:  # raised above the shoulder, the root stays on the arm's own side
        alpha = math.radians(-math.copysign(abs(upper_angle) - 90, upper_angle))
    else:
        alpha = math.radians(upper_angle - 90 * math.tanh(upper_angle / 18))
    inset = p["rc"] - p["rs"]
    return p["cx"] + inset * math.sin(alpha), p["cy"] - inset * math.cos(alpha)


def arm_root(p, spec, i, upper_angle):
    if spec.get("shoulders", "roll") == "roll":
        return rolled_root(p, upper_angle)
    return p["cx"] + p[f"s{i}x"], p["cy"] + p[f"s{i}y"]


def hip_at(p, side):
    return p["px"] + p["hip_dx"] * side, p["py"] + p["hip_dy"] * side


def rolled_hip(p, thigh_angle):
    """Thigh root that rolls inside the pelvis, the lower-body twin of rolled_root.

    The thigh's trailing edge stays tangent to the pelvis, so the seat is one smooth curve
    at any leg angle, with no bump above a dent where the thigh leaves the body.
    """
    side = math.tanh(thigh_angle / 18)
    r = math.radians(thigh_angle)
    inset = p["rp"] - p["rhip"]
    return p["px"] + inset * side * math.cos(r), p["py"] + inset * side * math.sin(r)


def leg_root(p, spec, side, thigh_angle):
    if spec.get("hips", "roll") == "roll":
        return rolled_hip(p, thigh_angle)
    return hip_at(p, side)


def rest_joints(p, spec):
    """(arms, legs) of the rest pose: arms are (root, elbow, hand), legs (hip, knee, foot)."""
    arms, legs = [], []
    for i in (0, 1):
        k = 0 if spec.get("twin_arms") else i
        angle, flex = p[f"a{k}"], p[f"f{k}"]
        root = arm_root(p, spec, k, angle)
        elbow = along(root, angle, p["upper"])
        arms.append((root, elbow, along(elbow, angle - flex, p["fore"])))
    for i, side in enumerate((1, -1)):
        k = 0 if spec.get("twin_legs") else i
        angle, flex = p[f"l{k}"], p[f"k{k}"]
        hip = leg_root(p, spec, 0 if spec.get("twin_legs") else side, angle)
        knee = along(hip, angle, p["thigh"])
        legs.append((hip, knee, along(knee, angle + flex, p["shin"])))
    return arms, legs


def bones_of(p, arms, legs, chest, pelvis):
    """Every capsule of a pose as (name, joint a, joint b, radius a, radius b), back to front."""
    out = []
    for name, i in (("far", 1), ("near", 0)):
        hip, knee, foot = legs[i]
        root, elbow, hand = arms[i]
        out.append((f"{name}-thigh", hip, knee, p["rhip"], p["rk"]))
        out.append((f"{name}-shin", knee, foot, p["rk"], p["rf"]))
        out.append((f"{name}-upper", root, elbow, p["rs"], p["re"]))
        out.append((f"{name}-fore", elbow, hand, p["re"], p["rh"]))
    out.append(("torso", chest, pelvis, p["rc"], p["rp"]))
    return out


def start_params(spec, art, head):
    chest, pelvis = spec["chest"], spec["pelvis"]
    r = head["radius"]
    arms, legs = spec["arms"], spec["legs"]
    p = dict(
        cx=chest[0], cy=chest[1], rc=spec.get("chest_radius", 0.85 * r),
        px=pelvis[0], py=pelvis[1], rp=spec.get("pelvis_radius", 0.8 * r),
        hip_dx=0.15 * r, hip_dy=0.05 * r,
        rs=0.5 * r, re=0.47 * r, rh=0.42 * r, rhip=0.6 * r, rk=0.53 * r, rf=0.5 * r,
    )
    uppers, fores, thighs, shins = [], [], [], []
    for i, arm in enumerate(arms):
        root = chest
        uppers.append(math.dist(root, arm["elbow"]))
        fores.append(math.dist(arm["elbow"], arm["hand"]))
        p[f"a{i}"] = angle_of(root, arm["elbow"])
        p[f"f{i}"] = max(0, angle_of(root, arm["elbow"]) - angle_of(arm["elbow"], arm["hand"]))
        offset = (arm["elbow"][0] - chest[0], arm["elbow"][1] - chest[1])
        scale = 0.35 * p["rc"] / (math.hypot(*offset) or 1)
        p[f"s{i}x"], p[f"s{i}y"] = offset[0] * scale, offset[1] * scale
    for i, leg in enumerate(legs):
        hip = pelvis
        thighs.append(math.dist(hip, leg["knee"]))
        shins.append(math.dist(leg["knee"], leg["foot"]))
        p[f"l{i}"] = angle_of(hip, leg["knee"])
        p[f"k{i}"] = angle_of(leg["knee"], leg["foot"]) - p[f"l{i}"]
    p["upper"], p["fore"] = sum(uppers) / len(uppers), sum(fores) / len(fores)
    p["thigh"], p["shin"] = sum(thighs) / len(thighs), sum(shins) / len(shins)
    return p


def render(p, spec, art):
    img = Image.new("1", art.size(), 0)
    draw = ImageDraw.Draw(img)
    arms, legs = rest_joints(p, spec)
    for _, a, b, ra, rb in bones_of(p, arms, legs, (p["cx"], p["cy"]), (p["px"], p["py"])):
        draw.polygon([raster_point(q) for q in capsule(a, b, ra, rb)], fill=1)
    return img


def borrow_body(own, donor, spec):
    """Give a figure another figure's torso and leg proportions, keeping its own height and stride.

    Everything is scaled so the leg plus torso stays the figure's own length, and the figure
    is moved so its front foot stays on the same ground.
    """
    span = lambda q: math.dist((q["cx"], q["cy"]), (q["px"], q["py"]))
    total = lambda q: q["thigh"] + q["shin"] + q["rf"] + span(q)
    scale = total(own) / total(donor)
    out = dict(own)
    for key in ("thigh", "shin", "rhip", "rk", "rf", "rc", "rp"):
        out[key] = donor[key] * scale
    length = span(donor) * scale
    ux, uy = (own["cx"] - own["px"]) / span(own), (own["cy"] - own["py"]) / span(own)
    out["cx"], out["cy"] = own["px"] + ux * length, own["py"] + uy * length
    reach = (out["thigh"] + out["shin"]) / (own["thigh"] + own["shin"])
    feet = [(own["px"] + (leg[2][0] - own["px"]) * reach * 0.97, leg[2][1]) for leg in rest_joints(own, spec)[1]]
    # Sit the hips for these legs: a stance leg should stay nearly straight at mid-stride.
    height = feet[0][1] - 0.95 * (out["thigh"] + out["shin"])
    out["cy"] += height - out["py"]
    out["py"] = height
    for i, side in enumerate((1, -1)):
        hip = (out["px"], out["py"])
        for _ in range(3):
            knee, _foot = ik(hip, feet[i], out["thigh"], out["shin"])
            out[f"l{i}"] = angle_of(hip, knee)
            hip = leg_root(out, spec, side, out[f"l{i}"])
        knee, foot = ik(hip, feet[i], out["thigh"], out["shin"])
        out[f"l{i}"] = angle_of(hip, knee)
        out[f"k{i}"] = angle_of(knee, foot) - out[f"l{i}"]
    return out


def overlap(img, target):
    inter = ImageChops.logical_and(img, target).histogram()[255]
    union = ImageChops.logical_or(img, target).histogram()[255]
    return inter / union


def penalty(p, spec):
    """Shape rules that overlap alone cannot see. Each one prevents a visible defect."""
    if spec.get("hips", "roll") == "roll":
        out = 0.05 * max(0, p["rhip"] + 0.5 - p["rp"])
    else:
        out = 0.02 * max(0, math.hypot(p["hip_dx"], p["hip_dy"]) + p["rhip"] - p["rp"])  # hip lump
    out += 0.03 * max(0, p["rp"] - p["rc"] - 0.2)  # pear-shaped torso
    if spec.get("shoulders", "roll") == "roll":
        out += 0.05 * max(0, p["rs"] + 0.5 - p["rc"])
    else:
        for i in (0, 1):
            out += 0.03 * max(0, math.hypot(p[f"s{i}x"], p[f"s{i}y"]) + p["rs"] - p["rc"])
    out += 0.02 * max(0, p["rs"] - 1.15 * p["re"])  # a wide cone instead of an arm reads as a hulking shoulder
    out += 0.002 * (max(0, -p["f0"]) + max(0, -p["f1"]))  # elbows that bend backwards
    out += 0.002 * max(0, abs(p["upper"] - p["fore"]) - 3)
    out += 0.004 * max(0, abs(p["thigh"] - p["shin"]) - 3)  # unequal bones make knees look misplaced
    return out


def fit_mask(art, spec, head):
    """The source with props and the head removed: what the skeleton has to cover."""
    props = set(spec.get("props", []))
    size = art.size()
    out = Image.new("1", size, 0)
    for i, subpaths in enumerate(art.paths):
        if i in props:
            continue
        for j, poly in enumerate(subpaths):
            if head and (i, j) == head[:2]:
                continue
            piece = Image.new("1", size, 0)
            ImageDraw.Draw(piece).polygon([raster_point(q) for q in poly], fill=1)
            out = ImageChops.logical_or(out, piece)
    return out


def fit(spec_path):
    spec = json.loads(Path(spec_path).read_text())
    art = Art(Path(spec_path).parent / spec["source"])
    head = find_head(art)
    if head is None:
        raise SystemExit("No near-circular head subpath found; run svgart.py inspect.")
    target = fit_mask(art, spec, head)
    p = start_params(spec, art, head[2])
    frozen = set()
    if spec.get("twin_arms"):
        frozen |= {"a1", "f1", "s1x", "s1y"}
    if spec.get("twin_legs"):
        frozen |= {"l1", "k1", "hip_dx", "hip_dy"}
        p["hip_dx"] = p["hip_dy"] = 0.0
    if spec.get("shoulders", "roll") == "roll":
        frozen |= {"s0x", "s0y", "s1x", "s1y"}
    if spec.get("hips", "roll") == "roll":
        frozen |= {"hip_dx", "hip_dy"}
    keys = [k for k in p if k not in frozen]
    wide = lambda k: 4.0 if re.fullmatch(r"[aflk][01]", k) else 1.0  # angles take bigger steps
    score = lambda q: overlap(render(q, spec, art), target) - penalty(q, spec)
    best = score(p)
    print(f"start {best:.4f}")
    for step in (1.0, 0.5, 0.25, 0.1):
        for _ in range(5):
            improved = False
            for key in keys:
                for sign in (1, -1):
                    trial = dict(p)
                    trial[key] += sign * step * wide(key)
                    value = score(trial)
                    if value > best + 1e-6:
                        p, best, improved = trial, value, True
                        break
            if not improved:
                break
    rng = random.Random(7)
    for i in range(ANNEAL):
        sigma = 0.35 * (1 - i / ANNEAL) + 0.03
        trial = dict(p)
        for key in rng.sample(keys, rng.randint(2, 5)):
            trial[key] += rng.gauss(0, sigma * wide(key))
        value = score(trial)
        if value > best:
            p, best = trial, value
    final = overlap(render(p, spec, art), target)
    p = {k: round(v, 3) for k, v in p.items()}
    Path(spec_path).with_suffix(".rig.json").write_text(json.dumps(p, indent=1) + "\n")
    rigged = render(p, spec, art).convert("L")
    sheet = Image.new("RGB", art.size(), (24, 35, 47))
    sheet.paste((255, 70, 70), mask=target.convert("L"))
    sheet.paste((235, 235, 235), mask=rigged)
    sheet.paste((70, 170, 255), mask=ImageChops.subtract(rigged, target.convert("L")))
    sheet.paste((255, 70, 70), mask=ImageChops.subtract(target.convert("L"), rigged))
    sheet.save(Path(spec_path).with_suffix(".fit.png"))
    print(f"first-pose overlap {final:.4f}  rule penalty {penalty(p, spec):.4f}")
    print("radii chest %.1f pelvis %.1f  lengths upper %.1f fore %.1f thigh %.1f shin %.1f" % (
        p["rc"], p["rp"], p["upper"], p["fore"], p["thigh"], p["shin"]))


class Rig:
    """A fitted figure, posable at any cycle time by a motion."""

    def __init__(self, spec, params, art):
        self.spec, self.p, self.art = spec, params, art
        self.chest = (params["cx"], params["cy"])
        self.pelvis = (params["px"], params["py"])
        self.head_index = find_head(art)
        info = self.head_index[2]
        self.head = (*info["centre"], info["radius"])
        self.rest_arms, self.rest_legs = rest_joints(params, spec)
        self.height = art.height

    def to_body(self, point, frame):
        """Move a torso-fixed point: pitch about the pelvis, then the pelvis offset."""
        dx, dy, pitch = frame
        r = math.radians(pitch - self.upright)
        x, y = point[0] - self.pelvis[0], point[1] - self.pelvis[1]
        return (
            self.pelvis[0] + x * math.cos(r) - y * math.sin(r) + dx,
            self.pelvis[1] + x * math.sin(r) + y * math.cos(r) + dy,
        )

    def head_at(self, t, motion):
        top = lambda u: self.to_body(self.chest, motion(u)["frame"])
        lag = getattr(self, "head_lag", HEAD_LAG)
        now, before = top(t - lag), top(-lag)
        # Set the neck by the visible gap above the chest. The source's head-to-chest distance
        # can run diagonally past an arm, which leaves a big gap once the head sits over the body.
        neck = self.p["rc"] + self.head[2] + self.neck_gap
        if callable(self.neck_tilt):
            tilt = math.radians(self.neck_tilt(t))
            return now[0] + neck * math.sin(tilt), now[1] - neck * math.cos(tilt)
        if self.neck_tilt is None:
            rest = self.to_body(self.head[:2], (0, 0, 0))
        else:
            tilt = math.radians(self.neck_tilt)
            chest = top(0)
            rest = (chest[0] + neck * math.sin(tilt), chest[1] - neck * math.cos(tilt))
        return rest[0] + (now[0] - before[0]) * 1.1, rest[1] + (now[1] - before[1]) * 1.1

    def pose(self, t, motion):
        p, spec = self.p, self.spec
        m = motion(t)
        frame = m["frame"]
        legs_frame = m.get("leg_frame", frame)
        arms, legs = [], []
        for i, entry in enumerate(m["arms"]):
            if entry[0] == "fk":
                _, upper, flex = entry
                root = self.to_body(arm_root(p, spec, i, upper), frame)
                elbow = along(root, upper, p["upper"])
                arms.append((root, elbow, along(elbow, upper - flex, p["fore"])))
            else:
                root = self.to_body(self.rest_arms[i][0], frame)
                elbow, hand = ik(root, entry[1], p["upper"], p["fore"], bend=-1)
                arms.append((root, elbow, hand))
        for i, entry in enumerate(m["legs"]):
            if entry[0] == "fk":
                _, angle, flex = entry
                hip = self.to_body(leg_root(p, spec, m["hips"][i], angle), legs_frame)
                knee = along(hip, angle, p["thigh"])
                legs.append((hip, knee, along(knee, angle + flex, p["shin"])))
            else:
                hip = self.to_body(self.pelvis, legs_frame)
                target = entry[1]
                for _ in range(2):  # the root depends on the thigh angle, which depends on the root
                    target = peel(hip, entry[1], p["thigh"] + p["shin"], m.get("leg_reach"))
                    knee, foot = ik(hip, target, p["thigh"], p["shin"])
                    hip = self.to_body(leg_root(p, spec, m["hips"][i], angle_of(hip, knee)), legs_frame)
                target = peel(hip, entry[1], p["thigh"] + p["shin"], m.get("leg_reach"))
                knee, foot = ik(hip, target, p["thigh"], p["shin"])
                legs.append((hip, knee, foot))
        chest, pelvis = self.to_body(self.chest, frame), self.to_body(self.pelvis, frame)
        return bones_of(p, arms, legs, chest, pelvis), self.head_at(t, motion)


def num(v, digits=2):
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def capsule_d(length, r1, r2, start=0.0):
    """Tapered capsule in bone space: joint at the origin, far end along +y.

    A positive start begins it part-way along the bone, keeping the same taper.
    """
    a = math.asin(max(-1, min(1, (r1 - r2) / length)))
    r1 += (r2 - r1) * start / length
    x1, y1 = r1 * math.cos(a), start + r1 * math.sin(a)
    x2, y2 = r2 * math.cos(a), length + r2 * math.sin(a)
    top, bottom = int(a > 0), int(a < 0)
    return (
        f"M{num(-x1)} {num(y1)}A{num(r1)} {num(r1)} 0 {top} 1 {num(x1)} {num(y1)}"
        f"L{num(x2)} {num(y2)}A{num(r2)} {num(r2)} 0 {bottom} 1 {num(-x2)} {num(y2)}Z"
    )


def bone_svg(name, d, frames, duration):
    """A bone with its translate and rotate tracks. Angles are unwrapped so arms never spin."""
    pos, rot, last = [], [], None
    for a, b in frames:
        pos.append(f"{num(a[0])} {num(a[1])}")
        angle = angle_of(a, b)
        if last is not None:
            angle += 360 * round((last - angle) / 360)
        rot.append(num(angle, 1))
        last = angle
    return (
        f'<path id="{name}" d="{d}" transform="translate({pos[0]}) rotate({rot[0]})">'
        f'<animateTransform attributeName="transform" type="translate" dur="{duration}s" '
        f'repeatCount="indefinite" values="{";".join(pos)}"/>'
        f'<animateTransform attributeName="transform" type="rotate" additive="sum" dur="{duration}s" '
        f'repeatCount="indefinite" values="{";".join(rot)}"/></path>'
    )


def confetti_svg(centre, head_radius, duration, colors, floor, pieces=26):
    """Confetti that bursts up on each arm pump, then tumbles down behind the figure.

    Pieces are staggered around the two pumps of the routine and are transparent when they
    wrap, so the loop has no seam. Returns the animated pieces, a still scatter of the same
    pieces for reduced motion, and the area they use.
    """
    rng = random.Random(11)
    cx, cy = centre[0], centre[1] - 1.5 * head_radius
    moving, still, pieces_out = [], [], []
    spread = 4.7 * head_radius
    for i in range(pieces):
        fire = (i % 2) * duration / 4 + rng.uniform(0, 0.08) * duration
        begin = f'begin="{num(fire - duration, 3)}s"'
        timing = f'dur="{num(duration, 3)}s" {begin} repeatCount="indefinite"'
        angle = math.radians(rng.uniform(-68, 68))
        power = rng.uniform(0.6, 1.0) * 3.3 * head_radius
        px, py = cx + math.sin(angle) * power * 1.9, cy - math.cos(angle) * power * 1.5
        ex = cx + math.sin(angle) * power * 1.6 + rng.uniform(-0.8, 0.8) * head_radius
        ex = max(cx - spread, min(cx + spread, ex))
        ey = floor - rng.uniform(0, 0.45) * (floor - cy)
        color = colors[i * 3 // 2 % len(colors)]  # pieces alternate between bursts, so step unevenly to mix
        turn = rng.choice((-1, 1)) * rng.randint(360, 900)
        flip = rng.uniform(0.5, 1.0)
        size = rng.uniform(0.3, 0.44) * head_radius
        kind = rng.random()
        spin = (
            f'<animateTransform attributeName="transform" type="scale" values="1 1;1 0.12;1 1" '
            f'dur="{num(flip, 2)}s" repeatCount="indefinite"/>'
        )
        piece = dict(fire=fire, path=((cx, cy), (px, py), (ex, ey)), color=color, turn=turn, flip=flip)
        pieces_out.append(piece)
        if kind < 0.22:
            shape = f'<circle r="{num(size * 0.72)}" fill="{color}">{spin}</circle>'
            piece.update(kind="dot", w=size * 1.44, h=size * 1.44)
        else:
            w, h = (size * 0.7, size * 3.2) if kind > 0.8 else (size * 1.5, size)
            piece.update(kind="bar", w=w, h=h)
            shape = (
                f'<rect x="{num(-w / 2)}" y="{num(-h / 2)}" width="{num(w)}" height="{num(h)}" '
                f'rx="{num(min(w, h) * 0.22)}" fill="{color}">{spin}</rect>'
            )
        moving.append(
            f'<g opacity="0.01"><animate attributeName="opacity" keyTimes="0;0.02;0.36;0.5;1" '
            f'values="0;1;1;0;0" {timing}/>'
            f'<animateMotion path="M{num(cx)} {num(cy)}Q{num(px)} {num(py)} {num(ex)} {num(ey)}" '
            f'calcMode="spline" keyPoints="0;1;1" keyTimes="0;0.5;1" keySplines="0.1 0.42 0.62 0.72;0 0 1 1" {timing}/>'
            f'<g><animateTransform attributeName="transform" type="rotate" from="0" to="{turn}" {timing}/>'
            f'{shape}</g></g>'
        )
        u = 0.4 + 0.58 * (i * 0.618 % 1)  # evenly spread along the fall, so the still never clumps
        v = 1 - u
        sx = v * v * cx + 2 * v * u * px + u * u * ex
        sy = v * v * cy + 2 * v * u * py + u * u * ey
        plain = re.sub(r"<animateTransform[^>]*/>", "", shape)
        still.append(f'<g transform="translate({num(sx)} {num(sy)}) rotate({rng.randint(0, 180)})">{plain}</g>')
    box = (cx - spread - head_radius, cy - 3.0 * head_radius, cx + spread + head_radius)
    return "".join(moving), "".join(still), box, pieces_out


def still_svg(art, head, props):
    """The source art for reduced motion, with the head as a true circle where it stands alone."""
    parts = []
    for i, d in enumerate(art.d):
        if i in props:
            continue
        if i == head[0] and len(art.paths[i]) == 1:
            cx, cy = head[2]["centre"]
            parts.append(f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(head[2]["radius"])}"/>')
        else:
            parts.append(f'<path fill-rule="evenodd" d="{d}"/>')
    return "".join(parts)


def bake(spec_path, out_path, lottie_base=None):
    spec_path, out_path = Path(spec_path), Path(out_path)
    spec = json.loads(spec_path.read_text())
    art = Art(spec_path.parent / spec["source"])
    params = json.loads(spec_path.with_suffix(".rig.json").read_text())
    if "arm_scale" in spec:  # a fitted arm can be as long as the pose implies, not as it should read
        params["upper"] = params["fore"] = spec["arm_scale"] * (params["upper"] + params["fore"]) / 2
    if "borrow_body" in spec:
        donor = json.loads((spec_path.parent / spec["borrow_body"]).read_text())
        params = borrow_body(params, donor, spec)
    if "arm_width" in spec:  # a fit on a thick pose can leave arms fat, so set them from the head
        width = spec["arm_width"] * find_head(art)[2]["radius"]
        params["rs"], params["re"], params["rh"] = 1.1 * width, width, 0.9 * width
    if "arm_ratio" in spec:  # the same arm-to-leg share keeps a set of figures matched
        total = spec["arm_ratio"] * (params["thigh"] + params["shin"] + params["rf"]) - params["rh"]
        params["upper"] = params["fore"] = total / 2
    rig = Rig(spec, params, art)
    options = dict(spec.get("motion", {}))
    kind = options.pop("type", "walk")
    base = options.get("activity", kind)
    posture = {**motions.POSTURE.get(base, {}), **spec.get("posture", {})}
    rig.upright = posture.get("upright", 0)
    rig.neck_tilt = posture.get("neck_tilt")
    rig.neck_gap = posture.get("neck_gap", head_gap(art, rig.head_index, spec.get("props", [])))
    print(f"head gap {rig.neck_gap:.2f} units")
    motion, duration, belt = motions.build(kind, rig, options)
    frames = int(spec.get("frames", 36))
    cycles = getattr(rig, "sub_cycles", 1)
    if cycles > 1:  # arms run on a longer routine than the legs, so only they need the full timeline
        frames = 24 * cycles

    poses = [rig.pose(i / frames, motion) for i in range(frames)]
    poses.append(poses[0])
    gaps = [motion(i / frames).get("leg_gap", 1) for i in range(frames)]
    gaps.append(gaps[0])
    tracks = {}
    for bones, _ in poses:
        for name, a, b, ra, rb in bones:
            tracks.setdefault(name, dict(joints=[], radii=(ra, rb)))["joints"].append((a, b))
    heads = [h for _, h in poses]

    p = params
    lengths = {"thigh": p["thigh"], "shin": p["shin"], "upper": p["upper"], "fore": p["fore"],
               "torso": math.dist(rig.chest, rig.pelvis)}
    svg_bone = {}
    for name, track in tracks.items():
        key = name.split("-")[-1]
        joints, length = track["joints"], duration
        keep_all = key in ("upper", "fore") or (key == "torso" and getattr(rig, "full_body", False))
        if cycles > 1 and not keep_all:
            joints, length = joints[:frames // cycles] + joints[:1], round(duration / cycles, 4)
        svg_bone[name] = bone_svg(name, capsule_d(lengths[key], *track["radii"]), joints, length)
        if name == "torso":
            torso_track = (joints, length, track["radii"])

    r = rig.head[2]
    xs, ys = [0, art.width], [0, art.height]
    for name, track in tracks.items():
        for (a, b), (ra, rb) in ((j, track["radii"]) for j in track["joints"]):
            xs += [a[0] - ra, a[0] + ra, b[0] - rb, b[0] + rb]
            ys += [a[1] - ra, a[1] + ra, b[1] - rb, b[1] + rb]
    for x, y in heads:
        xs += [x - r, x + r]
        ys += [y - r, y + r]
    confetti, confetti_still, confetti_pieces = "", "", []
    if getattr(rig, "confetti", None):
        floor = max(ys)
        confetti, confetti_still, box, confetti_pieces = confetti_svg(heads[0], r, duration, rig.confetti, floor)
        xs += [box[0], box[2]]
        ys += [box[1]]
    x0, y0 = math.floor(min(xs)) - 1, math.floor(min(ys)) - 1
    x1, y1 = math.ceil(max(xs)) + 1, math.ceil(max(ys)) + 1
    w, h = x1 - x0, y1 - y0

    head_track, head_length = heads, duration
    if cycles > 1 and not getattr(rig, "full_body", False):
        head_track, head_length = heads[:frames // cycles] + heads[:1], round(duration / cycles, 4)
    head_vals = ";".join(f"{num(x - rig.head[0])} {num(y - rig.head[1])}" for x, y in head_track)
    head_svg = (
        f'<circle id="head" cx="{num(rig.head[0])}" cy="{num(rig.head[1])}" r="{num(r)}" '
        f'transform="translate({head_vals.split(";")[0]})">'
        f'<animateTransform attributeName="transform" type="translate" dur="{head_length}s" '
        f'repeatCount="indefinite" values="{head_vals}"/></circle>'
    )
    props = "".join(f'<path fill-rule="evenodd" d="{art.d[i]}"/>' for i in spec.get("props", []))
    rect = f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#fff"/>'
    attrs = f'maskUnits="userSpaceOnUse" x="{x0}" y="{y0}" width="{w}" height="{h}"'
    halo = f'fill="#000" stroke="#000" stroke-width="{num(HALO * 2)}"'
    use = lambda name: f'<use href="#{name}" xlink:href="#{name}" {halo}/>'
    # The far arm goes behind the torso, and a thin gap below the chest shows it passing behind,
    # so its stroke still reads. Both arms in front looks like two arms stuck on the chest.
    in_front = spec.get("arms_in_front", False)
    credit = f'<!--! {spec["credit"]} --><metadata>{spec["credit"]}</metadata>' if "credit" in spec else ""
    b = svg_bone
    far_arm = b["far-upper"] + "\n" + b["far-fore"]
    # The gap runs from the armpit down. Stopping short of the root keeps the shoulder joined,
    # and two front arms must stop sooner or their gaps meet and cut the torso from the chest.
    cut_from = spec.get("arm_cut_from", 0.72 if in_front else 0.62) * p["upper"]
    upper_cut = capsule_d(p["upper"], p["rs"], p["re"], cut_from)
    guides = ""
    for side in ("near", "far") if in_front else ("near",):
        guides += bone_svg(f"{side}-cut", upper_cut, tracks[f"{side}-upper"]["joints"], duration)
    # The gap stops short of the chest, so the shoulder stays joined.
    guides += bone_svg(
        "torso-cut", capsule_d(lengths["torso"], *torso_track[2], 0.42 * lengths["torso"]),
        torso_track[0], torso_track[1],
    )
    guides = f"<defs>{guides}</defs>\n"
    masks, open_arm, open_leg, close_arm, close_leg = "", "", "", "", ""
    if spec.get("halo", True):
        leg_cut = use("near-shin")
        if min(gaps) < 1:
            values = gaps[:frames // cycles] + gaps[:1] if cycles > 1 else gaps
            widths = ";".join(num(HALO * 2 * v) for v in values)
            leg_cut = leg_cut.replace("/>", (
                f'><animate attributeName="stroke-width" dur="{round(duration / cycles, 4)}s" '
                f'repeatCount="indefinite" values="{widths}"/></use>'
            ))
        cuts = use("near-cut") + use("near-fore")
        if in_front:
            cuts += use("far-cut") + use("far-fore")
        masks = (
            f'<mask id="cut-arm" {attrs}>{rect}{cuts}</mask>\n'
            f'<mask id="cut-leg" {attrs}>{rect}{leg_cut}</mask>\n'
        )
        open_arm, open_leg = '<g mask="url(#cut-arm)">', '<g mask="url(#cut-leg)">'
        close_arm, close_leg = "</g>", "</g>"
        if in_front:
            masks += f'<mask id="cut-near" {attrs}>{rect}{use("near-cut")}{use("near-fore")}</mask>\n'
        else:
            masks += f'<mask id="cut-body" {attrs}>{rect}{use("torso-cut")}</mask>\n'
        masks = guides + masks
    still = still_svg(art, rig.head_index, spec.get("props", []))
    if getattr(rig, "still_t", None) is not None:  # a celebration rests on its peak, not on the source pose
        bones, peak = rig.pose(rig.still_t, motion)
        still = confetti_still
        for name, a, b2, ra, rb in bones:
            d = capsule_d(lengths[name.split("-")[-1]], ra, rb)
            still += f'<path d="{d}" transform="translate({num(a[0])} {num(a[1])}) rotate({num(angle_of(a, b2), 1)})"/>'
        still += f'<circle cx="{num(peak[0])}" cy="{num(peak[1])}" r="{num(r)}"/>'
    arm_behind = "" if in_front else (f'<g mask="url(#cut-body)">{far_arm}</g>' if masks else far_arm)
    arm_ahead = ""
    if in_front:
        arm_ahead = f'<g mask="url(#cut-near)">{far_arm}</g>' if masks else far_arm
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="{x0} {y0} {w} {h}" role="img" aria-label="{spec.get("label", "Person in motion")}">{credit}
<style>@media(prefers-reduced-motion:no-preference){{.still{{display:none}}}}@media(prefers-reduced-motion:reduce){{.moving{{display:none}}}}</style>
{masks}<g fill="{art.fill}">{props}<g class="moving">
{confetti}
{open_arm}
{open_leg}
{arm_behind}
{b["far-thigh"]}
{b["far-shin"]}
{close_leg}
{b["torso"]}
{b["near-thigh"]}
{b["near-shin"]}
{close_arm}
{arm_ahead}
{b["near-upper"]}
{b["near-fore"]}
{head_svg}
</g>
<g class="still">{still}</g></g>
</svg>
"""
    out_path.write_text(svg)
    if lottie_base:
        rings = []
        for i in spec.get("props", []):
            outer, inner = describe(art.paths[i][0]), describe(art.paths[i][1])
            rings.append((*outer["centre"], (outer["radius"] + inner["radius"]) / 2, outer["radius"] - inner["radius"]))
        lottie.write(dict(
            name=spec.get("label", "Figure"), canvas=(w, h, x0, y0), duration=duration, frames=frames,
            tracks=tracks, lengths=lengths, angle=angle_of, heads=heads, head=r, in_front=in_front,
            halo=HALO * 2 if spec.get("halo", True) else 0, rings=rings, confetti=confetti_pieces,
            arm_cut_from=cut_from, credit=spec.get("credit"), leg_gaps=gaps,
        ), lottie_base, {"dark": "#FFFFFF", "light": "#000000"})
    write_preview(out_path, svg, art, spec_path.parent / spec["source"], w, h, y1, rig, belt, duration)
    print(f"canvas {w}x{h} at {x0},{y0}  bytes {len(svg)}  cycle {duration}s  frames {frames}")
    reach = (p["upper"] + p["fore"] + p["rh"]) / (p["thigh"] + p["shin"] + p["rf"])
    print(f"arm is {reach:.0%} of leg length")
    if belt:
        print(f"belt speed {belt:.2f} units/s")
        if kind in ("walk", "run"):
            step = belt * duration / 2
            print(f"step {step:.1f} units, {step / art.height:.0%} of height")
    print(f"preview {out_path.with_suffix('.preview.html')}")


def write_preview(out_path, svg, art, source_path, w, h, y1, rig, belt, duration):
    """Self-contained page: source beside the live figure, a scrubber, and a foot-slide road."""
    as_uri = lambda text: "data:image/svg+xml;base64," + base64.b64encode(text.encode()).decode()
    source_uri, walk_uri = as_uri(source_path.read_text()), as_uri(svg)
    light = art.fill.lower() in ("white", "#fff", "#ffffff")
    bg, ink = ("#18232f", "#afbdca") if light else ("#f4f6f8", "#44515e")
    road = ""
    if belt:
        scale = 2.4
        travel = 900
        run = (travel + w * scale) / (belt * scale)
        ground = getattr(rig, "ground", max(rig.rest_legs[0][2][1], rig.rest_legs[1][2][1])) + rig.p["rf"]
        road = f"""<div class="road" style="height:{h * scale:.0f}px"><img src="{walk_uri}" alt="Figure moving along a ground line" style="height:{h * scale:.1f}px;left:-{w * scale:.0f}px;bottom:{-(y1 - ground) * scale:.1f}px;animation-duration:{run:.3f}s"></div>
<p>{getattr(rig, "road_note", "Crossing the page at the motion's own belt speed, so a planted foot should hold still on the line.")}</p>"""
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{out_path.stem} preview</title>
<style>
body{{margin:0;min-height:100vh;background:{bg};color:{ink};font:15px system-ui;overflow-x:hidden}}
main{{max-width:760px;margin:auto;padding:32px 16px;text-align:center}}
.pair{{display:flex;justify-content:center;gap:48px;flex-wrap:wrap}}
figure{{margin:0}}figcaption{{margin-top:12px}}
.pair svg,.pair img{{height:300px;width:auto;display:block}}
.controls{{margin:24px 0;display:flex;gap:12px;justify-content:center;align-items:center;flex-wrap:wrap}}
button{{padding:8px 18px;border:0;border-radius:16px;font:inherit}}
input{{width:220px;max-width:100%}}
.road{{position:relative;margin-top:40px;border-bottom:2px solid {ink};overflow:hidden}}
.road img{{position:absolute;animation:go linear infinite}}
@keyframes go{{to{{transform:translateX({900 + w * 2.4:.0f}px)}}}}
@media(prefers-reduced-motion:reduce){{.road img{{animation:none;left:40px!important}}}}
</style>
<main>
<div class="pair">
<figure><img src="{source_uri}" alt="Source artwork"><figcaption>Source</figcaption></figure>
<figure id="live">{svg}<figcaption>Animated</figcaption></figure>
</div>
<div class="controls"><button id="toggle">Pause</button>
<label>Scrub <input id="scrub" type="range" min="0" max="{duration}" step="0.01" value="0"></label></div>
{road}
</main>
<script>
const s=document.querySelector('#live svg'),b=document.getElementById('toggle'),r=document.getElementById('scrub');
b.onclick=()=>{{const p=s.animationsPaused();p?s.unpauseAnimations():s.pauseAnimations();b.textContent=p?'Pause':'Play'}};
r.oninput=()=>{{s.pauseAnimations();s.setCurrentTime(+r.value);b.textContent='Play'}};
</script>
</html>
"""
    out_path.with_suffix(".preview.html").write_text(page)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "fit":
        fit(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == "bake":
        bake(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 6 and sys.argv[1] == "bake" and sys.argv[4] == "--lottie":
        bake(sys.argv[2], sys.argv[3], sys.argv[5])
    else:
        raise SystemExit(__doc__)
