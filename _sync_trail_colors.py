#!/usr/bin/env python3
"""Rewrite every `--tc:` in the site's HTML from the canonical TrailArt c1.

The `--tc` custom property is what colours a trail card's frame, its background wash, its
elevation silhouette and its spine. It was typed by hand into `trails.html` and `index.html`,
which is why twelve trails had drifted away from the app by 2026-07-13 (Nile was teal #2E9E86
in the app and gold #D0A24E on the website; Tahoe Rim was green in one and orange in the other).

Run this after any change to TrailArt.kt. It invents nothing: every value comes from
`_trail_colors.py`, which reads the app.

    python _sync_trail_colors.py [--check]

--check exits 1 if the HTML disagrees with the app, so it can be a gate rather than a chore.
"""
import os
import re
import sys

from _trail_colors import C1

WEB = os.path.dirname(os.path.abspath(__file__))

# trails.html: <article class="tcard" data-trail="ID" style="--tc:#XXXXXX">
TCARD = re.compile(r'(data-trail="([a-z0-9-]+)"[^>]*?--tc:)(#[0-9A-Fa-f]{6})')
# index.html teaser rows: <div class="trail" style="--tc:#XXXXXX">...<img src="img/trailmaps/ID.webp"
TEASER = re.compile(r'(--tc:)(#[0-9A-Fa-f]{6})("><img class="t-map" src="img/trailmaps/([a-z0-9-]+)\.webp")')
# the Inca hero + homepage profile figure, both keyed to the free trail
INCA = re.compile(r'(<(?:section class="thero"|figure class="why-prof") style="--tc:)(#[0-9A-Fa-f]{6})')


def sync(path, check):
    src = open(path, encoding="utf-8").read()
    drift = []

    def tcard(m):
        want = C1.get(m.group(2))
        if want and want.upper() != m.group(3).upper():
            drift.append((m.group(2), m.group(3), want))
            return m.group(1) + want
        return m.group(0)

    def teaser(m):
        want = C1.get(m.group(4))
        if want and want.upper() != m.group(2).upper():
            drift.append((m.group(4), m.group(2), want))
            return m.group(1) + want + m.group(3)
        return m.group(0)

    def inca(m):
        want = C1.get("inca-trail")
        if want and want.upper() != m.group(2).upper():
            drift.append(("inca-trail", m.group(2), want))
            return m.group(1) + want
        return m.group(0)

    out = INCA.sub(inca, TEASER.sub(teaser, TCARD.sub(tcard, src)))
    if drift and not check:
        open(path, "w", encoding="utf-8").write(out)
    return drift


if __name__ == "__main__":
    check = "--check" in sys.argv
    total = 0
    for f in ("trails.html", "index.html"):
        d = sync(os.path.join(WEB, f), check)
        total += len(d)
        for tid, was, now in d:
            print("  %-26s %s -> %s   (%s)" % (tid, was, now, f))
    if not total:
        print("website trail colours match the app.")
    elif check:
        print("\n%d colours in the HTML disagree with TrailArt.kt. Run without --check to fix." % total)
        sys.exit(1)
    else:
        print("\n%d colours re-synced from TrailArt.kt." % total)
