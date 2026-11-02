# Spec reference

A spec is a JSON file beside a copy of the source SVG. Working examples are in `assets/examples/`. All coordinates are in the source SVG's units. Read them from the sheet made by `svgart.py inspect`.

## Figure fields

| Field | Required | Meaning |
| --- | --- | --- |
| `source` | yes | Source SVG filename, relative to the spec |
| `label` | no | Accessible name for the animation |
| `chest`, `pelvis` | yes | `[x, y]` centres of the upper and lower torso |
| `arms` | yes | Two entries, each `{"elbow": [x, y], "hand": [x, y]}`. `arms[0]` is the near arm |
| `legs` | yes | Two entries, each `{"knee": [x, y], "foot": [x, y]}`. `legs[0]` is the near leg |
| `props` | no | Path indexes kept as static artwork behind the figure, such as wheels |
| `shoulders` | no | `"roll"` (default) for most figures, `"fixed"` for arms raised above the shoulders |
| `hips` | no | `"roll"` (default) keeps the seat a smooth curve. `"fixed"` uses set hip positions |
| `credit` | no | Text stored invisibly in the file, such as `Run animated by Your Name`. Goes in an SVG comment and metadata, and in Lottie metadata. The comment starts with `!`, so SVG optimizers keep it by default. Only add a copyright line if the author owns the work |
| `borrow_body` | no | Filename of another figure's `.rig.json`. Gives this figure that one's torso and leg proportions, keeping its own head, overall height and pose. Re-check the stride afterwards: `bake` adjusts hip height and stride for the new legs |
| `arm_width` | no | Sets arm thickness as a share of the head's radius, such as `0.44`. Use it when a fit leaves arms fat, or to match a set of figures |
| `arm_ratio` | no | Sets the arm to this share of the leg and evens out its two bones. Use it to match a set of figures |
| `arm_scale` | no | Multiplies the fitted arm length and evens out the upper arm and forearm. `bake` prints the arm as a share of the leg: aim for 65 to 75% |
| `arm_cut_from` | no | How far along the upper arm the gap starts, 0 to 1. Default 0.62, or 0.72 with `arms_in_front` |
| `arms_in_front` | no | Draws both arms in front of the torso. Default `false`: the near arm stays in front, and the far arm goes behind with a thin gap below the chest |
| `twin_arms`, `twin_legs` | no | `true` when the art draws one limb for the pair. Both entries then share a rest pose |
| `chest_radius`, `pelvis_radius` | no | Starting sizes for wide or heavy torsos |
| `posture` | no | `{"upright": degrees, "neck_tilt": degrees, "neck_gap": units}`. `upright` stands the torso up from the source lean. `neck_tilt` puts the head that far forward of straight above the chest, and `null` keeps the source's head position. `neck_gap` is the clear space between head and chest, measured from the source art by default |
| `halo` | no | `false` removes the cut-out gaps between crossing limbs |
| `frames` | no | Samples per cycle, default 36. Motion stays smooth between samples |
| `motion` | no | Motion block below, default `{"type": "walk"}` |

`hand` and `foot` mean the centre of the rounded end, about one limb radius in from the tip.

Twin limbs change the first frame: the second limb appears for the motion, so frame 0 cannot match a source that drew only one. Say so when delivering.

## Motion block

Set `"type"`, plus any options. Sizes default to a fraction of the art's height, so they scale with the icon. `duration` is seconds per cycle.

### `walk`

| Option | Default | Effect |
| --- | --- | --- |
| `duration` | 1.2 | One cycle is two steps |
| `double_support` | 0.08 | Fraction of each step with both feet down |
| `bob` | 0.92% of height | Half the vertical travel of the pelvis |
| `sit` | 0.35% of height | Lowers the body into the legs, so they stay off full stretch |
| `leg_reach` | 0.99 | Share of the leg it may stretch to. Past this the foot peels up instead of the knee snapping |
| `arm_back` | rest angle of the back arm | How far the arms swing behind the body, in degrees |
| `surge` | 0.56% of height | Speed-up and slow-down along the walk |
| `lean` | 1.2 | Torso pitch, degrees |
| `foot_lift` | 8.2% of height | Peak foot height, just after it lifts. It then skims low |
| `soft_landing` | 0.06 | Shortens the reach by this share of the leg, so the knee is bent at touchdown |
| `swing_tangent` | 0.5 | How much ground speed the foot keeps as it lifts |

Default posture: `upright` 5, `neck_tilt` 11.

### `run`

The rest pose is treated as the airborne moment: the near leg reaches forward and the far leg trails. The feet leave the rest pose, sweep down to land, push off, and return. The ground sits a little below the rest pose's front foot.

| Option | Default | Effect |
| --- | --- | --- |
| `duration` | 0.68 | One cycle is two strides, about 176 steps a minute |
| `land`, `toe_off` | 0.145, 0.355 | Cycle times a foot touches down and leaves. Shorter contact covers more ground per stride |
| `sink` | 1.2% of height | How far the body drops at mid-stance. Too much reads as sitting |
| `ground` | 3% of height below the front foot | `y` of the foot centre when planted |
| `foot_land` | 16% of the leg ahead of the pelvis | `x` of landing. Much further forward lands on a stiff leg and looks stompy |
| `foot_off` | 33% of the leg behind the pelvis | `x` of toe-off. Too far back and the leg runs out of reach, so the foot slides |
| `tuck` | behind and below the hip | `[x, y]` the foot passes through in recovery |
| `arm_back`, `arm_front` | rest angles, limited to 88 and -45 | Upper arm swing |
| `elbow_back`, `elbow_front` | rest bend of the back arm, 80 | Elbow bend at each end of the swing |
| `elbow_pump` | 14 | Extra elbow bend as the arm passes the body |
| `lean` | 1.5 | Torso pitch, degrees |

Healthy knee bend on the planted leg is about 20 degrees at landing and 50 at mid-stance, easing as the leg pushes off.

The ground speed comes from the stance foot: `foot_land` minus `foot_off`, divided by the contact time. `bake` prints the resulting step length. Aim for at least half the figure's height, roughly the spread of the feet in the pose, so the speed across the page matches the tempo of the legs.

Default posture: `upright` 6, `neck_tilt` 10.

### `pedal`

The hips stay on the saddle and the upper body stays quiet, so the legs do the work. Hands stay on their rest positions, and the far leg starts half a turn from the near leg. Default posture: `upright` 0, `neck_tilt` 38, which keeps the head in line with the leaning spine.

| Option | Default | Effect |
| --- | --- | --- |
| `duration` | 0.75 | One crank turn, about 80 rpm |
| `crank` | 10% of height | Crank radius |
| `start_angle` | 0 | Where the near foot starts: 0 is the bottom of the stroke, 90 is the back |
| `rock` | 0.8 | Torso pitch per pedal stroke, degrees |
| `gear` | 1.6 | Wheel turns per crank turn. With wheels as `props`, this sets the speed in the preview's road test |

### `celebrate`

The normal activity loop with a celebration that comes and goes on top of it. The legs never stop: they come straight from the activity's own motion. For the first half of the routine the arms give two overhead pumps under bursts of confetti that fall behind the figure. For the second half the figure carries on as normal, then the routine repeats. Riders sit up off the bars to salute and settle back onto them. The first frame is the logo's stride with the arms raised.

| Option | Default | Effect |
| --- | --- | --- |
| `activity` | `walk` | `walk`, `run` or `pedal` |
| `raise` | 124 | How high the arms go, in degrees from hanging. Lower it if an arm touches the head |
| `duration` | 4.08 | One full routine |
| `cycles` | 4 for walk, 6 otherwise | Activity cycles per routine. Keep the routine a whole number of cycles, and an even number, so each change lands with the near arm back |
| `colors` | gold, coral, teal, blue, violet | Confetti colours. Use the brand's palette when there is one: read it from the brand's own app icons or site. Leave out the figure's own colour, or pieces merge with it as bumps |
| `base` | none | Options passed to the activity's motion |

Set `arm_ratio` beside `motion` to give several figures the same arm-to-leg share. Start around `0.65` with an `arm_width` of `0.48`, then tune each figure by eye. One share does not suit every body: on one three-figure set the walker took `0.62`, the rider `0.65` and the runner `0.70`, because leg length and head size differ. Change one thing at a time, because length and thickness add up. Reduced-motion viewers see the raised-arm pose with a still scatter of confetti.

### `keys`

`duration` defaults to 1.0. `keys` lists the poses in time order. The rest pose is added automatically at `t: 0` and `t: 1`.

```json
{"type": "keys", "duration": 1.1, "keys": [
  {"t": 0.25, "pelvis": [0, -13], "pitch": 0, "arms": [[-65, 8], [65, 8]], "feet": [[-7, -9], [11, -9]]},
  {"t": 0.5, "pelvis": [0, -9], "arms": [[-135, 12], [135, 12]], "feet": [[-13, 0], [22, 0]]}
]}
```

| Key field | Meaning |
| --- | --- |
| `t` | Cycle time, between 0 and 1 |
| `pelvis` | `[dx, dy]` body offset. Negative `dy` is up |
| `pitch` | Torso pitch in degrees. Positive leans forward |
| `arms` | `[[angle, flex], [angle, flex]]`: changes to the upper arm angle and the elbow bend, near arm first |
| `feet` | `[[dx, dy], [dx, dy]]`: foot offsets, near leg first. `[0, 0]` keeps a foot planted however the body moves |

Default posture keeps the source lean and head position.
