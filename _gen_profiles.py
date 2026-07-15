#!/usr/bin/env python3
"""Draw the real elevation profile into every trail card, build the free-trail hero, and put the Inca
profile on the homepage. Rewrites trails.html + index.html in place. Run again after any elevation rebuild.

WHY A GENERATOR: there are 36 cards. A human editing 36 cards by hand is a human introducing a typo into
one of them, and a typo here is a wrong NUMBER, which is the one thing this site cannot afford.

WHY THE NUMBERS ARE HANDLED SO CAREFULLY (read before changing any of this):
  Source is trails/elevation/*.json — a 30 m public DEM (SRTM/ASTER/Mapzen) sampled along each trail's real
  track. The SHAPE it returns is honest. The TOTAL ASCENT it returns very often is not:
    - sampled coarsely, it cannot see the bumps between samples, so it UNDER-reports (Tour du Mont Blanc
      reads 8,319 m against a published ~10,000);
    - where our track is a straight line between sparse waypoints, the DEM faithfully reports the
      mountainside that line crosses — which the real path switchbacks around — so it OVER-reports
      (Annapurna reads 5,904 m for a pass published at 5,416 m).
  build_trailprofiles.py already encodes exactly when the climb figure is credible ("trustworthy"), so we
  re-derive it here from the SAME rule rather than inventing a second one. 9 of the 36 trails pass it.

  The HIGH POINT is not the safe figure it looks like, and this cost a rewrite of this file. A single DEM
  read cannot accumulate error the way a sum of deltas does — but it is a read of the ground under OUR
  ROUTE LINE, and where that line is straight between sparse waypoints it does not go where the path goes.
  Annapurna's maxM is 5,904 m. Thorong La, the pass it is meant to be, is published at 5,416 m: our line
  crosses a shoulder 488 m above the real trail. The error rides on the same "is the track credible" flag as
  ascent does, so it gets the same treatment.
  Therefore:
    - ascent is printed ONLY on the 9 trustworthy trails, and always with a "~";
    - the high point is printed on all 36, but with a "~" on the 27, and the page carries a legend saying in
      plain words what the "~" means — measured off our route line, close but not exact;
    - the profile is drawn on all 36, because the shape is the honest part, and it is captioned with its
      real min-max so a silhouette normalised to its own range cannot read as a bigger climb than it is.
  If you ever feel tempted to print an untrustworthy ascent "just for the look of it": the Inca Trail is the
  one we verified end to end (4,206 m read against 4,215 m published, nine metres out). That is what a number
  we are allowed to show off looks like.

NOT NAMING THE PASS: JD's standing rule is that "Dead Woman's Pass" never appears on a marketing surface.
The hero labels the high point by its height, not its name.

THE WALKING PACE IS ONE NUMBER AND IT LIVES HERE (added 2026-07-14, and it was a real defect):
  The site used to carry TWO paces. The homepage promised "about 5,000 steps a day carries you roughly
  three kilometres"; every "about N weeks" on the cards was computed at ~5.6 km/day, a rate the site never
  told anybody. A walker doing exactly the 5,000 steps we promised finished the Camino eleven weeks after
  the date we quoted them. Now there is ONE pace, it is derived from the app's OWN stride, it is stated on
  the page in words, and the cards are computed from it here rather than typed by hand:
      STRIDE_M = 0.72   — the shipping app's constant (PhoneStepTracker.kt, HealthConnectStepSource.kt,
                          TrailState.mc, Ledger.mc — all four agree)
      5,000 steps x 0.72 m = 3.6 km a day
  Change STEPS_PER_DAY/STRIDE_M and every card duration moves with it. If you change it, change the words
  on index.html + trails.html + faq.html that state it out loud, or the site is lying again.
"""
import json, os, re, glob

ROOT = r"C:\Users\jwden\WatchApps"
ELEV = os.path.join(ROOT, "trails", "elevation")
WEB = os.path.join(ROOT, "watchwalks-web")
KT = os.path.join(ROOT, "watchwalks-android", "app", "src", "main", "java", "com", "watchwalks",
                  "companion", "data", "SampleData.kt")

STRIDE_M = 0.72          # the app's stride. Not ours to pick — read it off the app and match it.
STEPS_PER_DAY = 5000     # the pace the site states out loud, in words, wherever a duration appears.
KM_PER_DAY = STEPS_PER_DAY * STRIDE_M / 1000.0   # 3.6


def app_km():
    """Trail lengths from the SHIPPING app, which is the only source of truth for a distance. The site has
    already published 110 km for a 303 km trail by trusting its own HTML; it does not get to do that twice."""
    kt = open(KT, encoding="utf-8").read()
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r'Trail\("[a-z0-9-]+",\s*"([^"]+)",\s*"[^"]*",\s*(\d+)', kt)}


def duration(km):
    """How long this trail takes at the ONE stated pace. Longer than the old numbers, and that is the point:
    it is the walk the reader will actually get. Weeks up to a year and a half, then years, because "about
    169 weeks" is a number no human converts."""
    weeks = km / KM_PER_DAY / 7.0
    if weeks < 78:
        # "about 1 weeks" shipped on the Otter Trail and the Routeburn cards. The duration is the one
        # figure on a trail card a reader actually converts into a decision, and it was printed in broken
        # English on the two trails most likely to be somebody's first. (78 weeks is already 1.5 years, so
        # the years branch below can never want a singular.)
        w = round(weeks)
        return "about a week" if w <= 1 else f"about {w} weeks"
    years = f"{km / KM_PER_DAY / 365.25:.1f}".rstrip("0").rstrip(".")   # "3 years", never "3.0 years"
    return f"about {years} years"

# Same threshold build_trailprofiles.py uses. Two copies of a rule drift; this one exists only because the
# web repo is a separate repo and cannot import the sibling. Keep them equal.
MAX_IMPLAUSIBLE_SEGS = 5

# The one card that has no satellite image to key off (its route is an inline SVG), so it has no filename
# to read the id from.
NAME_ID = {"Last Degree to the South Pole": "south-pole-last-degree"}


def load():
    out = {}
    for f in sorted(glob.glob(os.path.join(ELEV, "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        st, q = d.get("stats"), d.get("quality", {})
        prof = [(p["km"], p["ele"]) for p in d.get("profile", []) if p.get("ele") is not None]
        if not st or d.get("coverage") == "none" or len(prof) < 2:
            print(f"  ! {d['trailId']}: no usable DEM coverage — no profile drawn")
            continue
        conf = q.get("ascentConfidence", "indicative")
        trust = (conf == "good"
                 and q.get("implausibleGradeSegments", 0) <= MAX_IMPLAUSIBLE_SEGS
                 and not d.get("lowConfidence"))
        out[d["trailId"]] = {"prof": prof, "st": st, "conf": conf, "trust": trust}
    return out


def thin(prof, target):
    """Even sampling down to ~target points, but the high point is never allowed to be the sample that gets
    dropped — losing it would flatten the one feature the profile exists to show."""
    if len(prof) <= target:
        return prof
    hi = max(range(len(prof)), key=lambda i: prof[i][1])
    step = len(prof) / target
    keep = sorted({0, hi, len(prof) - 1} | {int(i * step) for i in range(target)})
    return [prof[i] for i in keep if i < len(prof)]


def paths(prof, w, h, pad_top=6, pad_bot=2):
    """Fill + stroke path data. The SVG is stretched with preserveAspectRatio="none" (so a card of any width
    keeps the x axis proportional to distance, which is what makes the high-point marker land in the right
    place); the stroke survives that with vector-effect="non-scaling-stroke"."""
    xs = [p[0] for p in prof]
    ys = [p[1] for p in prof]
    x0, x1 = xs[0], xs[-1]
    lo, hi = min(ys), max(ys)
    rng = max(hi - lo, 1.0)
    sx = lambda km: (km - x0) / max(x1 - x0, 1e-6) * w
    sy = lambda e: h - pad_bot - (e - lo) / rng * (h - pad_top - pad_bot)
    pts = [f"{sx(km):.1f},{sy(e):.1f}" for km, e in prof]
    line = "M " + " L ".join(pts)
    fill = f"{line} L {w:.1f},{h:.1f} L 0,{h:.1f} Z"
    return fill, line


def n(v):
    return f"{int(round(v)):,}"


def card_svg(tid, name, d):
    st = d["st"]
    prof = thin(d["prof"], 110)
    fill, line = paths(prof, 300, 56)
    peak_x = st["highPointKm"] / max(d["prof"][-1][0], 1e-6) * 100
    # Descriptive, not decorative: a screen-reader user gets the same three numbers a sighted one reads off
    # the silhouette — including the same hedge, which is the part that would be easiest to quietly drop.
    approx = "" if d["trust"] else "approximately "
    lab = (f"Elevation profile of the {name}: the ground runs from {n(prof[0][1])} metres at the start, "
           f"through a high point of {approx}{n(st['maxM'])} metres, to {n(prof[-1][1])} metres at the "
           f"finish. Lowest point {n(st['minM'])} metres.")
    return (
        f'<div class="tc-prof">'
        f'<svg class="tc-prof-svg" viewBox="0 0 300 56" preserveAspectRatio="none" role="img" aria-label="{lab}">'
        f'<path class="pf-fill" d="{fill}"/>'
        f'<path class="pf-line" d="{line}" vector-effect="non-scaling-stroke"/>'
        f'</svg>'
        f'<span class="tc-prof-peak" style="left:{peak_x:.1f}%" aria-hidden="true"></span>'
        f'<span class="tc-prof-cap">{n(st["minM"])}&ndash;{n(st["maxM"])} m</span>'
        f'</div>'
    )


def stats_row(km, marks, d):
    st = d["st"]
    # The "~" is not decoration and it is not a style. It is the difference between a figure we stand behind
    # and one we don't, and the legend on the page says which is which.
    tilde = "" if d["trust"] else "~"
    li = [f'<li><b>{km:,}</b> km</li>', f'<li><b>{marks}</b> landmarks</li>',
          f'<li><b>{tilde}{n(st["maxM"])}</b> m high point</li>']
    # Even a trustworthy DEM ascent lands within roughly +/-15% of a guidebook, so it is never bare.
    if d["trust"]:
        li.append(f'<li><b>~{n(st["ascentM"])}</b> m climb</li>')
    # Computed, never typed: at 5,000 steps a day, which the legend above the cards says in plain words.
    li.append(f'<li class="tc-weeks">{duration(km)}</li>')
    return '<ul class="tc-stats">' + "".join(li) + "</ul>"


def hero(d):
    """The free trail, given the room it earns. Inca is the ONE trail we verified against a published
    height (4,206 m read, 4,215 m published), so it is the one trail whose number we may show off."""
    st = d["st"]
    prof = d["prof"]
    total = prof[-1][0]
    fill, line = paths(prof, 900, 210, pad_top=6)
    peak_x = st["highPointKm"] / total * 100
    lab = (f"Elevation profile of the Inca Trail: the ground climbs from {n(prof[0][1])} metres at the "
           f"Urubamba river to a high point of {n(st['maxM'])} metres roughly a quarter of the way in, "
           f"drops into cloud forest, crosses two lower passes and falls to Machu Picchu at "
           f"{n(prof[-1][1])} metres. Forty-three kilometres in total.")
    return f'''<!-- GEN:hero — built by _gen_profiles.py. Do not hand-edit; edit the generator. -->
<section class="thero" style="--tc:#F4B04A" aria-labelledby="thero-h">
  <div class="thero-map">
    <img src="img/trailmaps/inca-trail.webp" width="680" height="430" loading="eager"
         alt="Satellite route map of the Inca Trail, from KM82 on the Urubamba river to Machu Picchu, with a pin at each of its twelve landmarks">
  </div>
  <div class="thero-body">
    <div class="tc-head"><span class="eyebrow">Start here</span><span class="tag free">Free</span></div>
    <!-- H2, not H3: the page goes H1 (page title) -> this -> H2 per continent. An H3 here skipped a
         level straight after the H1 (WCAG 1.3.1). The size comes from .thero-body h2 in styles.css. -->
    <h2 id="thero-h">Inca Trail</h2>
    <p class="tc-region">Peru &middot; 43 km &middot; 12 landmarks</p>
    <!-- "roughly two weeks": the site's ONE rate is 5,000 steps = 3.6 km a day (the app's 0.72 m stride),
         and 43 km at that rate is 12 days. Every duration on this page comes from the same number — see
         KM_PER_DAY at the top of this file. Change the rate and this sentence changes with it. -->
    <p class="thero-blurb">Forty-three kilometres of Inca stone, from the permit gate on the Urubamba river up
      through the cloud forest to the Sun Gate and Machu&nbsp;Picchu. At {STEPS_PER_DAY:,} steps a day, that
      is about two weeks of ordinary walking. It is free, and it needs no account.</p>
    <figure class="thero-prof">
      <div class="prof-wrap">
        <svg class="prof-svg" viewBox="0 0 900 210" preserveAspectRatio="none" role="img" aria-label="{lab}">
          <path class="pf-fill" d="{fill}"/>
          <path class="pf-line" d="{line}" vector-effect="non-scaling-stroke"/>
          <line class="pf-drop" x1="{st['highPointKm'] / total * 900:.1f}" y1="0"
                x2="{st['highPointKm'] / total * 900:.1f}" y2="210" vector-effect="non-scaling-stroke"/>
        </svg>
        <!-- The label is HTML, not SVG text: the SVG is stretched with preserveAspectRatio="none", which
             would squash any glyph inside it, and at 430px wide it would shrink the type to about 8px. -->
        <span class="prof-peak" style="left:{peak_x:.1f}%"><b>{n(st['maxM'])} m</b><em>high point</em></span>
      </div>
      <div class="prof-axis" aria-hidden="true"><span>0 km &middot; {n(prof[0][1])} m</span><span>{total:.0f} km &middot; {n(prof[-1][1])} m</span></div>
      <figcaption>Sampled from a public 30&nbsp;m elevation model along the real route. We measured the
        highest pass at <b>{n(st['maxM'])} m</b>; its published height is <b>4,215 m</b>. Nine metres out.</figcaption>
    </figure>
    <a class="btn" href="index.html#get">Start the Inca Trail, free</a>
  </div>
</section>
<!-- /GEN:hero -->'''


def why_profile(d):
    st = d["st"]
    prof = d["prof"]
    total = prof[-1][0]
    fill, line = paths(prof, 900, 190, pad_top=6)
    peak_x = st["highPointKm"] / total * 100
    lab = (f"Elevation profile of the Inca Trail: it climbs from {n(prof[0][1])} metres to a high point of "
           f"{n(st['maxM'])} metres, then falls through two lower passes to Machu Picchu at "
           f"{n(prof[-1][1])} metres over 43 kilometres.")
    return f'''<!-- GEN:inca-profile — built by _gen_profiles.py. Do not hand-edit; edit the generator. -->
    <figure class="why-prof" style="--tc:#F4B04A">
      <div class="prof-wrap">
        <svg class="prof-svg" viewBox="0 0 900 190" preserveAspectRatio="none" role="img" aria-label="{lab}">
          <path class="pf-fill" d="{fill}"/>
          <path class="pf-line" d="{line}" vector-effect="non-scaling-stroke"/>
          <line class="pf-drop" x1="{st['highPointKm'] / total * 900:.1f}" y1="0"
                x2="{st['highPointKm'] / total * 900:.1f}" y2="190" vector-effect="non-scaling-stroke"/>
        </svg>
        <span class="prof-peak" style="left:{peak_x:.1f}%"><b>{n(st['maxM'])} m</b><em>high point</em></span>
      </div>
      <div class="prof-axis" aria-hidden="true"><span>KM82 Piscacucho &middot; {n(prof[0][1])} m</span><span>Machu Picchu &middot; 43 km</span></div>
      <figcaption>This is the Inca Trail, actually measured: the long climb out of the Urubamba valley, the
        high pass, then the drop through cloud forest to Machu&nbsp;Picchu. Sampled from a public 30&nbsp;m
        elevation model along the real route &mdash; we read the highest pass at 4,206&nbsp;m against a
        published 4,215&nbsp;m.</figcaption>
    </figure>
<!-- /GEN:inca-profile -->'''


def legend(data):
    """The tilde is doing real work on 27 of these cards. A mark whose meaning is never explained is not
    honesty, it is a disclaimer nobody can read — so it gets a legend, in words, above the cards."""
    t = sum(1 for d in data.values() if d["trust"])
    return f'''<!-- GEN:legend — built by _gen_profiles.py. Do not hand-edit; edit the generator. -->
  <p class="elev-note"><b>Every time below is worked out at {STEPS_PER_DAY:,} steps a day</b> &mdash; about
    {KM_PER_DAY:.1f}&nbsp;km, at the {STRIDE_M} m stride the app counts a step as. That is the pace of an
    ordinary day, not a hiking day. Walk more and you arrive sooner: at 10,000 steps every one of these
    halves.</p>
  <p class="elev-note">Every profile below is the real ground under the route, sampled from a public
    30&nbsp;m elevation model &mdash; not drawn by hand and not copied from a guidebook.
    <b>A &ldquo;~&rdquo; means the figure is close, not exact.</b> On {len(data) - t} of the {len(data)} trails our
    route line runs straighter than the walked path does, so it can cross ground the real trail contours
    around, and the heights it reads there run a little high. The shape is right; those numbers are
    approximate, and we would rather say so. On the other {t} the track is fine enough to trust, and those
    cards also carry a total climb.</p>
<!-- /GEN:legend -->'''


CARD_RE = re.compile(r'<article class="tcard".*?</article>', re.S)


def rewrite_trails(data):
    p = os.path.join(WEB, "trails.html")
    h = open(p, encoding="utf-8").read()
    done, missing, drift = [], [], []
    akm = app_km()

    def one(m):
        card = m.group(0)
        # Re-runnable: strip what a previous run put in before rebuilding it, so the script is safe to run
        # after every elevation rebuild rather than being a one-shot that silently doubles its own output.
        card = re.sub(r'<div class="tc-prof">.*?</span></div>', "", card, flags=re.S)
        card = re.sub(r'\s*data-trail="[a-z0-9-]+"', "", card)
        img = re.search(r'img/trailmaps/([a-z0-9-]+)\.webp', card)
        name = re.search(r"<h3[^>]*>(.*?)</h3>", card).group(1)
        tid = img.group(1) if img else NAME_ID.get(name)
        if not tid or tid not in data:
            missing.append(name)
            return card
        d = data[tid]
        card_km = int(re.search(r"<li><b>([\d,]+)</b> km</li>", card).group(1).replace(",", ""))
        marks = re.search(r"<li><b>(\d+)</b> landmarks</li>", card).group(1)
        # The app wins. A card that disagrees with the app about how long a trail is gets corrected and
        # SHOUTED about — the km also appears in the card's region line, which no regex here touches.
        km = akm.get(name.replace("&nbsp;", " "), card_km)
        if km != card_km:
            drift.append(f"{name}: card said {card_km} km, app says {km} km (region line NOT auto-fixed)")
        card = re.sub(r'<ul class="tc-stats">.*?</ul>', stats_row(km, marks, d), card, flags=re.S)
        # Under the map, above the words: the silhouette reads as part of the map, not as a chart bolted on.
        card = card.replace('</div><div class="tc-body">', "</div>" + card_svg(tid, name, d) + '<div class="tc-body">')
        card = card.replace('<article class="tcard"', f'<article class="tcard" data-trail="{tid}"', 1)
        done.append(tid)
        return card

    h = CARD_RE.sub(one, h)

    # The free trail is the hero, so it must not also sit in the South America grid as one of twelve —
    # the same card twice on one page reads as a bug.
    h = re.sub(r'<article class="tcard" data-trail="inca-trail".*?</article>', "", h, flags=re.S)
    h = re.sub(r"<!-- GEN:hero.*?<!-- /GEN:hero -->\n?", "", h, flags=re.S)
    h = re.sub(r"<!-- GEN:legend.*?<!-- /GEN:legend -->\n?", "", h, flags=re.S)
    anchor = '  <nav class="tnav"'
    h = h.replace(anchor, hero(data["inca-trail"]) + "\n\n" + anchor, 1)
    anchor2 = '<section class="tcont" id="south-america">'
    h = h.replace(anchor2, legend(data) + "\n\n" + anchor2, 1)
    open(p, "w", encoding="utf-8").write(h)
    print(f"trails.html: {len(done)} cards given a profile + a duration at "
          f"{STEPS_PER_DAY:,} steps/day ({KM_PER_DAY:.1f} km/day); hero rebuilt"
          + (f"; NO ELEVATION for {missing}" if missing else ""))
    for w in drift:
        print(f"  !! LENGTH DRIFT — {w}")


def rewrite_index(data):
    p = os.path.join(WEB, "index.html")
    h = open(p, encoding="utf-8").read()
    h = re.sub(r"[ \t]*<!-- GEN:inca-profile.*?<!-- /GEN:inca-profile -->\n?", "", h, flags=re.S)
    anchor = "\n\n    <!-- story cards + milestone photos -->"
    assert anchor in h, "why-section anchor moved"
    h = h.replace(anchor, "\n\n" + why_profile(data["inca-trail"]) + anchor, 1)
    open(p, "w", encoding="utf-8").write(h)
    print("index.html: Inca profile placed in the why section")


if __name__ == "__main__":
    data = load()
    t = sum(1 for d in data.values() if d["trust"])
    print(f"{len(data)} trails with elevation; {t} carry a trustworthy ascent figure, "
          f"{len(data) - t} do not (their ascent is NOT printed)")
    rewrite_trails(data)
    rewrite_index(data)
