#!/usr/bin/env python3
"""Write dark-mode and light-mode copies of a baked SVG, and a page to compare them.

usage: themes.py <out.svg> [--dark "#FFFFFF"] [--light "#000000"]
Writes <out>.dark.svg and <out>.light.svg beside the source. The input is not changed.
Only the figure and its props change colour. Confetti keeps its colours, and the cut-out
gaps between limbs are real transparency, so they work on any background.
"""
import re
import sys
from pathlib import Path


def recolour(svg, fill):
    new, count = re.subn(r'<g fill="[^"]+">', f'<g fill="{fill}">', svg, count=1)
    if not count:
        raise SystemExit("No figure group found; bake the SVG with rig.py first.")
    return new


def main():
    args = sys.argv[1:]
    colours = {"dark": "#FFFFFF", "light": "#000000"}
    for name in tuple(colours):
        flag = f"--{name}"
        if flag in args:
            at = args.index(flag)
            colours[name] = args[at + 1]
            del args[at:at + 2]
    if len(args) != 1:
        raise SystemExit(__doc__)
    source = Path(args[0])
    svg = source.read_text()
    for name, fill in colours.items():
        target = source.with_suffix(f".{name}.svg")
        target.write_text(recolour(svg, fill))
        print("wrote", target)


if __name__ == "__main__":
    main()
