#!/usr/bin/env python3
"""img/_raw/*.png (bare emulator captures) -> img/shot-*.webp (what the pages load).

Called by _shoot_web.sh; safe to run on its own if the raws are already there.

THIS IS THE WHOLE OF THE IMAGE PIPELINE, AND IT DELIBERATELY DOES ALMOST NOTHING.
No frame, no bezel, no rounded corners, no drawn outline, no background plate baked into the pixels
(BRAND.md §3 — the website is UNFRAMED, and a hand-drawn bezel is banned outright). A screenshot that
arrives with its own homemade border is exactly the thing we are removing. The PAGE gives the shot its
ground: a trail-tinted terrain plate, a real shadow and a caption, in CSS, in both themes.

So all that happens here is: downscale to a sane web width, and encode WebP.
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "img", "_raw")
OUT = os.path.join(HERE, "img")

# raw name -> (published name, target width in px, pixels to cut off the TOP of the raw)
# 720 px is 2x the 300 px the hero shot is ever displayed at, and 2x is where a phone screenshot stops
# getting visibly better.
#
# WHY story.png IS CROPPED AND THE OTHER TWO ARE NOT — DO NOT "TIDY" THIS AWAY.
# The story shot is taken with the landmark sheet OPEN over the trail spine. iOS scrolls the list under
# the status bar and draws the clock straight on top of it, so the raw capture has "09:41" printed
# across the word "Castrojeriz" — on the page that reads as a rendering bug, not as an app. Cutting the
# status bar alone slices the Castrojeriz card's title in half, so the cut is taken at the card BOUNDARY
# below it: the shot then opens on a clean card and the León sheet, which is what the paragraph beside
# it is actually about. This is a crop of a real capture — nothing is painted, moved or invented.
SHOTS = {
    "journey.png": ("shot-journey.webp", 720, 0),
    "story.png":   ("shot-story.webp",   720, 430),
    "medals.png":  ("shot-medals.webp",  720, 0),
}


def main():
    if not os.path.isdir(RAW):
        raise SystemExit(f"no raw captures at {RAW} — run ./_shoot_web.sh first")
    for src, (dst, width, crop_top) in SHOTS.items():
        p = os.path.join(RAW, src)
        if not os.path.exists(p):
            print(f"  -- {src}: not captured, leaving {dst} as it was")
            continue
        im = Image.open(p).convert("RGB")
        if crop_top:
            im = im.crop((0, crop_top, im.width, im.height))
        h = round(im.height * width / im.width)
        im = im.resize((width, h), Image.LANCZOS)
        im.save(os.path.join(OUT, dst), "WEBP", quality=82, method=6)
        print(f"  {src} -> {dst}  {width}x{h}"
              + (f"  (top {crop_top}px cropped)" if crop_top else ""))


if __name__ == "__main__":
    main()
