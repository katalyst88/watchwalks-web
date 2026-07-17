#!/usr/bin/env python3
"""ONE source of truth for trail colour on the website.

The site used to carry FOUR hand-copied snapshots of the trail palette:

  * `COLOR = {...}` in `_gen_trailmaps.py`
  * `COLOR = {...}` in `_gen_satmaps.py`
  * `style="--tc:#XXXXXX"` baked into every card in `trails.html`
  * the same, baked into the 12 teaser rows + the Inca profile in `index.html`

They had already drifted apart: on 2026-07-13, twelve trails had a `--tc` in the HTML that
disagreed with the app's own `c1`, and the two generators still held the ORIGINAL palette --
the one full of the blue-greys and violets BRAND s3 bans ("no blue-grays"). Because
`_gen_satmaps.py` DRAWS the route line into the .webp, that banned palette is baked into the
pixels of the satellite maps: the West Highland Way's route is painted lavender (#8E6FB0)
inside a card whose frame is brown.

That is exactly how surfaces drift. So nothing here hardcodes a colour. This module reads the
canonical `TrailArt` map out of the Android app and hands `c1` (identity) and `c2` (secondary)
to whatever needs them. When the trail-data layer regenerates `c2`, every website artefact
inherits it by re-running the generators -- no hand-edits, nothing to forget.

    from _trail_colors import C1, C2, load
"""
import os
import re

ART_KT = os.path.join(
    r"C:\Users\jwden\WatchApps",
    "watchwalks-android", "app", "src", "main", "java", "com", "watchwalks",
    "companion", "ui", "components", "TrailArt.kt",
)

# "<id>" to TrailArt(GlyphKind.X, Color(0xFFc1), Color(0xFFc2), ...)
_ENTRY = re.compile(
    r'"([a-z0-9-]+)"\s*to\s*TrailArt\(\s*GlyphKind\.\w+,\s*'
    r'Color\(0xFF([0-9A-Fa-f]{6})\),\s*Color\(0xFF([0-9A-Fa-f]{6})\)'
)


def load(path=ART_KT):
    """-> {trail_id: (c1, c2)} straight from TrailArt.kt. Raises if the file moves or the
    shape of the map changes, rather than silently falling back to a stale copy."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            "TrailArt.kt is the source of truth for trail colour and it is not at %s. "
            "Do NOT paste a palette in here -- fix the path." % path
        )
    src = open(path, encoding="utf-8").read()
    art = {m.group(1): ("#" + m.group(2).upper(), "#" + m.group(3).upper())
           for m in _ENTRY.finditer(src)}
    if len(art) < 30:
        raise ValueError("only %d trails parsed out of TrailArt.kt -- the regex has gone "
                         "stale, and a partial palette is worse than none" % len(art))
    return art


ART = load()
C1 = {k: v[0] for k, v in ART.items()}   # identity colour: cards, route line, profile, spine
C2 = {k: v[1] for k, v in ART.items()}   # secondary: the site does not use it (yet)

if __name__ == "__main__":
    for t in sorted(ART):
        print("%-26s c1=%s  c2=%s" % (t, C1[t], C2[t]))
    print("\n%d trails" % len(ART))
