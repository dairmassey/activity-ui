---
name: animate-pictogram
description: Turn a flat SVG pictogram of a person into a smooth, looping animated SVG of that figure doing an activity (walking, running, cycling, jumping jacks, waving, dancing, stretching, or anything else) while keeping the look of the original icon. Use this whenever someone wants a stick figure, person icon, fitness icon, wayfinding figure or sports pictogram to move, walk, run, jump or otherwise come alive, even if they only say "make this icon walk", "animate my logo guy" or "can this SVG move", and whenever an earlier attempt at animating such an icon came out stiff, seamed or broken. Output is a small self-contained SVG with no JavaScript that also works inside an img tag.
---

# Animate a pictogram

Turn a static figure into a looping SVG by fitting a skeleton to the artwork and driving that skeleton with real motion. The result is usually 10 to 15 KB, needs no script, and plays in an `<img>` tag.

Do not cut the source outline into pieces and rotate them. That approach leaves seams at every joint and blobs at the hips, and no amount of tuning rescues it. Capsules that overlap in one colour have no seams to hide.

Everything below runs from `scripts/` in this skill, with Python 3.9+ and Pillow. Run commands with absolute paths, and give each one `</dev/null` if it could ever wait on input.

## Workflow

### 1. Protect the source

Work in a new folder and write output to a new file such as `name.animated.svg`. Do not overwrite the user's art, because the fit needs it and they will want to compare against it. If an old attempt exists, look at it to learn what went wrong, then keep it rather than patching it.

### 2. Look at the art

```bash
python3 scripts/svgart.py inspect source.svg grid.png
```

Read `grid.png`, which marks every 10 units, and the printed subpath list. Work out:

- **Where the joints are**: chest, pelvis, each elbow and hand, each knee and foot.
- **Props**: anything that is not the body, such as wheels, balls or equipment. Note their path indexes.
- **Hidden limbs**: icons often draw one arm or leg where the activity needs two. Mark these as twins (see the spec).
- **Facing**: the rig assumes the figure faces right. Mirror left-facing art first.

If the script reports that it needs paths, the file has live shapes or strokes. Ask the user to export outlined paths.

### 3. Write the spec

Create `figure.json` beside a copy of the source. `references/spec.md` has every field, and `assets/examples/` has working specs for each motion. Copy the closest example. Joints only need to be close, because the fit refines them.

Pick the limbs so `arms[0]` and `legs[0]` are the near pair, drawn on top. For walking and running they must be opposite limbs: the forward leg with the back arm.

Choose the shoulder style:

- `"roll"` for most figures, including hands gripping handlebars. This keeps the shoulder line one smooth curve from the back into the arm at every angle.
- `"fixed"` only for arms raised above the shoulders, where the arm leaves the chest from its side.

Choose the motion:

| Activity | Motion | Rest pose it expects |
| --- | --- | --- |
| Walking, hiking, marching | `walk` | Mid-stride, both feet near the ground |
| Running, jogging, sprinting | `run` | Airborne: front leg reaching, back leg trailing |
| Cycling, spinning, rowing machines with a crank | `pedal` | Near foot on the crank, hands on the bars |
| A win, a finished goal, a celebration | `celebrate` | The same pose as its `activity`: walk, run or pedal |
| Anything else | `keys` | Any pose |

If the art does not suit a built-in motion, use `keys`. It handles any activity: see the section below.

### 4. Fit the skeleton

```bash
python3 scripts/rig.py fit figure.json
```

Read `figure.fit.png`. White is covered, red is art the rig missed, blue is rig outside the art. Aim for an overlap of 0.92 or better, but trust the picture over the number: overlap cannot see lumps or a misplaced joint. If a limb is clearly in the wrong place, correct that joint in the spec and fit again.

### 5. Bake and verify

```bash
python3 scripts/rig.py bake figure.json out.svg
python3 scripts/verify.py out.svg check --source source.svg --crop x,y,w,h
```

`verify.py` confirms the file is valid and the loop closes, then renders 16 frames in Chrome and WebKit. Read `check/sheet-chrome.png`, `check/sheet-webkit.png` and `check/first-frame.png`. Without Chrome, open `out.preview.html` in any browser instead.

`--crop` adds `check/crop-chrome.png`: 12 close-up frames of a region given in the SVG's coordinates. Always crop to the shoulders and arms. Contact sheets are too small to judge joints, and problems there are easy to miss.

### 6. Review the frames with a critical eye

The mid-motion frames are where problems live, because the arms stop hiding the body there. Go through the table, change the spec, and bake again. Baking takes about a second, so iterate freely.

Frames show shapes, not weight, so a run can pass every check and still feel wrong. Think about how the activity really moves: where the body is highest, where the weight lands, what the arms do. When a user says something feels off, question the assumption behind the motion before adjusting numbers.

| What you see | Why | Fix |
| --- | --- | --- |
| Hunched, head craning forward | The icon's lean reads as a stoop once the arms drop, and icons often place the head further forward than the spine | Raise `posture.upright` (3 to 6). Keep `posture.neck_tilt` no more than the torso's lean: about 10 upright, about 40 on a bike. Do this even when it moves the head from the source |
| Head floats away from the body | Moving the head kept a source distance that ran diagonally past an arm | The neck is now set by the gap above the chest, measured from the source art by default, so it matches the logo. `bake` prints it. A moving figure can read wider than the still logo, so if asked, set `posture.neck_gap` to about 0.28 of the head radius. Below about 0.2 it reads too close. In a celebration, lower `raise` so the arms still clear the head |
| Crouching or kneeling mid-move | The body stayed low while the legs needed room | Raise the body at that moment: pelvis `dy` negative. A straight leg reaches `thigh + shin` from the hip |
| Lumps, dimples or a notch on the shoulders | Arm roots poking past the chest, or arms starting below a round chest | Use `"roll"`, and do not add separate shoulder shapes |
| Chest swells and shrinks, or a sharp corner at the back | Shoulders sliding along the body, or the top of the arm fitted as a wide cone | Same fix, and refit. The fit keeps arms close to arm width. The chest must keep one size |
| Arm stroke looks inconsistent | The far arm vanishes into the torso, so every second stroke disappears | The far arm goes behind the torso with a thin gap below the chest, so it visibly passes behind. Compare frames half a cycle apart |
| Both arms look stuck on the front of the chest | `arms_in_front` puts the far arm over the torso, and outlines make that obvious | Leave `arms_in_front` off, so the near arm stays in front and the far arm goes behind |
| Lumpy butt: a bump with a dent below it as the thigh swings | The round pelvis shows past a thigh joined inside it | The thigh root now rolls inside the pelvis, the same way the arm root does in the chest. Keep `hips` at `"roll"` and refit |
| Feet skate | Foot paths do not match the ground speed | Use `walk`/`run` paths. In `keys`, keep a planted foot's offset constant |
| Limbs merge into a blob | Overlapping solid limbs | Check that the near pair is set correctly. Halos need the right limb on top |
| Arm spins the wrong way round | A key asks for the long way round | Add a key between the two poses |
| Knees jerk at push-off and landing | The leg reaches full stretch, where the knee moves fastest and then whips into a bend | Lower `leg_reach` or raise `sit`, and check the knee stays bent through both moments. Keep `bob` low enough that the planted foot stays on the ground |
| Arms swing too far behind | The back arm copies the icon's pose, which can be wider than a real swing | Set `arm_back` to about the same angle as the forward swing |
| Stompy, heavy landings | The body stops sharply at a low point, or the foot stays high and drops steeply onto a straight leg | Keep body height on a smooth curve, land the foot close under the body, and land with the knee already bent. A walking foot peaks just after it lifts, then skims low. Measure lift mid-swing and knee bend at touchdown rather than judging frames |
| Does not feel like a run | The body moves backwards from reality, or the arms hang | A runner is highest in flight and lowest at mid-stance. Treat a striding runner icon as the airborne moment, not the landing |
| Speed across the page does not match the leg tempo | Each step covers far less ground than the legs seem to reach, so the figure churns without getting anywhere. Moving it faster would just make the feet slide | Read the step length from `bake`. Lengthen the stride instead: shorter foot contact and a longer sweep under the body, until a step is about half the figure's height |
| Arms too long | The fit copies the pose's reach, which can make an arm as long as a leg, and bent elbows only hide that | Set `arm_scale` until `bake` reports the arm at about 65 to 75% of the leg. Keep a runner's elbows fairly open, about 35 to 55 degrees |
| Arms look shorter in one animation of a set | The bones match, but folded elbows pull the hand in, so a run at 80 degrees reads shorter than a raised arm at the same length | Open the elbows with `elbow_back`, `elbow_front` and `elbow_pump`. A celebrate spec passes the same values in `motion.base` so its normal section matches |
| Arms look fat | The fit took thickness from a heavy pose or a merged shoulder | Set `arm_width`, about 0.48 of the head's radius, and use the same value across a set. Shortening and slimming add up, so change one at a time and compare versions side by side |
| Arm melts into the body as a blob | The gap only covered the forearm | The gap now runs up to the armpit. Set `arm_cut_from` lower to start it nearer the shoulder |
| A brief flash where two limbs cross | The gap cuts what is left of the far limb into thin floating slivers for a few frames. Step through the crossing in close-ups, because normal frames miss it | Narrow the gap to nothing during that crossing and let it return smoothly. The `pedal` motion does this with `leg_gap` |
| A small notch at the edge of the shoulder | The arm's gap starts so high it pokes out through the body | Raise `arm_cut_from`. The default is 0.62 |
| A line cuts the torso from the chest | Two front arms' gaps meet across the chest | Raise `arm_cut_from`. The default for front arms is 0.72 |
| Celebration feels generic or cheap | Replacing the activity with a stock jump loses the figure's identity, and a neat ring of sparks reads as a spinner | Keep the activity running, let the celebration come and go on top of the normal loop, and use tumbling confetti that bursts up and drifts down |
| Bumps on a figure under confetti | Confetti in the figure's own colour merges with it as it passes behind | Leave that colour out of `colors` |
| Hand vanishes into the head | The figure is side-on, so straight up means through the head | Raise the arm out in front or behind, about 120 to 140 degrees from hanging, and move the forearm instead |

Run one finished file through SVGO with its default settings before handing it over, and render the result. Many build pipelines do this automatically, and it deletes anything that looks hidden. So confetti starts at a tiny opacity rather than 0, and the still pose is hidden inside a media query.

Also check that no limb flips suddenly between frames, and that the figure still looks like the source at frame 0. When the user dislikes something, fix the cause in the rig rather than painting over the symptom, and look at every other frame afterwards: a fix for one pose can create a new flaw in another.

For dark-mode and light-mode versions, run this on the finished SVG:

```bash
python3 scripts/themes.py out.svg
```

It writes `out.dark.svg` and `out.light.svg`. Only the figure and props change colour; `--dark` and `--light` set them. Check both on real backgrounds, because a colour that disappears on one can be fine on the other.

For native iOS and Android apps, also export Lottie. SVG animation only plays in browsers and web views:

```bash
python3 scripts/rig.py bake figure.json out.svg --lottie out
```

This writes `out.dark.json` and `out.light.json` from the same frames as the SVG, using only keyframes, shapes and track mattes. Compare them against the SVG at the same moments in more than one player, because a matte that works in one can fail in another.

### 7. Deliver

Show the user `out.preview.html`, which is self-contained and has the source beside the animation, a scrubber, and a foot-slide test for walking and running. Tell them plainly:

- how far frame 0 moved from the source, and why (posture changes and added limbs both do this)
- the new canvas size, because the viewBox grows to fit the motion, and a layout that forces the old size will shrink the figure
- which browsers you checked

## Making a matched set

When several icons must read as one family, give them the same routine and let the activity differ. Matching means matching by eye, not by number: tune `arm_ratio` per figure, because bodies differ. To make one figure share another's build, use `borrow_body`, then check its knee bend and foot contact, because different legs change the hip height and stride that work. In `celebrate`, all of them share the routine length, arm pumps and confetti. Compare arm length with the figure's normal animation too: `bake` reports it, and raised arms read longer than swinging ones. Review them together in one sheet. Leave the original art and any existing animations alone, and confirm that with checksums before you finish.

## Designing a `keys` motion

Think like an animator: choose 2 to 4 poses that define the activity, then let the spline connect them. Each key is an offset from the rest pose, so anything you leave out stays at rest, and the rest pose itself is added at `t: 0` and `t: 1`.

Work out the body height first. At any key, the distance from hip to foot must be at most `thigh + shin` from the fit output. If legs straighten at a pose, lift the pelvis to match. A jumping jack closing to a stand needs the pelvis much higher than the wide starting pose, and getting this wrong produces kneeling. For a jump, move the feet up with the pelvis so they actually leave the ground.

Angles are degrees: 0 hangs straight down, positive swings backward, negative swings forward. Arm keys are changes from rest, so a raised arm brought down to the side needs a change of about 130. Give the two sides mirrored values for symmetrical moves, and repeat a key to hold a pose.

## Rules the rig already follows

These came from real corrections, so keep them if you change the scripts:

- The head is a true circle, not the source's slightly uneven path.
- The two halves of a cycle should look the same, because only the limbs have swapped.
- Near limbs get a thin cut-out gap from the armpit and the knee down, so limbs stay readable where they cross and the shoulder stays joined. It is a real mask, so it works on any background.
- The head trails the body slightly, which stops it looking bolted on.
- Reduced-motion viewers get the source art, still. `celebrate` shows its peak pose instead, since that is the moment worth keeping.
- Bones keep their angles unwrapped, so a limb never whips the long way round.
- The first and last frames are the same frame, so the loop cannot jump.
- Arm and thigh roots both roll inside the torso, so the shoulder and seat stay smooth curves.
