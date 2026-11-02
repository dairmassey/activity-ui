"""Motions for rig.py. Each builder returns (motion, duration, belt speed or None).

A motion maps cycle time t to:
  frame  (dx, dy, pitch): pelvis offset and torso pitch, all zero at t = 0
  arms   two entries, ("fk", upper angle, elbow flex) or ("ik", hand position)
  legs   two entries, ("fk", thigh angle, knee flex) or ("ik", foot position)
  hips   two side factors: +1 and -1 at rest, sliding through 0 as the pelvis rotates

Index 0 is the near limb, drawn on top. Angles are degrees: 0 hangs straight down,
positive swings backward (-x), negative swings forward (+x).
"""
import math

TAU = 2 * math.pi

# Default body lean per motion. Upright walkers look hunched at the source's lean;
# runners and riders need theirs. Override with "posture" in the spec.
POSTURE = {
    "walk": {"upright": 5.0, "neck_tilt": 11.0},
    "run": {"upright": 6.0, "neck_tilt": 10.0},
    "pedal": {"upright": 0.0, "neck_tilt": 38.0},
    "keys": {"upright": 0.0, "neck_tilt": None},
    "celebrate": {},
}


def arm_swing(rig, t, elbow_forward=0.0, elbow_back=0.0, back=None):
    """Arm 0 starts at its rest angle and reaches arm 1's rest angle half a cycle later."""
    p = rig.p
    forward = -math.cos(TAU * t)
    back = p["a0"] if back is None else back
    upper = (back + p["a1"]) / 2 + forward * (p["a1"] - back) / 2
    flex = (p["f0"] + p["f1"]) / 2 + forward * (p["f1"] - p["f0"]) / 2
    swing = math.sin(TAU * t)
    flex += (elbow_forward if swing > 0 else elbow_back) * swing * swing
    return "fk", upper, flex


def hermite(a, b, ma, mb, dt, s):
    h00, h10 = 2 * s**3 - 3 * s**2 + 1, s**3 - 2 * s**2 + s
    h01, h11 = -2 * s**3 + 3 * s**2, s**3 - s**2
    return h00 * a + h10 * dt * ma + h01 * b + h11 * dt * mb


def spline(keys, t, start_slope=None, end_slope=None, periodic=False):
    """Smooth curve through (time, values) keys, with time-aware Catmull-Rom tangents."""
    n = len(keys)
    width = len(keys[0][1])

    def slope(i):
        if periodic:
            ta, va = keys[(i - 1) % (n - 1)]
            tb, vb = keys[(i + 1) % (n - 1)] if i < n - 1 else keys[1]
            ta, tb = (ta - 1 if i == 0 else ta), (tb + 1 if i == n - 1 else tb)
        elif i == 0:
            return start_slope
        elif i == n - 1:
            return end_slope
        else:
            (ta, va), (tb, vb) = keys[i - 1], keys[i + 1]
        return [(b - a) / (tb - ta) for a, b in zip(va, vb)]

    for i in range(n - 1):
        t0, v0 = keys[i]
        t1, v1 = keys[i + 1]
        if t <= t1 or i == n - 2:
            s = (t - t0) / (t1 - t0)
            m0, m1 = slope(i), slope(i + 1)
            return [hermite(v0[k], v1[k], m0[k], m1[k], t1 - t0, s) for k in range(width)]


def walk(rig, o):
    """Rest pose: near leg just landed, far leg at toe-off, near arm back, far arm forward."""
    size = rig.height
    double = o.get("double_support", 0.08)
    stance = 0.5 + double
    bob, surge = o.get("bob", 0.0092 * size), o.get("surge", 0.0056 * size)
    arm_back = o.get("arm_back")
    lean = o.get("lean", 1.2)
    lift = o.get("foot_lift", 0.082 * size)
    keep = o.get("swing_tangent", 0.5)
    duration = o.get("duration", 1.2)
    front, back = rig.rest_legs[0][2], rig.rest_legs[1][2]
    # Sitting slightly into the legs keeps them off full stretch, where a knee snaps.
    ground, foot_back = front[1] - o.get("sit", 0.0035 * size), back[0]
    share = double / stance
    foot_land = (front[0] - foot_back * share) / (1 - share)
    foot_land -= o.get("soft_landing", 0.06) * (rig.p["thigh"] + rig.p["shin"])
    stride = (foot_land - foot_back) / stance
    # The foot peels up behind the body, skims low through the swing and sets down softly.
    # Lifting highest mid-swing reads as marching, and dropping onto a straight leg as a stomp.
    clearance = [(0.0, [0.0]), (0.3, [1.0]), (0.62, [0.3]), (0.88, [0.12]), (1.0, [0.0])]

    def foot(f):
        if f < stance:
            return foot_land - (foot_land - foot_back) * f / stance, ground
        s = (f - stance) / (1 - stance)
        slope = -keep * stride
        x = hermite(foot_back, foot_land, slope, slope, 1 - stance, s)
        return x, ground - lift * max(0.0, spline(clearance, s, [0.0], [0.0])[0])

    def frame(t):
        phase = 2 * TAU * (t + double / 2)
        start = TAU * double
        return (
            surge * (math.sin(phase) - math.sin(start)),
            bob * (math.cos(phase) - math.cos(start)),
            lean * (math.sin(2 * TAU * (t + 0.04)) - math.sin(2 * TAU * 0.04)),
        )

    def motion(t):
        return dict(
            frame=frame(t),
            arms=[arm_swing(rig, t, 36, 12, arm_back), arm_swing(rig, t + 0.5, 36, 12, arm_back)],
            legs=[("ik", foot((t + double) % 1)), ("ik", foot((t + double + 0.5) % 1))],
            hips=[math.cos(TAU * t), -math.cos(TAU * t)],
            leg_reach=o.get("leg_reach", 0.99),
        )

    return motion, duration, stride / duration


def run(rig, o):
    """Rest pose: airborne, near leg reaching forward, far leg trailing, near arm back.

    A runner is highest in flight and lowest at mid-stance. The foot lands close under the
    body while sweeping backward, and the knee absorbs the weight, which keeps it light.
    """
    p, size = rig.p, rig.height
    land, off = o.get("land", 0.145), o.get("toe_off", 0.355)
    sink = o.get("sink", 0.012 * size)
    lean = o.get("lean", 1.5)
    duration = o.get("duration", 0.68)
    front, back = rig.rest_legs[0][2], rig.rest_legs[1][2]
    ground = o.get("ground", front[1] + 0.03 * size)
    rig.ground = ground
    px, py = rig.pelvis
    length = p["thigh"] + p["shin"]
    foot_land = o.get("foot_land", px + 0.16 * length)
    foot_off = o.get("foot_off", px - 0.33 * length)
    tuck = o.get("tuck", (px - 0.3 * length, py + 0.35 * length))
    belt = (foot_land - foot_off) / (off - land)
    swing = [
        (off, [foot_off, ground]),
        (0.5, list(back)),
        (0.74, list(tuck)),
        (1.0, list(front)),
        (1 + land, [foot_land, ground]),
    ]
    arm_back, arm_front = o.get("arm_back", min(p["a0"], 88)), o.get("arm_front", max(p["a1"], -45))
    elbow_back, elbow_front = o.get("elbow_back", p["f0"]), o.get("elbow_front", 80)
    pump = o.get("elbow_pump", 14)

    def foot(t):
        t %= 1
        if land <= t <= off:
            return foot_land - belt * (t - land), ground
        x, y = spline(swing, t + 1 if t < land else t, [-belt, 0], [-belt, 0])
        return x, min(y, ground)

    def arm(t):
        forward = -math.cos(TAU * t)
        upper = (arm_back + arm_front) / 2 + forward * (arm_front - arm_back) / 2
        carry = (elbow_back + elbow_front) / 2 + forward * (elbow_front - elbow_back) / 2
        return "fk", upper, carry + pump * math.sin(TAU * t) ** 2

    def frame(t):
        return 0.0, sink * (1 - math.cos(2 * TAU * t)) / 2, lean * math.sin(2 * TAU * t)

    def motion(t):
        return dict(
            frame=frame(t),
            arms=[arm(t), arm(t + 0.5)],
            legs=[("ik", foot(t)), ("ik", foot(t + 0.5))],
            hips=[math.cos(TAU * t), -math.cos(TAU * t)],
        )

    return motion, duration, belt / duration


def pedal(rig, o):
    """Feet turn a crank, hands stay on the bars. Rest pose: near foot on the crank circle.

    The hips sit on the saddle and the upper body stays quiet, so the legs do the work.
    With wheels as props, road speed follows the pedalling through the gear.
    """
    size = rig.height
    radius = o.get("crank", 0.1 * size)
    duration = o.get("duration", 0.75)
    foot = rig.rest_legs[0][2]
    start = math.radians(o.get("start_angle", 0))  # 0 is the bottom of the stroke
    cx = foot[0] + radius * math.sin(start)
    cy = foot[1] - radius * math.cos(start)
    rock = o.get("rock", 0.8)
    hands = [rig.rest_arms[0][2], rig.rest_arms[1][2]]

    def crank(angle):
        return cx - radius * math.sin(angle), cy + radius * math.cos(angle)

    def leg_gap(t):
        """Close the gap as the far leg passes behind the near shin at the bottom of the stroke.

        There the gap would slice the far leg into thin floating slivers that read as a flash.
        """
        phase = abs((t + 0.54) % 1 - 0.5)
        s = max(0.0, min(1.0, (phase - 0.13) / 0.11))
        return s * s * (3 - 2 * s)

    def motion(t):
        a = start + TAU * t
        return dict(
            frame=(0.0, 0.0, rock * math.sin(2 * TAU * t)),
            arms=[("ik", hands[0]), ("ik", hands[1])],
            legs=[("ik", crank(a)), ("ik", crank(a + math.pi))],
            hips=[0, 0],
            leg_gap=leg_gap(t),
        )

    belt = None
    wheels = [rig.art.paths[i][0] for i in rig.spec.get("props", [])]
    if wheels:
        tops = [min(y for _, y in w) for w in wheels]
        bottoms = [max(y for _, y in w) for w in wheels]
        wheel_radius = (bottoms[0] - tops[0]) / 2
        belt = o.get("gear", 1.6) * TAU * wheel_radius / duration
        rig.ground = max(bottoms) - rig.p["rf"]
        rig.road_note = "Rolling at the speed this cadence would drive the wheels in a moderate gear."
    return motion, duration, belt


def celebrate(rig, o):
    """The normal activity loop, with a celebration that comes and goes on top of it.

    The legs never stop: they come straight from the activity's own motion. The arms punch up
    for two pumps under a burst of confetti, drop back into their normal action, then rise
    again. Half the routine is celebrating and half is the normal loop. The routine fits a
    whole number of activity cycles, and each change lands where the near arm is already
    back, so neither the loop nor the blend has a jump.
    """
    p = rig.p
    activity = o.get("activity", "walk")
    routine = o.get("duration", 4.08)
    cycles = o.get("cycles", {"walk": 4, "run": 6, "pedal": 6}[activity])
    base, _, belt = BUILDERS[activity](rig, {**o.get("base", {}), "duration": routine / cycles})
    rig.sub_cycles = cycles
    rig.still_t = 0.0
    rig.confetti = o.get("colors", ["#FFC83D", "#FF5C7A", "#3DD6C6", "#6C8CFF", "#B98CFF"])
    rig.head_lag = 0.012
    rig.full_body = activity == "pedal"  # a rider sits up, so the torso and head need every frame
    posture = rig.spec.get("posture", {})
    normal_tilt = rig.neck_tilt if rig.neck_tilt is not None else 0.0
    high_tilt = posture.get("celebrate_tilt", 0 if activity == "pedal" else 6)
    lean = math.degrees(math.atan2(p["cx"] - p["px"], p["py"] - p["cy"]))
    sit_up = lean - 18 if activity == "pedal" else 0.0
    low_upper, low_flex = 98, 44
    high_upper, high_flex = o.get("raise", 124), 6
    # A pump: a quick punch up, a slower fall.
    beat = [(0.0, [1.0]), (0.12, [0.95]), (0.62, [0.15]), (0.76, [0.2]), (1.0, [1.0])]

    def blend(t):
        """1 while celebrating, 0 in the normal loop, easing between them."""
        t %= 1
        if t < 0.42:
            s = 1.0
        elif t < 0.5:
            s = 1 - (t - 0.42) / 0.08
        elif t < 0.92:
            s = 0.0
        else:
            s = (t - 0.92) / 0.08
        return s * s * (3 - 2 * s)

    # A rider's head moves with the sit-up. Otherwise it holds still, so its track can repeat.
    if activity == "pedal":
        rig.neck_tilt = lambda t: normal_tilt + (high_tilt - normal_tilt) * blend(t)
    else:
        rig.neck_tilt = lambda t: high_tilt

    def motion(t):
        m = dict(base(t * cycles % 1))
        amount = blend(t)
        pump = min(1.0, max(0.0, spline(beat, t * 4 % 1, periodic=True)[0]))
        upper = low_upper + (high_upper - low_upper) * pump
        flex = low_flex + (high_flex - low_flex) * pump
        raised = [(upper, -flex), (-upper, flex)]
        if activity == "pedal":
            pair = 0 if rig.spec.get("twin_arms") else 1  # twin arms share one rest pose
            normal = [(p["a0"], p["f0"]), (p[f"a{pair}"], p[f"f{pair}"])]
            dx, dy, pitch = m["frame"]
            m["leg_frame"] = m["frame"]
            m["frame"] = (dx, dy, pitch - sit_up * amount)
        else:
            normal = [m["arms"][0][1:], m["arms"][1][1:]]
        m["arms"] = [
            ("fk", n[0] + (r[0] - n[0]) * amount, n[1] + (r[1] - n[1]) * amount)
            for n, r in zip(normal, raised)
        ]
        return m

    return motion, routine, belt


def keys(rig, o):
    """Any other activity: poses given as offsets from rest at chosen cycle times.

    Each key: {"t": 0.5, "pelvis": [dx, dy], "pitch": deg, "arms": [[angle, flex], [angle, flex]],
    "feet": [[dx, dy], [dx, dy]]}. Omitted fields stay at rest. The rest pose is added at t = 0 and 1.
    """
    p = rig.p
    duration = o.get("duration", 1.0)
    feet = [rig.rest_legs[0][2], rig.rest_legs[1][2]]

    def row(k):
        pelvis = k.get("pelvis", [0, 0])
        arms = k.get("arms", [[0, 0], [0, 0]])
        moved = k.get("feet", [[0, 0], [0, 0]])
        return [*pelvis, k.get("pitch", 0), *arms[0], *arms[1], *moved[0], *moved[1]]

    table = [(0.0, row({}))] + [(k["t"], row(k)) for k in o["keys"]] + [(1.0, row({}))]

    def motion(t):
        v = spline(table, t % 1, periodic=True)
        return dict(
            frame=(v[0], v[1], v[2]),
            arms=[("fk", p["a0"] + v[3], p["f0"] + v[4]), ("fk", p["a1"] + v[5], p["f1"] + v[6])],
            legs=[
                ("ik", (feet[0][0] + v[7], feet[0][1] + v[8])),
                ("ik", (feet[1][0] + v[9], feet[1][1] + v[10])),
            ],
            hips=[1, -1],
        )

    return motion, duration, None


BUILDERS = dict(walk=walk, run=run, pedal=pedal, celebrate=celebrate, keys=keys)


def build(kind, rig, options):
    if kind not in BUILDERS:
        raise SystemExit(f"Unknown motion {kind}; choose from {', '.join(BUILDERS)}.")
    return BUILDERS[kind](rig, options)
