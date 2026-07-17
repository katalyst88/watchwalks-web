#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_web_parity.py — make watchwalks-web/ a CHECKED artefact.

WHY THIS EXISTS
---------------
`verify_platform_parity.py` and `verify_story_parity.py` do not read watchwalks-web/ at all.
So "all 5 parity artefacts agree" has always been silent about the website. On 2026-07-16 the
index.html headline tiles were found reading 36 trails / 28,421 km / 1,091 landmarks when the
catalogue had been 41 / 28,250 / 1,117 for two revisions. The most prominent number on the site
was five trails stale, and every check in the repo said green. This closes that hole.

The site asserts ~200 numbers about trail data by hand. This does not fix them and does not
edit the site. It tells you, out loud, the moment one of them stops being true.

TWO TRAPS THIS FILE EXISTS TO AVOID (both cost a predecessor a wrong conclusion, 2026-07-17)
--------------------------------------------------------------------------------------------
1. HTML COMMENTS. A naive grep for `\\d+ trails?` reports index.html claiming "36, 41 and 42"
   simultaneously. It does not. Two of those live inside a comment *documenting the old bug*.
   The grep counted the fix's changelog as the bug. ALWAYS strip comments before asserting.
2. TAGS BETWEEN NUMBER AND UNIT. trails.html writes `<li><b>180</b> km</li>`. A `[\\d,]+\\s*km`
   grep finds 5 claims on a page that carries ~200, and you conclude the page is nearly clean.
   ALWAYS strip tags before matching.

Both failures report GREEN. A check that says "fine" because it is broken is indistinguishable
from a check that says "fine" because things are fine — unless you make the check prove its work.
That is why --show prints the counts it actually compared: a checker that finds 0 cards must not
be allowed to pass silently. See SANITY FLOOR below.

USAGE
    export PYTHONIOENCODING=utf-8        # a Turkish 'ş' (Lycian Way) kills this silently otherwise
    python verify_web_parity.py          # exit 0 = site agrees with the catalogue
    python verify_web_parity.py --show   # print every comparison made

EXIT CODES:  0 = in sync   1 = drift found   2 = the checker itself could not run honestly
"""

import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "watchwalks-web")
SD = os.path.join(ROOT, "watchwalks-android", "app", "src", "main", "java", "com",
                  "watchwalks", "companion", "data", "SampleData.kt")

SHOW = "--show" in sys.argv
failures = []
notes = []


def fail(msg):
    failures.append(msg)
    print("  FAIL " + msg)


def ok(msg):
    if SHOW:
        print("  ok   " + msg)


def strip_comments(html):
    """HTML comments are prose ABOUT the numbers, not the numbers. Trap 1."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def strip_tags(html):
    """`<li><b>180</b> km</li>` must read as `180 km`. Trap 2."""
    return re.sub(r"<[^>]+>", " ", html)


def live_text(path):
    raw = open(path, encoding="utf-8").read()
    return strip_tags(strip_comments(raw))


# ---------------------------------------------------------------- the catalogue (source of truth)

def load_catalogue():
    """SampleData.kt is the truth. Note Trail() args are POSITIONAL:
       Trail(id, name, region, km, finalLandmark, ...). A grep for `id = "` returns ZERO
       and would convince you the file is empty."""
    src = open(SD, encoding="utf-8").read()
    trails = {}
    for m in re.finditer(r'Trail\("([a-z0-9-]+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\d+)', src):
        tid, name, region, km = m.groups()
        trails[tid] = {"name": name, "region": region, "km": int(km)}

    # milestones live in a separate `"<id>" to listOf( Milestone(...), ... )` map.
    # Brace-match rather than regex the block: blurbs contain ')' and would truncate the count.
    milestones = {}
    for m in re.finditer(r'"([a-z0-9-]+)"\s+to\s+listOf\(', src):
        tid = m.group(1)
        i = m.end()
        depth = 1
        while i < len(src) and depth:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        block = src[m.end():i]
        if "Milestone(" in block:
            milestones[tid] = len(re.findall(r"Milestone\(", block))
    return trails, milestones


# ---------------------------------------------------------------- checks

def check_trail_count(trails):
    print("\n[1] trail count on every page vs the catalogue")
    n = len(trails)
    words = {36: "thirty-six", 41: "forty-one", 42: "forty-two", 40: "forty", 39: "thirty-nine"}
    expect_word = words.get(n, "").replace("-", "[- ]?")
    pages = sorted(f for f in os.listdir(WEB) if f.endswith(".html") and not f.startswith("_"))
    for f in pages:
        t = live_text(os.path.join(WEB, f))
        # digits
        for m in re.finditer(r"\b(\d{2})\s+(?:trails?|journeys?)\b", t, re.I):
            if int(m.group(1)) != n:
                fail("%s says %s trails; catalogue has %d" % (f, m.group(1), n))
        # spelled out — the 2026-07-16 miss was partly prose ("Forty-one real routes")
        if expect_word:
            for m in re.finditer(r"\b(thirty[- ]?six|forty[- ]?one|forty[- ]?two|thirty[- ]?nine)\b",
                                 t, re.I):
                if not re.fullmatch(expect_word, m.group(0), re.I):
                    fail("%s spells out '%s'; catalogue has %d" % (f, m.group(0), n))
    ok("%d pages all agree on %d trails" % (len(pages), n))
    return len(pages)


def check_headline_totals(trails, milestones):
    print("\n[2] index.html headline tiles vs the catalogue")
    total_km = sum(t["km"] for t in trails.values())
    total_lm = sum(milestones.values())
    t = live_text(os.path.join(WEB, "index.html"))
    flat = re.sub(r"\s+", " ", t)
    for label, val in (("total km", total_km), ("landmarks", total_lm)):
        pretty = "{:,}".format(val)
        if pretty not in flat:
            fail("index.html does not state the true %s (%s). The tiles are the most "
                 "prominent numbers on the site and were 5 trails stale on 2026-07-16." % (label, pretty))
        else:
            ok("index.html states %s = %s" % (label, pretty))
    return total_km, total_lm


def check_cards(trails, milestones):
    """Every trail card on trails.html, diffed against the catalogue.
    These cards are GENERATED by _gen_trailmaps.py — a mismatch means the generator has not
    been re-run since the data moved, not that someone fat-fingered a number."""
    print("\n[3] trails.html trail cards vs the catalogue")
    raw = strip_comments(open(os.path.join(WEB, "trails.html"), encoding="utf-8").read())
    cards = list(re.finditer(r'<article class="tcard" data-trail="([^"]+)"(.*?)</article>', raw, re.S))

    # SANITY FLOOR: a regex that matches nothing must never report success.
    if len(cards) < 2:
        print("  ABORT: found %d trail cards. The card markup has changed and this check is "
              "no longer reading the page. It is NOT green — it is blind." % len(cards))
        sys.exit(2)

    seen = set()
    for m in cards:
        tid, body = m.group(1), strip_tags(m.group(2))
        seen.add(tid)
        if tid not in trails:
            fail("trails.html has a card for '%s' which is not in the catalogue" % tid)
            continue
        km = re.search(r"([\d,]+)\s*km\b", body)
        lm = re.search(r"([\d,]+)\s*landmarks?\b", body)
        if km:
            v = int(km.group(1).replace(",", ""))
            if v != trails[tid]["km"]:
                fail("%s card says %d km; catalogue says %d km" % (tid, v, trails[tid]["km"]))
            else:
                ok("%s %d km" % (tid, v))
        if lm and tid in milestones:
            v = int(lm.group(1).replace(",", ""))
            if v != milestones[tid]:
                fail("%s card says %d landmarks; catalogue says %d" % (tid, v, milestones[tid]))

    # inca-trail is the hero card above the grid, not an <article> — it is not "missing".
    missing = set(trails) - seen - {"inca-trail"}
    if missing:
        fail("catalogue trails with no card on trails.html: %s" % ", ".join(sorted(missing)))
    ok("%d cards checked" % len(cards))
    return len(cards)


def check_brand():
    """BRAND.md is LOCKED and beats any handover. 'Unlock' is BANNED; 'journey' is NOT."""
    print("\n[4] brand rules")
    for f in sorted(os.listdir(WEB)):
        if not f.endswith(".html"):
            continue
        t = live_text(os.path.join(WEB, f))
        for m in re.finditer(r"\bunlock\w*", t, re.I):
            fail("%s uses the banned word '%s'" % (f, m.group(0)))
        if re.search(r"dead\s+woman", t, re.I):
            fail("%s names Dead Woman's Pass — banned on every marketing surface" % f)
    ok("no banned 'unlock'; no 'Dead Woman's Pass' on any rendered page")


def check_generated_freshness():
    """The ladder fix rewrites milestone km. Every generator below PINS BY KM
    (_gen_trailmaps matches each milestone km to the nearest track point). So a changed ladder
    silently invalidates the maps and profiles: the pin moves, the picture does not.
    Timestamps only — this reports SUSPECTED staleness, it cannot prove content drift."""
    print("\n[5] generated assets vs trail data (staleness, by mtime)")

    def newest(paths):
        paths = [p for p in paths if os.path.exists(p)]
        return max((os.path.getmtime(p) for p in paths), default=0)

    def stamp(t):
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t else "missing"

    tj = [os.path.join(ROOT, "trails", f) for f in os.listdir(os.path.join(ROOT, "trails"))
          if f.endswith(".json")] if os.path.isdir(os.path.join(ROOT, "trails")) else []
    data_t = max(newest([SD]), newest(tj))
    print("      newest trail data: %s" % stamp(data_t))

    outputs = {
        "trails.html (cards, maps, profiles)": [os.path.join(WEB, "trails.html")],
        "attribution.html (high points)": [os.path.join(WEB, "attribution.html")],
        "img/trailmaps/*": [os.path.join(WEB, "img", "trailmaps", f)
                            for f in os.listdir(os.path.join(WEB, "img", "trailmaps"))]
        if os.path.isdir(os.path.join(WEB, "img", "trailmaps")) else [],
    }
    for label, paths in outputs.items():
        t = newest(paths)
        state = "STALE" if t and data_t > t else "fresh"
        line = "      %-38s %s  %s" % (label, stamp(t), state)
        print(line)
        if state == "STALE":
            notes.append("%s is older than the trail data (%s < %s) — regenerate before launch"
                         % (label, stamp(t), stamp(data_t)))


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        print("WARNING: stdout is %s, not utf-8. A Turkish 's' in Lycian Way can kill this "
              "mid-run. export PYTHONIOENCODING=utf-8" % sys.stdout.encoding)

    trails, milestones = load_catalogue()

    # SANITY FLOOR: if the catalogue parse breaks, everything below trivially "passes".
    if len(trails) < 2:
        print("ABORT: parsed %d trails from SampleData.kt. The parser is broken, not the "
              "catalogue. Refusing to report green." % len(trails))
        sys.exit(2)

    print("catalogue: %d trails, %s km, %s landmarks  (SampleData.kt)"
          % (len(trails), "{:,}".format(sum(t["km"] for t in trails.values())),
             "{:,}".format(sum(milestones.values()))))

    check_trail_count(trails)
    check_headline_totals(trails, milestones)
    check_cards(trails, milestones)
    check_brand()
    check_generated_freshness()

    print("\n" + "=" * 66)
    if notes:
        print("NOTES (not failures):")
        for n in notes:
            print("  - " + n)
    if failures:
        print("DRIFT: %d" % len(failures))
        for f in failures:
            print("  - " + f)
        print("\nThe site asserts these numbers by hand. Re-run the generators "
              "(_gen_trailmaps.py, _gen_profiles.py, _gen_attribution.py) rather than "
              "editing HTML, or the next data change puts them back.")
        sys.exit(1)
    print("IN SYNC: the website agrees with the catalogue.")
    sys.exit(0)


if __name__ == "__main__":
    main()
