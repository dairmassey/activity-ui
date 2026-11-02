#!/usr/bin/env python3
"""Check a baked SVG and render a contact sheet in Chrome and, where available, WebKit.

usage: verify.py <out.svg> <work dir> [--source original.svg] [--crop x,y,w,h]
Writes sheet-chrome.png, sheet-webkit.png and first-frame.png into the work dir.
--crop adds crop-chrome.png: 12 close-up frames of one region, for judging joints.
"""
import math
import re
import shutil
import subprocess
import sys
import xml.dom.minidom
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HERE = Path(__file__).parent

SHEET = """<!doctype html><meta charset="utf-8"><title>sheet</title>
<style>body{{margin:0;background:{bg};color:{ink};font:12px system-ui}}
#g{{display:grid;grid-template-columns:repeat(8,1fr);gap:4px;padding:8px}}
figure{{margin:0;text-align:center}}object{{width:150px;height:auto;display:block;margin:auto}}</style>
<div id="g"></div><script>
const g=document.getElementById('g'),T={dur};
for(let i=0;i<16;i++){{const f=document.createElement('figure'),o=document.createElement('object');
o.type='image/svg+xml';o.data='{url}';o.onload=()=>{{const s=o.contentDocument.documentElement;s.pauseAnimations();s.setCurrentTime(T*i/16)}};
f.append(o,document.createTextNode((i/16).toFixed(3)));g.append(f)}}
</script>"""

CROP = """<!doctype html><meta charset="utf-8"><title>crop</title>
<style>body{{margin:0;background:{bg};color:{ink};font:12px system-ui}}
#g{{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;padding:6px}}
figure{{margin:0;text-align:center}}object{{width:210px;height:{h}px;display:block;margin:auto}}</style>
<div id="g"></div><script>
const g=document.getElementById('g'),T={dur};
for(let i=0;i<12;i++){{const f=document.createElement('figure'),o=document.createElement('object');
o.type='image/svg+xml';o.data='{url}';o.onload=()=>{{const s=o.contentDocument.documentElement;s.setAttribute('viewBox','{crop}');s.setAttribute('width','100%');s.setAttribute('height','100%');s.pauseAnimations();s.setCurrentTime(T*i/12)}};
f.append(o,document.createTextNode((i/12).toFixed(3)));g.append(f)}}
</script>"""

FIRST = """<!doctype html><meta charset="utf-8"><title>first</title>
<style>body{{margin:0;background:{bg}}}object{{display:block;width:{w}px;height:{h}px;position:absolute;left:10px;top:10px}}
svg{{position:absolute;left:{ow}px;top:10px;width:{w}px;height:{h}px}}#b{{left:{ow}px}}</style>
<object id="a" type="image/svg+xml" data="{url}"></object><object id="b" type="image/svg+xml" data="{url}"></object>
<svg viewBox="{view}"><g fill="#ff3b3b" fill-opacity=".55">{paths}</g></svg>
<script>for(const id of 'ab'){{const o=document.getElementById(id);o.onload=()=>{{const s=o.contentDocument.documentElement;s.pauseAnimations();s.setCurrentTime(0)}}}}</script>"""


def main():
    args = sys.argv[1:]
    source = crop = None
    if "--crop" in args:
        at = args.index("--crop")
        crop = args[at + 1]
        del args[at:at + 2]
    if "--source" in args:
        at = args.index("--source")
        source = Path(args[at + 1]).resolve()
        del args[at:at + 2]
    if len(args) != 2:
        raise SystemExit(__doc__)
    svg_path, work = Path(args[0]).resolve(), Path(args[1]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    text = svg_path.read_text()
    xml.dom.minidom.parseString(text)
    tracks = re.findall(r' values="([^"]+)"', text)
    broken = [i for i, v in enumerate(tracks) if v.split(";")[0] != v.split(";")[-1]]
    dur = max(float(d) for d in re.findall(r'dur="([\d.]+)s"', text))
    view = re.search(r'viewBox="([^"]+)"', text).group(1)
    print(f"xml ok  tracks {len(tracks)}  loop mismatches {broken}  cycle {dur}s  bytes {len(text)}  viewBox {view}")

    light = re.search(r'<g fill="(white|#fff|#ffffff)"', text, re.I) is not None
    bg, ink = ("#18232f", "#afbdca") if light else ("#f4f6f8", "#44515e")
    url = svg_path.as_uri()
    (work / "sheet.html").write_text(SHEET.format(bg=bg, ink=ink, dur=dur, url=url))
    pages = [("sheet.html", "sheet-chrome.png", "1300,600")]
    if crop:
        box = [float(v) for v in crop.split(",")]
        tall = round(210 * box[3] / box[2])
        (work / "crop.html").write_text(CROP.format(
            bg=bg, ink=ink, dur=dur, url=url, crop=crop.replace(",", " "), h=tall))
        pages.append(("crop.html", "crop-chrome.png", f"1300,{2 * tall + 60}"))
    if source:
        vx = [float(v) for v in view.split()]
        scale = 7
        paths = "".join(f'<path d="{d}"/>' for d in re.findall(
            r'\sd="([^"]+)"', re.sub(r"<(mask|clipPath|defs)\b.*?</\1>", "", source.read_text(), flags=re.S)))
        (work / "first.html").write_text(FIRST.format(
            bg=bg, url=url, view=view, paths=paths, w=vx[2] * scale, h=vx[3] * scale, ow=vx[2] * scale + 30))
        pages.append(("first.html", "first-frame.png", f"{int(vx[2] * scale * 2 + 50)},{int(vx[3] * scale + 20)}"))
    for page, png, size in pages:
        subprocess.run([
            CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
            f"--window-size={size}", "--virtual-time-budget=4000",
            f"--screenshot={work / png}", (work / page).as_uri(),
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        print("wrote", work / png)

    swiftc = shutil.which("swiftc")
    if not swiftc:
        print("swiftc not found: WebKit check skipped")
        return
    helper = work / "webkit_shot"
    if not helper.exists():
        subprocess.run([swiftc, "-O", str(HERE / "webkit_shot.swift"), "-o", str(helper)],
                       stdin=subprocess.DEVNULL, check=True, timeout=120)
    subprocess.run([str(helper), (work / "sheet.html").as_uri(), str(work / "sheet-webkit.png"), "1300", "600", "3"],
                   stdin=subprocess.DEVNULL, timeout=40)
    print("wrote", work / "sheet-webkit.png")


if __name__ == "__main__":
    main()
