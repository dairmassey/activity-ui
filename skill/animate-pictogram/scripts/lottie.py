"""Write a baked figure as Lottie JSON, for native iOS, Android and web players.

Uses only keyframed transforms, shapes and alpha-inverted track mattes, with no expressions,
so it stays within what the native players support. Limb gaps are the same shapes as the
SVG masks, drawn as mattes. Every key is linear, sampled from the same frames as the SVG.
"""
import json
import math

SCALE = 4  # composition units per SVG unit, so small figures keep precise coordinates
LINEAR_IN = {"x": [1], "y": [1]}
LINEAR_OUT = {"x": [0], "y": [0]}
LINEAR_IN_XY = {"x": 1, "y": 1}
LINEAR_OUT_XY = {"x": 0, "y": 0}


def rgb(colour):
    named = {"white": "#FFFFFF", "black": "#000000", "#fff": "#FFFFFF", "#000": "#000000"}
    value = named.get(colour.lower(), colour).lstrip("#")
    return [round(int(value[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [1]


def r2(v):
    return round(v, 2)


def fixed(value):
    return {"a": 0, "k": value}


def transform(position=None, rotation=None, scale=None, opacity=None, anchor=(0, 0)):
    return {
        "o": opacity or fixed(100),
        "r": rotation or fixed(0),
        "p": position or fixed([0, 0, 0]),
        "a": fixed([anchor[0], anchor[1], 0]),
        "s": scale or fixed([100, 100, 100]),
    }


def track_scalar(keys):
    """keys are (frame, value). Values on either side of a key blend linearly."""
    out = []
    for i, (frame, value) in enumerate(keys):
        key = {"t": frame, "s": [r2(value)]}
        if i < len(keys) - 1:
            key.update(i=LINEAR_IN, o=LINEAR_OUT)
        out.append(key)
    return {"a": 1, "k": out}


def track_point(keys):
    out = []
    for i, (frame, x, y) in enumerate(keys):
        key = {"t": frame, "s": [r2(x), r2(y), 0]}
        if i < len(keys) - 1:
            key.update(i=LINEAR_IN_XY, o=LINEAR_OUT_XY)
        out.append(key)
    return {"a": 1, "k": out}


def track_scale(keys):
    out = []
    for i, (frame, x, y) in enumerate(keys):
        key = {"t": frame, "s": [r2(x), r2(y), 100]}
        if i < len(keys) - 1:
            key.update(i={"x": [1, 1, 1], "y": [1, 1, 1]}, o={"x": [0, 0, 0], "y": [0, 0, 0]})
        out.append(key)
    return {"a": 1, "k": out}


def arc(cx, cy, radius, start, end):
    """Bezier segments for a circular arc. Returns [(point, in tangent, out tangent)]."""
    count = max(1, math.ceil(abs(end - start) / (math.pi / 2)))
    step = (end - start) / count
    handle = 4 / 3 * math.tan(step / 4) * radius
    points = []
    for i in range(count + 1):
        angle = start + step * i
        x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        tx, ty = -math.sin(angle) * handle, math.cos(angle) * handle
        points.append(((x, y), (-tx, -ty), (tx, ty)))
    return points


def capsule(length, r1, r2_, start=0.0):
    """Tapered capsule in bone space, matching rig.capsule_d."""
    tilt = math.asin(max(-1, min(1, (r1 - r2_) / length)))
    r1 += (r2_ - r1) * start / length
    top = arc(0, start, r1, math.pi - tilt, 2 * math.pi + tilt)
    bottom = arc(0, length, r2_, tilt, math.pi - tilt)
    top[0] = (top[0][0], (0, 0), top[0][2])
    top[-1] = (top[-1][0], top[-1][1], (0, 0))
    bottom[0] = (bottom[0][0], (0, 0), bottom[0][2])
    bottom[-1] = (bottom[-1][0], bottom[-1][1], (0, 0))
    points = top + bottom
    return {
        "c": True,
        "v": [[r2(p[0] * SCALE), r2(p[1] * SCALE)] for p, _, _ in points],
        "i": [[r2(t[0] * SCALE), r2(t[1] * SCALE)] for _, t, _ in points],
        "o": [[r2(t[0] * SCALE), r2(t[1] * SCALE)] for _, _, t in points],
    }


def group(items):
    return {
        "ty": "gr",
        "it": items + [{
            "ty": "tr", "p": fixed([0, 0]), "a": fixed([0, 0]), "s": fixed([100, 100]),
            "r": fixed(0), "o": fixed(100),
        }],
    }


def fill(colour):
    return {"ty": "fl", "c": fixed(colour), "o": fixed(100), "r": 1}


class Writer:
    def __init__(self, w, h, x0, y0, frames, op):
        self.w, self.h, self.x0, self.y0 = w * SCALE, h * SCALE, x0, y0
        self.frames, self.op = frames, op
        self.next_index = 1
        self.assets = []

    def at(self, i):
        return r2(i / self.frames * self.op)

    def layer(self, name, shapes, ks, **extra):
        index = self.next_index
        self.next_index += 1
        return {
            "ddd": 0, "ind": index, "ty": 4, "nm": name, "sr": 1, "ks": ks, "ao": 0,
            "shapes": shapes, "ip": 0, "op": self.op, "st": 0, "bm": 0, **extra,
        }

    def comp(self, name, layers, **extra):
        self.assets.append({"id": name, "nm": name, "fr": self.fps, "layers": layers})
        index = self.next_index
        self.next_index += 1
        return {
            "ddd": 0, "ind": index, "ty": 0, "nm": name, "refId": name, "sr": 1,
            "ks": transform(), "ao": 0, "w": self.w, "h": self.h, "ip": 0, "op": self.op,
            "st": 0, "bm": 0, **extra,
        }

    def bone_motion(self, joints, unwrap):
        points, angles, last = [], [], None
        for i, (a, b) in enumerate(joints):
            points.append((self.at(i), (a[0] - self.x0) * SCALE, (a[1] - self.y0) * SCALE))
            angle = unwrap(a, b)
            if last is not None:
                angle += 360 * round((last - angle) / 360)
            angles.append((self.at(i), angle))
            last = angle
        return transform(position=track_point(points), rotation=track_scalar(angles))

    def bone(self, name, shape, joints, unwrap, colour, stroke=0.0, stroke_track=None, **extra):
        items = [{"ty": "sh", "ks": fixed(shape)}]
        if stroke:
            width = fixed(stroke * SCALE)
            if stroke_track and min(stroke_track) < 1:
                width = track_scalar([(self.at(i), v * stroke * SCALE) for i, v in enumerate(stroke_track)])
            items.append({
                "ty": "st", "c": fixed(colour), "o": fixed(100), "w": width, "lc": 2, "lj": 2,
            })
        items.append(fill(colour))
        return self.layer(name, [group(items)], self.bone_motion(joints, unwrap), **extra)


def ease(t, x1=0.1, y1=0.42, x2=0.62, y2=0.72):
    """cubic-bezier timing, the same curve the SVG confetti uses."""
    low, high = 0.0, 1.0
    for _ in range(30):
        mid = (low + high) / 2
        x = 3 * (1 - mid) ** 2 * mid * x1 + 3 * (1 - mid) * mid * mid * x2 + mid**3
        low, high = (mid, high) if x < t else (low, mid)
    u = (low + high) / 2
    return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u * u * y2 + u**3


def along_curve(piece, share):
    """Point a given share of the way along the path by distance, as SVG motion does."""
    start, control, end = piece["path"]
    samples = []
    length, last = 0.0, start
    for i in range(61):
        t = i / 60
        p = tuple((1 - t) ** 2 * start[n] + 2 * t * (1 - t) * control[n] + t * t * end[n] for n in (0, 1))
        length += math.dist(p, last)
        samples.append((length, p))
        last = p
    goal = share * length
    return next((p for d, p in samples if d >= goal), samples[-1][1])


def confetti_layer(writer, piece, duration):
    fps = writer.op / duration
    first = piece["fire"] * fps
    life = duration * 0.5 * fps
    steps = 14
    points = []
    for i in range(steps + 1):
        share = i / steps
        x, y = along_curve(piece, ease(share))
        points.append((r2(first + life * share), (x - writer.x0) * SCALE, (y - writer.y0) * SCALE))
    opacity = [(r2(first), 0), (r2(first + life * 0.04), 100), (r2(first + life * 0.72), 100), (r2(first + life), 0)]
    spin = [(r2(first), 0), (r2(first + life), piece["turn"] / 2)]
    half = piece["flip"] * fps / 2
    flips, frame, wide = [], first, True
    while frame < first + life:
        flips.append((r2(frame), 100, 100 if wide else 12))
        frame += half
        wide = not wide
    flips.append((r2(first + life), 100, 100 if wide else 12))
    colour = rgb(piece["color"])
    if piece["kind"] == "dot":
        shape = {"ty": "el", "p": fixed([0, 0]), "s": fixed([r2(piece["w"] * SCALE)] * 2)}
    else:
        shape = {
            "ty": "rc", "p": fixed([0, 0]), "s": fixed([r2(piece["w"] * SCALE), r2(piece["h"] * SCALE)]),
            "r": fixed(r2(min(piece["w"], piece["h"]) * 0.22 * SCALE)),
        }
    ks = transform(
        position=track_point(points), rotation=track_scalar(spin), scale=track_scale(flips),
        opacity=track_scalar(opacity),
    )
    layer = writer.layer("confetti", [group([shape, fill(colour)])], ks)
    layer["ip"], layer["op"] = r2(first), r2(first + life)
    return layer


def ring_layer(writer, ring, colour):
    cx, cy, radius, width = ring
    shape = {"ty": "el", "p": fixed([r2((cx - writer.x0) * SCALE), r2((cy - writer.y0) * SCALE)]), "s": fixed([r2(radius * 2 * SCALE)] * 2)}
    stroke = {"ty": "st", "c": fixed(colour), "o": fixed(100), "w": fixed(r2(width * SCALE)), "lc": 2, "lj": 2}
    return writer.layer("wheel", [group([shape, stroke])], transform())


def build(data, colour):
    """data: canvas, duration, frames, tracks, lengths, heads, head, in_front, halo, rings, confetti."""
    w, h, x0, y0 = data["canvas"]
    duration, frames = data["duration"], data["frames"]
    fps = 50 if abs(duration * 50 - round(duration * 50)) < 1e-6 else 60
    op = round(duration * fps)
    writer = Writer(w, h, x0, y0, frames, op)
    writer.fps = fps
    fill_colour = rgb(colour)
    tracks, lengths, unwrap = data["tracks"], data["lengths"], data["angle"]
    halo_colour = [0, 0, 0, 1]
    halo = data["halo"]

    def shape_of(name):
        return capsule(lengths[name.split("-")[-1]], *tracks[name]["radii"])

    def bone(name, **extra):
        return writer.bone(name, shape_of(name), tracks[name]["joints"], unwrap, fill_colour, **extra)

    def cut(name, source, **extra):
        return writer.bone(name, shape_of(source), tracks[source]["joints"], unwrap, halo_colour, stroke=halo, **extra)

    def partial_cut(name, source, start, **extra):
        radii = tracks[source]["radii"]
        shape = capsule(lengths[source.split("-")[-1]], *radii, start)
        return writer.bone(name, shape, tracks[source]["joints"], unwrap, halo_colour, stroke=halo, **extra)

    in_front = data["in_front"]
    head_keys = []
    for i, (x, y) in enumerate(data["heads"]):
        head_keys.append((writer.at(i), (x - x0) * SCALE, (y - y0) * SCALE))
    head_shape = {"ty": "el", "p": fixed([0, 0]), "s": fixed([r2(data["head"] * 2 * SCALE)] * 2)}
    head = writer.layer("head", [group([head_shape, fill(fill_colour)])], transform(position=track_point(head_keys)))

    legs_far = [bone("far-shin"), bone("far-thigh")]
    if in_front:
        far_layers = legs_far
    else:
        arm = writer.comp("far-arm", [bone("far-fore"), bone("far-upper")], tt=2)
        matte = partial_cut("torso-gap", "torso", 0.42 * lengths["torso"], td=1)
        far_layers = legs_far + [matte, arm]
    far = writer.comp("far-side", far_layers, tt=2)
    leg_matte = cut("leg-gap", "near-shin", td=1, stroke_track=data.get("leg_gaps"))
    body = writer.comp("body", [bone("near-shin"), bone("near-thigh"), bone("torso"), leg_matte, far], tt=2)

    arm_start = data["arm_cut_from"]
    halos = [cut("arm-gap", "near-fore"), partial_cut("shoulder-gap", "near-upper", arm_start)]
    if in_front:
        halos += [cut("far-arm-gap", "far-fore"), partial_cut("far-shoulder-gap", "far-upper", arm_start)]
    body_matte = writer.comp("arm-gaps", halos, td=1)

    layers = [head, bone("near-fore"), bone("near-upper")]
    if in_front:
        near_gaps = [cut("near-gap", "near-fore"), partial_cut("near-shoulder", "near-upper", arm_start)]
        layers += [
            writer.comp("near-gaps", near_gaps, td=1),
            writer.comp("far-arm-front", [bone("far-fore"), bone("far-upper")], tt=2),
        ]
    layers += [body_matte, body]
    layers += [confetti_layer(writer, piece, duration) for piece in data["confetti"]]
    layers += [ring_layer(writer, ring, fill_colour) for ring in data["rings"]]
    doc = {
        "v": "5.7.0", "fr": fps, "ip": 0, "op": op, "w": writer.w, "h": writer.h,
        "nm": data["name"], "ddd": 0, "assets": writer.assets, "layers": layers,
    }
    if data.get("credit"):
        doc["meta"] = {"g": "animate-pictogram", "d": data["credit"]}
    return doc


def write(data, base, colours):
    for mode, colour in colours.items():
        target = f"{base}.{mode}.json"
        with open(target, "w") as out:
            json.dump(build(data, colour), out, separators=(",", ":"))
        print("wrote", target)
