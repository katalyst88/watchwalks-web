#!/usr/bin/env python3
# =============================================================================================
# STOP. THIS SCRIPT REWRITES THE WHOLE OF trails.html FROM A TEMPLATE THAT IS STALE.
#
# Running it on 2026-07-13 silently reverted the page to an older design: it deleted the skip
# link, the <main id="main" tabindex="-1"> landmark AND the <details class="mnav"> mobile nav --
# which, under 720px, is the ONLY way out of the page. Three accessibility regressions and a
# dead end on every phone, in exchange for a colour change.
#
# To change trail COLOURS you do not need this script. Run:  python _sync_trail_colors.py
# It rewrites only the --tc values, by regex, and touches nothing else.
#
# Only run this if you actually intend to regenerate the trail CARDS, and diff the result before
# you commit it.
# =============================================================================================
# Generate the "See the trails" showcase page: one card per trail with an inline SVG route map
# (route in the trail's identity colour + milestone pins coloured by type), key stats, grouped by
# continent. Route polylines come from the repo's *_encoded.txt tracks; milestone types + names from
# SampleData.kt; trail colours from the app's TrailArt map. Fully self-contained, no external assets.
import os, re, json, glob, math

ROOT = r"C:\Users\jwden\WatchApps"
# Milestones come from the REPO, not a scratchpad. This pointed at ONE SESSION'S temp directory
# (%TEMP%/claude/.../ad05301a-.../scratchpad/story_pass), which was deleted with that session -- so
# the generator that builds trails.html has been UNRUNNABLE (FileNotFoundError on the first trail),
# and nobody noticed because nobody ran it. verify_web_parity.py tells you to "re-run the
# generators" to fix drift; this one could not run, which is part of why the drift persists.
# _gen_satmaps.py carries a comment saying this exact bug was fixed -- it was fixed THERE ONLY.
# A build input that lives in %TEMP% is a build input with an expiry date.
SP = os.path.join(ROOT, "trails")
SD = os.path.join(ROOT, r"watchwalks-android\app\src\main\java\com\watchwalks\companion\data\SampleData.kt")
OUT = os.path.join(ROOT, "watchwalks-web", "trails.html")

# id -> encoded-track shortname (most are identical bar a suffix)
TRACK = {"pacific-crest":"pct","length-of-britain":"britain","te-araroa":"teararoa","route-66":"route66",
 "cape-to-cape":"capetocape","tour-du-mont-blanc":"tmb","west-highland-way":"westhighland","john-muir-trail":"jmt",
 "tahoe-rim":"tahoerim","torres-del-paine-w":"torres","australian-alps":"ausalps","haute-route":"hauteroute",
 "long-trail":"longtrail","annapurna-circuit":"annapurna","manaslu-circuit":"manaslu","atlas-traverse":"atlas",
 "inca-road":"incaroad",
 "inca-trail":"inca","jordan-trail":"jordan","larapinta-trail":"larapinta","lycian-way":"lycian",
 "wonderland-trail":"wonderland"}

# Trail identity colour (c1). NOT a copy: read live from the app's TrailArt map, so the site
# cannot drift from the apps the way it already had (12 trails disagreed on 2026-07-13, and the
# palette baked into these .webp route lines was the banned blue/violet one). See _trail_colors.py.
from _trail_colors import C1 as COLOR

# Milestone type -> pin colour (mirrors milestoneTypeColor in CelebrationOverlay.kt).
TYPE_COLOR = {"start":"#2FB471","finish":"#E8B23A","pass":"#5C82D0","summit":"#5C82D0","camp":"#E0993A",
 "water":"#4FB3C0","forest":"#4E9E5A","bridge":"#9E7BD0","town":"#D4915A","landmark":"#CC6FA0"}

CONTINENT_ORDER = ["South America","North America","Europe","Asia","Africa","Oceania","Antarctica"]

def load_track(tid):
    sn = TRACK.get(tid, tid)
    f = os.path.join(ROOT, sn + "_encoded.txt")
    if os.path.exists(f):
        pts = []
        for tok in open(f, encoding="utf-8").read().strip().split(";"):
            p = tok.split(",")
            if len(p) == 3:
                try: pts.append((float(p[0]), float(p[1]), float(p[2])))
                except ValueError: pass
        return pts
    # Fallback 1: the GeoPoint(km, lat, lng) kotlin track (e.g. inca has only this).
    kt = os.path.join(ROOT, sn + "_track_kotlin.txt")
    if os.path.exists(kt):
        pts = []
        for m in re.finditer(r"GeoPoint\(([-0-9.]+)f?,\s*([-0-9.]+),\s*([-0-9.]+)\)", open(kt, encoding="utf-8").read()):
            pts.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
        if pts: return pts
    # Fallback 2: South Pole (and any trackless trail): use milestone lat/lngs as the line.
    mj = os.path.join(ROOT, "trails", tid + ".json")
    if os.path.exists(mj):
        d = json.load(open(mj, encoding="utf-8"))
        return [(m["km"], m["lat"], m["lng"]) for m in d.get("milestones", []) if "lat" in m]
    return []

def parse_blurbs():
    # SampleData's blurbFor map: "id" to "one-line description." — the app's own brief trail descriptions.
    src = open(SD, encoding="utf-8").read()
    blurbs = {}
    for m in re.finditer(r'"([a-z0-9-]+)"\s+to\s+"((?:[^"\\]|\\.)*)"', src):
        tid, txt = m.group(1), m.group(2)
        # only real trail ids, and skip the id->key/colour tables (those values aren't sentences)
        if tid in COLOR and ("." in txt or len(txt) > 25) and tid not in blurbs:
            blurbs[tid] = txt.replace('\\"', '"').encode().decode("unicode_escape") if "\\u" in txt else txt.replace('\\"', '"')
    return blurbs

def parse_trails():
    src = open(SD, encoding="utf-8").read()
    out = []
    for m in re.finditer(r'Trail\("([a-z0-9-]+)",\s*"([^"]+)",\s*"([^"]+)",\s*(\d+),\s*"[^"]*"(.*?)\)', src):
        tid, name, region, km, rest = m.groups()
        free = "free = true" in rest
        cm = re.search(r"Continent\.([A-Z_]+)", rest)
        cont = {"SOUTH_AMERICA":"South America","NORTH_AMERICA":"North America","EUROPE":"Europe",
                "ASIA":"Asia","AFRICA":"Africa","OCEANIA":"Oceania","ANTARCTICA":"Antarctica"}.get(
                cm.group(1) if cm else "", "Other")
        out.append(dict(id=tid, name=name, region=region, km=int(km), free=free, continent=cont))
    return out

def project(pts, W=300, H=190, pad=16):
    # equirectangular with longitude scaled by cos(mean lat); fit to box preserving aspect
    lats = [p[1] for p in pts]; lngs = [p[2] for p in pts]
    lat0 = math.radians(sum(lats)/len(lats))
    xs = [p[2]*math.cos(lat0) for p in pts]; ys = [-p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    dx, dy = maxx-minx or 1e-6, maxy-miny or 1e-6
    s = min((W-2*pad)/dx, (H-2*pad)/dy)
    ox = (W - s*dx)/2 - s*minx; oy = (H - s*dy)/2 - s*miny
    return [(round(x*s+ox,1), round(y*s+oy,1)) for x, y in zip(xs, ys)], s, ox, oy, lat0

def decimate(pts, keep=140):
    if len(pts) <= keep: return pts
    step = len(pts)/keep
    return [pts[int(i*step)] for i in range(keep)] + [pts[-1]]

def svg_for(tid, track, milestones, color):
    if len(track) < 2: return ""
    W, H = 300, 190
    dec = decimate(track, 140)
    proj, s, ox, oy, lat0 = project(dec, W, H)
    path = "M" + " L".join(f"{x},{y}" for x, y in proj)
    # milestone pins: match each milestone km to nearest track point, project the same way
    tk = [p[0] for p in track]
    pins = []
    for ms in milestones:
        km = ms["km"]
        j = min(range(len(track)), key=lambda i: abs(track[i][0]-km))
        px = track[j][2]*math.cos(lat0)*s+ox; py = -track[j][1]*s+oy
        pins.append((round(px,1), round(py,1), TYPE_COLOR.get(ms["type"], "#9A938A")))
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.1" fill="{c}" stroke="#fff" stroke-width="1"/>' for x,y,c in pins)
    return (f'<svg class="tm" viewBox="0 0 {W} {H}" role="img" aria-label="Route map">'
            f'<path d="{path}" fill="none" stroke="#fff" stroke-width="5.5" stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
            f'{dots}</svg>')

def main():
    trails = parse_trails()
    blurbs = parse_blurbs()
    cards = {}
    for t in trails:
        tid = t["id"]
        track = load_track(tid)
        # Milestones are OPTIONAL here. inca-trail -- the FREE trail, index 0 of the catalogue and
        # the hero of the site -- is in SampleData.kt but has NO trails/inca-trail.json (its
        # milestones live in SampleData.kt itself). Unguarded, that one missing file aborted the
        # generation of ALL 41 cards. A trail missing its pins must cost that trail its pins.
        mp = os.path.join(SP, tid + ".json")
        if os.path.exists(mp):
            ms = json.load(open(mp, encoding="utf-8"))["milestones"]
        else:
            ms = []
            print(f"  !! {tid}: no {tid}.json -- card will claim 0 landmarks and draw NO pins")
        color = COLOR.get(tid, "#4E9E5A")
        svg = svg_for(tid, track, ms, color)
        # Vector route drawn over the satellite basemap. svg_for() CANNOT do this job: it projects
        # equirectangular (x=lng*cos(lat0)) into a 300x190 viewBox while the raster is web mercator,
        # tile-based, 680x430 -- two different projections, so its line would sit off the valley. It
        # stays as the no-raster fallback only.
        try:
            from _gen_route_overlay import overlay_svg
            t["overlay"] = overlay_svg(tid)[0]
        except Exception as e:
            # A trail without an overlay loses its route line entirely, so this must be loud.
            print(f"  !! {tid}: NO route overlay ({e.__class__.__name__}: {e})")
            t["overlay"] = ""
        t["svg"] = svg; t["mcount"] = len(ms); t["color"] = color
        t["blurb"] = blurbs.get(tid, "")
        cards.setdefault(t["continent"], []).append(t)
    # emit page
    sections = []
    for cont in CONTINENT_ORDER:
        group = sorted(cards.get(cont, []), key=lambda x: (not x["free"], x["km"]))
        if not group: continue
        cardhtml = []
        for t in group:
            tag = '<span class="tag free">Free</span>' if t["free"] else '<span class="tag price">Paid</span>'
            # Satellite BASEMAP + the route as a vector overlay on top (registers pixel-exactly --
            # _gen_route_overlay reuses _gen_satmaps' own projection; proved to 0.000000000 px).
            #
            # The route used to be baked into these pixels. The card shows the 680x430 raster at
            # ~311 CSS px (measured in Chrome), a 2.19x DOWNSCALE at DPR1 -- terrain survives that,
            # a width-4 hard-edged line does not, which is the "low res" JD reported. It is NOT an
            # upscale problem, so @2x/srcset was the wrong fix. Vector is sharp at every DPR AND the
            # colour now comes from --tc (the DOM) rather than being frozen in the pixels, so the
            # site can no longer drift from the app's palette the way it already had once.
            #
            # NOTE: the overlay only lines up with a basemap built by `_gen_satmaps.py --no-route`.
            # Until those are regenerated the shipped webps still have the old line baked in and you
            # would see BOTH. Regenerate maps and this page together.
            img = os.path.join(os.path.dirname(__file__), "img", "trailmaps", t["id"] + ".webp")
            if os.path.exists(img):
                mapel = (f'<img class="tm" src="img/trailmaps/{t["id"]}.webp" width="680" height="430" '
                         f'loading="lazy" alt="Satellite route map of the {t["name"]}">'
                         + t["overlay"])
            else:
                mapel = t["svg"]
            # ⚠️ data-trail IS LOAD-BEARING — do not "tidy" it away. The LIVE page carries it
            # (`data-trail="alpamayo"`) but this generator did not emit it, so the first honest
            # regeneration silently stripped it from all 41 cards. `verify_web_parity.py` anchors on
            # exactly this attribute, and its sanity floor caught the loss at once: "found 0 trail
            # cards ... It is NOT green — it is blind". Without that floor a blind checker would have
            # reported a clean site while reading nothing — which is the failure this whole codebase
            # keeps re-learning. It is also simply correct: a card should say which trail it is.
            # ⚠️ t["id"], NOT tid. `tid` belongs to the PARSE loop above and is long dead here — this
            # is the emit loop (`for t in group`). My first go used `tid` and Python happily handed
            # back its leftover value, so all 41 cards were stamped data-trail="gr-r2", the last trail
            # parsed. It rendered perfectly and looked completely normal.
            cardhtml.append(
                f'<article class="tcard" data-trail="{t["id"]}" style="--tc:{t["color"]}">'
                f'<div class="tm-wrap">{mapel}</div>'
                f'<div class="tc-body"><div class="tc-head"><h3>{t["name"]}</h3>{tag}</div>'
                f'<p class="tc-region">{t["region"]}</p>'
                + (f'<p class="tc-blurb">{t["blurb"]}</p>' if t["blurb"] else '')
                + f'<ul class="tc-stats"><li><b>{t["km"]:,}</b> km</li>'
                f'<li><b>{t["mcount"]}</b> landmarks</li></ul></div></article>')
        sections.append(f'<section class="tcont"><h2>{cont}</h2><div class="tgrid">' + "".join(cardhtml) + "</div></section>")
    total = sum(len(v) for v in cards.values())
    return "\n".join(sections), total

HEAD = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>See the trails | Watch Walks</title>
<meta name="description" content="Every Watch Walks trail, grouped by continent, with its route map and key stats. From the free Inca Trail to the Pacific Crest Trail, the Camino de Santiago, Te Araroa and more.">
<link rel="canonical" href="https://watchwalks.com/trails.html">
<meta name="theme-color" content="#1F5C3D">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="apple-touch-icon" href="favicon.svg">
<link rel="stylesheet" href="styles.css">
</head>
<body>

<header>
  <div class="wrap nav">
    <a class="brand" href="index.html" style="color:inherit">
      <img src="favicon.svg" alt="" width="26" height="26" aria-hidden="true">
      Watch Walks
    </a>
    <span class="spacer"></span>
    <a class="navlink" href="index.html#why">Why you'll love it</a>
    <a class="navlink" href="compatibility.html">Compatibility</a>
    <a class="navlink" href="faq.html">Questions</a>
    <a class="navlink" href="index.html#get">Get it</a>
  </div>
</header>

<main class="wrap">

  <section class="hero" style="border-top:none;display:block;padding:60px 0 18px">
    <span class="eyebrow">The trails</span>
    <h1 style="font-size:clamp(30px,4.6vw,46px);font-weight:800;letter-spacing:-0.02em;line-height:1.08;margin-top:10px">Every trail, start to finish.</h1>
    <!-- ⚠️ THIS LEAD IS HAND-TYPED IN A GENERATOR, which is the worst of both worlds: it looks
         generated, so nobody proofreads it, and it is code, so nobody re-counts it. It carried THREE
         defects at once until 2026-07-17.
         "Around three dozen" = 36. We ship 41. The site's own tiles said 41 two pages away. Hedging
         with a vague count does not make it safe — it just makes it wrong more quietly, and it
         undersells the catalogue by five trails.
         "unlock" x2 — BANNED by the LOCKED BRAND.md. ("journey" is NOT banned and stays.) Both rode
         in here for weeks because verify_web_parity's brand check ABORTED before it ever ran: the
         card check died first on a sanity floor, so [4] never executed. A checker that stops early
         is a checker that is not checking.
         If the catalogue count changes again, this sentence is the one that will lie. -->
    <p class="lead" style="max-width:42em">Forty-one of the world's great long walks, each a complete journey with its own route and landmarks. Start free on the Inca Trail; add any other with a one-time purchase, yours to keep. Each map below traces the real route, with a pin at every landmark whose story opens as you walk.</p>
    <div class="cta-row" style="margin-top:20px" data-cta>
      <a class="btn" href="join-apple.html" data-p="ios">Get it on the App&nbsp;Store</a>
      <a class="btn" href="join-wearos.html" data-p="android">Get it on Google&nbsp;Play</a>
      <a class="btn" href="join-garmin.html" data-p="garmin">Get it on Garmin</a>
    </div>
  </section>

'''

FOOT = '''
  <p class="sat-credit">Satellite imagery: Esri, Maxar, Earthstar Geographics, and the GIS User Community.</p>

  <section class="cta-band" style="text-align:center">
    <h2>Pick a trail and start walking.</h2>
    <p class="sub" style="margin:8px auto 22px">Free to start on the Inca Trail, on the watch and phone you already own.</p>
    <div class="cta-row center" data-cta>
      <a class="btn" href="join-apple.html" data-p="ios">Get it on the App&nbsp;Store</a>
      <a class="btn" href="join-wearos.html" data-p="android">Get it on Google&nbsp;Play</a>
      <a class="btn" href="join-garmin.html" data-p="garmin">Get it on Garmin</a>
    </div>
  </section>

</main>

<footer>
  <div class="wrap row">
    <span class="brand" style="font-size:16px">
      <img src="favicon.svg" alt="" width="26" height="26" aria-hidden="true">
      Watch Walks
    </span>
    <span class="spacer"></span>
    <a href="index.html">Home</a>
    <a href="compatibility.html">Compatible devices</a>
    <a href="faq.html">Questions</a>
    <a href="privacy.html">Privacy</a>
    <a href="contact.html">Contact</a>
    <span>&copy; 2026 Watch Walks</span>
  </div>
</footer>

<script src="openin.js"></script>
<script>
(function(){
  var ua = navigator.userAgent || '';
  var p = /iPhone|iPad|iPod|Macintosh/i.test(ua) ? 'ios' : /Android/i.test(ua) ? 'android' : null;
  if (!p) return;
  document.querySelectorAll('[data-cta]').forEach(function(row){
    var pick = row.querySelector('[data-p="'+p+'"]'); if (pick) row.insertBefore(pick, row.firstChild);
  });
})();
</script>
</body>
</html>
'''

if __name__ == "__main__":
    body, total = main()
    open(OUT, "w", encoding="utf-8").write(HEAD + body + FOOT)
    print(f"generated {total} trail cards -> {OUT}")
