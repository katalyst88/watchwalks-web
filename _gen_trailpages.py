#!/usr/bin/env python3
"""Build one indexable page per trail — /trails/<slug>.html — plus sitemap.xml and robots.txt.

WHY THIS EXISTS: the site ranks for essentially nothing, and the one thing it owns that no competitor
has is 873 landmark photographs bound to 1,099 written stories across 41 real routes. trails.html
carries all 41 as cards on ONE url, so all of that text competes with itself for a single ranking.
A page per trail turns it into 41 pages that each answer a real query ("camino de santiago distance",
"te araroa landmarks") with material nobody else can copy.

READ BEFORE CHANGING ANYTHING HERE:

⛔⛔ NOTHING IS EVER OVERLAID ON A LANDMARK PHOTOGRAPH, AND THE PHOTOGRAPH IS COPIED BYTE FOR BYTE.
   They are CC BY-SA / CC BY. ShareAlike would drag Watch Walks' own artwork into the licence the
   moment we composited anything onto one, so the files are `shutil.copy2`'d unmodified — no resize,
   no recompress, no watermark, no gradient, nothing. COPY_FRAMEWORK §6 states this and it is a
   licence condition, not a courtesy. The credit is rendered in the <figcaption> DIRECTLY BENEATH the
   image, and a landmark whose manifest carries no credit is rendered WITHOUT its photograph rather
   than with an uncredited one.

⛔⛔ THE PHOTO IS RESOLVED BY SLUG, NEVER BY POSITION. The manifests say `keyedBy: slug` because
   resolving by index once handed the Sun Gate a picture of Machu Picchu. A page that names one place
   and shows another is worse than no page.

⚠️ NOT NAMING THE PASS. JD's standing rule: "Dead Woman's Pass" never appears on a marketing surface,
   and a public web page is a marketing surface. `_gen_attribution.py` already honours it; a rule
   implemented in one generator and not the other is not implemented. See MARKETING_NAME below.

⚠️ THE WALKING PACE IS NOT COPIED — IT IS IMPORTED from `_gen_profiles.py`, which is where the site's
   ONE pace lives (5,000 steps a day x 0.72 m stride = 3.6 km/day). The site has already shipped two
   different paces once and told a walker they would finish the Camino eleven weeks before they would.
   There is no second copy of that constant in this file, and `duration()` is the same function the
   trail cards use, so a page and the card that links to it cannot disagree.

⚠️ EVERY NUMBER AND EVERY NAME COMES OUT OF A DATA FILE. Distances from the shipping app's
   SampleData.kt; landmark names, km marks, coordinates and stories from trails/<id>.json; photos and
   credits from the shipped ODR manifests. Nothing on these pages is typed by hand except the framing
   sentences, and those are run through marketing/slopcheck.py before they are written (--strict makes
   a hard fail abort the build).

⚠️ COLOUR. Every colour on the page is a styles.css token (--bg/--bg2/--line/--text/--subtle/--accent)
   so the dark theme works for free. The ONE literal is `--tc`, the trail's own identity colour, read
   live from `_trail_colors.py` and used exactly as trails.html already uses it: a decorative spine and
   a colour-mix tint. It is NEVER used as a text colour, so it cannot fail contrast.

Usage:
    python _gen_trailpages.py            # build pages + copy photos + sitemap + robots
    python _gen_trailpages.py --dry      # build nothing, report what it would do
    python _gen_trailpages.py --no-photos  # pages only, skip the ~280 MB photo copy
    python _gen_trailpages.py --strict   # abort if any generated sentence fails slopcheck
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # C:\Users\jwden\WatchApps
WEB = HERE
OUTDIR = os.path.join(WEB, "trails")
PHOTODIR = os.path.join(WEB, "img", "landmarks")
TRAILJSON = os.path.join(ROOT, "trails")
ODR = os.path.join(ROOT, "watchwalks-ios", "Resources", "odr")
GEO = os.path.join(ROOT, "watchwalks-ios", "Core", "Sources", "WatchWalksCore", "TrailGeo.swift")
KT = os.path.join(ROOT, "watchwalks-android", "app", "src", "main", "java", "com", "watchwalks",
                  "companion", "data", "SampleData.kt")
MARKETING = os.path.join(ROOT, "marketing")
SITE = "https://watchwalks.com"
CSS_V = "v=20260717"          # the site's cache-buster. Do not change it here alone.
PAGE_CSS_V = "v=20260902"     # trailpage.css only — new file, its own buster.

sys.path.insert(0, WEB)
sys.path.insert(0, MARKETING)
import _gen_profiles as prof            # the ONE pace + the ONE duration() the cards use
from _trail_colors import C1 as TRAIL_COLOR
import slopcheck                        # the house copy checker

# See the module docstring. Display-only; the trail data keeps the real name.
MARKETING_NAME = {"Dead Woman's Pass": "Warmiwañusca"}

# ⚠️ RENAMING THE MILESTONE IS NOT ENOUGH, and this is the part `_gen_attribution.py` never had to
# solve: it prints names only, while these pages print the STORIES, and the name appears inside three
# of the Inca Trail's stories as well ("...the last open ground before Dead Woman's Pass"). Swapping
# the heading and leaving the prose would put the banned name on the page three times over, under a
# heading that no longer matched it. Order matters — the appositive form has to go first, or rule 2
# turns "Warmiwañusca — Dead Woman's Pass —" into "Warmiwañusca — Warmiwañusca —".
PROSE_SCRUB = [
    ("Warmiwañusca — Dead Woman's Pass — ", "Warmiwañusca "),
    ("Dead Woman's Pass", "Warmiwañusca"),
    ("Dead Woman's", "Warmiwañusca"),
]
# The names that must not survive onto a marketing surface, asserted after every substitution.
BANNED_ON_SITE = ["Dead Woman"]


def scrub(text):
    """Apply the display rules to a block of shipped prose, then PROVE the banned name is gone."""
    if not text:
        return text
    for a, b in PROSE_SCRUB:
        text = text.replace(a, b)
    for bad in BANNED_ON_SITE:
        if bad in text:
            raise SystemExit(f"a banned name survived the scrub — add a rule for it:\n  {text}")
    return re.sub(r"  +", " ", text)

CONTINENT = {
    "SOUTH_AMERICA": "South America", "NORTH_AMERICA": "North America", "EUROPE": "Europe",
    "ASIA": "Asia", "AFRICA": "Africa", "OCEANIA": "Oceania", "ANTARCTICA": "Antarctica",
}

# Milestone `type` -> the word a reader understands. The raw values are app enum names.
TYPE_WORD = {
    "start": "Start", "finish": "Finish", "pass": "Mountain pass", "summit": "Summit",
    "camp": "Camp", "water": "Water", "forest": "Forest", "bridge": "Bridge",
    "town": "Town", "landmark": "Landmark",
}

# Pages that are deliberately kept out of the index (both carry <meta name="robots" content="noindex">).
NOINDEX = {"coming-soon.html", "thanks.html", "_og.html"}


# ── data ─────────────────────────────────────────────────────────────────────────────────────────
def marketing_name(name):
    return MARKETING_NAME.get(name, name)


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"['\u2019]", "", s).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def tile_keys():
    """trail id -> ODR pack key, read from the app's own table rather than kept as a second copy.

    ⚠️ Start AFTER the opening bracket: slicing from the type annotation cuts inside it and returns an
    empty map, which reads as "0 landmarks" rather than as a parse failure.
    """
    src = open(GEO, encoding="utf-8").read()
    marker = "tileKeys: [String: String] = ["
    body = src[src.index(marker) + len(marker):]
    body = body[:body.index("\n    ]")]
    return dict(re.findall(r'"([a-z0-9-]+)"\s*:\s*"([a-z0-9]+)"', body))


def _unescape_kt(s):
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def trails():
    """The 41 shipping trails, from the app's own registry. The site does not get to hold a second list."""
    kt = open(KT, encoding="utf-8").read()
    out = []
    for line in kt.splitlines():
        line = line.strip()
        if not line.startswith('Trail("'):
            continue
        m = re.match(r'Trail\("([a-z0-9-]+)",\s*"([^"]+)",\s*"([^"]*)",\s*(\d+),\s*"([^"]*)"(.*)', line)
        if not m:
            raise SystemExit("Trail(...) line did not parse — the registry shape changed:\n  " + line)
        rest = m.group(6)
        cont = re.search(r"continent\s*=\s*Continent\.([A-Z_]+)", rest)
        out.append({
            "id": m.group(1), "name": _unescape_kt(m.group(2)), "region": _unescape_kt(m.group(3)),
            "km": int(m.group(4)), "destination": _unescape_kt(m.group(5)),
            "free": "free = true" in rest,
            "continent": CONTINENT.get(cont.group(1), "") if cont else "",
        })
    return out


def blurbs():
    kt = open(KT, encoding="utf-8").read()
    blk = kt[kt.index("private val blurbs"):]
    blk = blk[:blk.index("\n    )")]
    return {k: _unescape_kt(v) for k, v in re.findall(r'"([a-z0-9-]+)"\s+to\s+"((?:[^"\\]|\\.)*)"', blk)}


def milestones(tid, packkey):
    """Every milestone on this trail, with its photograph resolved BY SLUG where one exists.

    A milestone with a photo but no credit is returned WITHOUT the photo — see the licence note at
    the top of this file. A milestone with no photo still gets its story; a milestone with neither
    still gets its name and its distance, because the route in order is itself useful.
    """
    tj = os.path.join(TRAILJSON, tid + ".json")
    if not os.path.exists(tj):
        return []
    raw = json.load(open(tj, encoding="utf-8")).get("milestones", [])

    # ⛔ HOW A PHOTO IS PAIRED TO A LANDMARK, AND WHY IT IS NOT BY NAME.
    # The manifest's `index` is the milestone's index in this same trail json — checked across all 38
    # packs, 0 mismatches — so the pairing is made on index and then VERIFIED against the name. A
    # mismatch drops the photo rather than guessing, because a page that names one place and shows
    # another is worse than a page with no picture.
    # Keying on the name alone looked equivalent and was not: four trails are LOOPS that pass through
    # the same town twice (Les Houches on the Tour du Mont Blanc, Longmire, Llámac, Tahoe City), the
    # manifest ships a SECOND photograph for the second visit under a `-2` slug, and a name-keyed dict
    # silently collapsed the pair — printing the return-leg photograph against the outbound landmark on
    # eight landmarks across four trails.
    photos = {}
    man = os.path.join(ODR, packkey, "milestones", "manifest.json") if packkey else None
    if man and os.path.exists(man):
        for e in json.load(open(man, encoding="utf-8")).get("milestones", []):
            i = e.get("index")
            if i is None or not e.get("image") or not (e.get("credit") or "").strip():
                continue
            if i >= len(raw) or raw[i].get("name") != e.get("name"):
                print(f"  ! {tid}: manifest index {i} is {e.get('name')!r} but the trail says "
                      f"{raw[i].get('name') if i < len(raw) else '<out of range>'!r} — photo dropped")
                continue
            src = os.path.join(ODR, packkey, "milestones", e["image"])
            if os.path.exists(src):
                photos[i] = {"slug": e["slug"], "file": e["image"], "src": src,
                             "credit": e["credit"].strip(), "source": e.get("source", "")}

    out = []
    seen_anchor = {}
    for idx, m in enumerate(raw):
        real = m.get("name")
        if not real:
            continue
        shown = marketing_name(real)
        # A loop trail passes the same town twice, so the same anchor id would appear twice on the
        # page — invalid HTML, and the second JSON-LD url would point at the first landmark.
        anchor = slugify(shown)
        seen_anchor[anchor] = seen_anchor.get(anchor, 0) + 1
        if seen_anchor[anchor] > 1:
            anchor = f"{anchor}-{seen_anchor[anchor]}"
        p = photos.get(idx)
        out.append({
            "name": shown, "anchor": anchor, "km": m.get("km"),
            "type": m.get("type", ""), "story": scrub((m.get("story") or "").strip()),
            "lat": m.get("lat"), "lng": m.get("lng"), "photo": p,
        })
    return out


def image_size(path):
    """Real pixel dimensions, so the page reserves the space and nothing shifts as photos arrive."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


# ── the sentences this file writes (everything else comes out of a data file) ────────────────────
def _pick(options, seed):
    return options[sum(ord(c) for c in seed) % len(options)]


_THE_ENDINGS = ("Trail", "Track", "Way", "Route", "Circuit", "Road", "Traverse", "Pilgrimage")


def with_article(name):
    """Whether the name takes "the". Checked by eye against all 41, because "into the Route 66" and
    "into the Walk the Nile" are what you get for guessing, on 41 pages at once."""
    if name.startswith(("The ", "Walk ", "Last Degree")):
        return name
    if name.startswith(("Camino", "Length of", "Tour du")):
        return "the " + name
    if "(" in name:
        return name
    if name.endswith(_THE_ENDINGS):
        return "the " + name
    return name


def eyebrow(t):
    """Continent and region, unless they are the same word.

    ⚠️ Antarctica is both, and the page shipped "ANTARCTICA - ANTARCTICA" until a screenshot showed it.
    """
    c, r = t["continent"] or "", t["region"] or ""
    if not c or c.lower() == r.lower():
        return r or c or "Trail"
    return f"{c} \u00b7 {r}"


def region_prose(region):
    """The region as it can sit after a preposition.

    ⚠️ "runs 3,940 km through USA" and "through USA (California)" are what you get for dropping a raw
    data field into a sentence, and it would have shipped on eight pages. The parenthetical is a
    qualifier for the stats strip, not for prose, so prose uses the part before it — nothing is
    invented, only left out. The full string still appears verbatim in the page eyebrow.
    """
    base = region.split(" (")[0].strip()
    if base.startswith(("USA", "United ", "Netherlands", "Philippines")):
        return "the " + base
    return base


def _closer(n, has_story, has_photo, seed):
    """The last line of the lead. It states what is actually on the page.

    ⚠️ The first draft promised "a photograph and a story for each" on every trail, which is a lie on
    the four trails with no photographs and on the South Pole route, which carries no stories at all.
    A page that promises material it does not have is worse than a short page.
    """
    if has_story and has_photo:
        forms = [f"Below are the {n} places you pass, each with its photograph and its story.",
                 f"All {n} landmarks are below, in walking order, with a photograph and the story of the place.",
                 f"Here are its {n} landmarks, in the order you meet them, photographed and written up."]
    elif has_story:
        forms = [f"Below are the {n} places you pass, and what happened at each one.",
                 f"All {n} landmarks are below, in walking order, with the story of each.",
                 f"Here are its {n} landmarks, in the order you meet them, and what each one is."]
    else:
        forms = [f"Below are the {n} landmarks, in the order you reach them.",
                 f"All {n} landmarks are listed below, in walking order.",
                 f"Here are its {n} landmarks, in the order the route meets them."]
    return _pick(forms, seed)


def lead_copy(t, n_landmarks, dur, has_story, has_photo, first_landmark=""):
    """The one paragraph under the h1. Assembled from four varied slots rather than one fixed
    sentence — 41 pages opening identically is the uniform-repetition tell BRAND §5 names outright.

    The short "you begin at X" line is not filler: it is the trail's real first milestone, it names a
    place (BRAND §2 wants the place, not "amazing experiences"), and it breaks a three-sentence
    paragraph of near-identical length, which slopcheck flags as the strongest AI rhythm tell after
    word choice.
    """
    a = with_article(t["name"])
    km = f"{t['km']:,}"
    reg = region_prose(t["region"])
    opens = [
        f"{t['name']} runs {km} km through {reg} and finishes at {t['destination']}.",
        f"{km} km through {reg}, ending at {t['destination']}.",
        f"There are {km} km between the two ends of {a}, and {t['destination']} is the far one.",
        f"{t['name']} crosses {reg} for {km} km and ends at {t['destination']}.",
    ]
    paces = [
        f"Watch Walks moves you along it with the steps you already take, so it's {dur} at 5,000 "
        f"steps a day.",
        f"Your ordinary week counts toward all of it: at 5,000 steps a day that's {dur}, with no "
        f"flights and no leave.",
        f"At 5,000 steps a day it's {dur} of the walking you do anyway.",
    ]
    starts = [f"You begin at {first_landmark}.",
              f"It starts at {first_landmark}.",
              f"The first landmark is {first_landmark}."]
    out = [_pick(opens, t["id"])]
    if first_landmark:
        out.append(_pick(starts, t["id"] + "s"))
    out.append(_pick(paces, t["id"] + "p"))
    out.append(_closer(n_landmarks, has_story, has_photo, t["id"] + "c"))
    return " ".join(out)


def cta_copy(t):
    a = with_article(t["name"])
    if t["free"]:
        price = "This trail is free."
    else:
        price = "The Inca Trail is free; this one is a one-time purchase with no subscription."
    return (f"Your watch is already counting these steps. Watch Walks spends them on {a}, all "
            f"{t['km']:,} km of it, and hands you each landmark as you reach it. There's no route "
            f"recording, no account and no ads. {price}")


def landmarks_intro(n, with_photos):
    if with_photos:
        return (f"{n} landmarks, in walking order. Each photograph is by the person credited beneath "
                f"it, used as they licensed it.")
    return f"{n} landmarks, in walking order."


def meta_description(t, n_landmarks, dur, has_story, has_photo):
    a = with_article(t["name"])
    km = f"{t['km']:,}"
    reg = region_prose(t["region"])
    if has_story and has_photo:
        what = f"All {n_landmarks} landmarks, with photographs and stories."
        of = "in walking order, with a photograph and a story for each"
    elif has_story:
        what = f"All {n_landmarks} landmarks, with the story of each."
        of = "in walking order, with the story of each"
    else:
        what = f"All {n_landmarks} landmarks, in walking order."
        of = "in walking order"
    forms = [
        f"{t['name']}: {km} km through {reg} to {t['destination']}, and the {n_landmarks} "
        f"landmarks along the way. Walk the route with your everyday steps in Watch Walks.",
        f"How long is {a}? {km} km, ending at {t['destination']}, and that's {dur} at 5,000 steps "
        f"a day. {what}",
        f"The {n_landmarks} landmarks of {a}, {of}. {km} km through {reg} to {t['destination']}.",
    ]
    return _pick(forms, t["id"] + "meta")


def check_copy(label, text, strict, problems):
    hard, soft, _ = slopcheck.check(text)
    if hard:
        problems.append((label, hard))
        print(f"  !! slopcheck HARD FAIL {label}: {hard}")
        if strict:
            raise SystemExit("aborting on --strict")
    return hard, soft


# ── page ─────────────────────────────────────────────────────────────────────────────────────────
def _reroot(block):
    """Rewrite the site chrome's own relative links for a page one directory down."""
    return re.sub(r'((?:href|src)=")(?!https?:|mailto:|tel:|#|\.\./|/)', '\\1../', block)


def site_chrome():
    """Take the header and footer VERBATIM from contact.html and re-root their links.

    ⚠️ These were hand-copied at first and were already wrong within the hour: contact.html's footer
    carries a `.foot-social` block with the Instagram and Facebook links, and the copy silently
    dropped it — which no test caught and only the screenshot showed. Chrome that is copied drifts;
    chrome that is read cannot.
    """
    src = open(os.path.join(WEB, "contact.html"), encoding="utf-8").read()
    hdr = src[src.index("<header>"):src.index("</header>") + len("</header>")]
    ftr = src[src.index("<footer>"):src.index("</footer>") + len("</footer>")]
    return _reroot(hdr), _reroot(ftr)


def head_and_nav(title, desc, canon, og_image, extra_head, header):
    e = html.escape
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Watch Walks">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta property="og:image" content="{e(og_image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(og_image)}">
<meta name="theme-color" content="#1F5C3D">
<link rel="icon" type="image/svg+xml" href="../favicon.svg">
<link rel="apple-touch-icon" href="../favicon.svg">
<link rel="stylesheet" href="../styles.css?{CSS_V}">
<link rel="stylesheet" href="../trailpage.css?{PAGE_CSS_V}">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>

{header}
"""


FOOTER_TAIL = """

<script src="../openin.js"></script>
</body>
</html>
"""


def jsonld(t, url, ms, og_image):
    """BreadcrumbList + a TouristTrip whose itinerary is the real landmark list with real coordinates.

    Validated by json.dumps/loads on the way out — a structured-data block that does not parse is worse
    than none, because it fails silently and nothing on the page shows it.
    """
    crumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Watch Walks", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Trails", "item": SITE + "/trails.html"},
            {"@type": "ListItem", "position": 3, "name": t["name"], "item": url},
        ],
    }
    items = []
    for i, m in enumerate(ms, 1):
        place = {"@type": "TouristAttraction" if m["type"] in ("landmark", "summit", "pass", "town")
                 else "Place", "name": m["name"], "url": url + "#" + m["anchor"]}
        if m["story"]:
            place["description"] = m["story"]
        if m["lat"] is not None and m["lng"] is not None:
            place["geo"] = {"@type": "GeoCoordinates", "latitude": round(float(m["lat"]), 6),
                            "longitude": round(float(m["lng"]), 6)}
        if m["photo"]:
            place["image"] = f"{SITE}/img/landmarks/{m['photo']['pack']}/{m['photo']['file']}"
        items.append({"@type": "ListItem", "position": i, "item": place})

    # ⚠️ ONLY PROPERTIES schema.org ACTUALLY DEFINES ON Trip/TouristTrip go in here. The first cut
    # carried `distance` and `arrivalPlace`, which read as obviously right and are on neither type
    # (Trip defines arrivalTime, departureTime, itinerary, offers, partOfTrip, provider, subTrip;
    # TouristTrip adds touristType). Invented properties are ignored silently, which is exactly how
    # structured data rots — so the distance and the destination go in the description, where they
    # are read.
    desc = t["blurb"] + " " if t["blurb"] else ""
    trip = {
        "@context": "https://schema.org", "@type": "TouristTrip",
        "name": t["name"], "url": url, "image": og_image,
        "description": (f"{desc}{t['name']} runs {t['km']} km through {t['region']}, "
                        f"finishing at {t['destination']}."),
        "touristType": "Walkers",
        "itinerary": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items},
    }
    out = []
    for obj in (crumbs, trip):
        s = json.dumps(obj, ensure_ascii=False, indent=1)
        json.loads(s)   # parses, or this build stops here
        out.append('<script type="application/ld+json">\n' + s + '\n</script>\n')
    return "".join(out)


def render(t, ms, related, dur, strict, problems):
    e = html.escape
    n = len(ms)
    withphoto = sum(1 for m in ms if m["photo"])
    slug = t["slug"]
    url = f"{SITE}/trails/{slug}.html"
    og_image = f"{SITE}/img/trailmaps/{t['id']}.webp"
    colour = TRAIL_COLOR.get(t["id"])

    has_story = any(m["story"] for m in ms)
    has_photo = withphoto > 0
    title = f"{t['name']} — {t['km']:,} km and its {n} landmarks | Watch Walks"
    desc = meta_description(t, n, dur, has_story, has_photo)
    lead = lead_copy(t, n, dur, has_story, has_photo, ms[0]["name"] if ms else "")
    cta = cta_copy(t)
    intro = landmarks_intro(n, has_photo)
    for label, txt in (("lead", lead), ("cta", cta), ("meta", desc)):
        check_copy(f"{t['id']}/{label}", txt, strict, problems)

    hdr, ftr = site_chrome()
    parts = [head_and_nav(title, desc, url, og_image, jsonld(t, url, ms, og_image), hdr)]
    style = f' style="--tc:{colour}"' if colour else ""
    parts.append(f'\n<main id="main" tabindex="-1" class="wrap tp"{style}>\n')

    # breadcrumb — the visible twin of the BreadcrumbList above
    parts.append(
        '  <nav class="bc" aria-label="Breadcrumb">\n'
        '    <a href="../index.html">Home</a> <span aria-hidden="true">/</span> '
        '<a href="../trails.html">Trails</a> <span aria-hidden="true">/</span> '
        f'<span aria-current="page">{e(t["name"])}</span>\n'
        '  </nav>\n\n')

    # hero
    tag = '<span class="tag free">Free</span>' if t["free"] else ""
    parts.append(
        '  <section class="tp-hero">\n'
        f'    <span class="eyebrow">{e(eyebrow(t))}</span>\n'
        f'    <h1>{e(t["name"])} {tag}</h1>\n')
    if t["blurb"]:
        parts.append(f'    <p class="tp-blurb">{e(t["blurb"])}</p>\n')
    parts.append(f'    <p class="lead">{e(lead)}</p>\n')
    parts.append(
        '    <ul class="tp-stats">\n'
        f'      <li><b>{t["km"]:,}</b><span>km end to end</span></li>\n'
        f'      <li><b>{n}</b><span>landmarks</span></li>\n'
        f'      <li><b>{e(dur.replace("about ", ""))}</b><span>at 5,000 steps a day</span></li>\n'
        f'      <li><b>{e(t["destination"])}</b><span>finishes at</span></li>\n'
        '    </ul>\n')
    mapfile = os.path.join(WEB, "img", "trailmaps", t["id"] + ".webp")
    if os.path.exists(mapfile):
        parts.append(
            f'    <img class="tp-map" src="../img/trailmaps/{t["id"]}.webp" width="680" height="430"\n'
            f'         alt="Satellite route map of {e(t["name"])}" loading="eager" decoding="async">\n')
    parts.append('  </section>\n\n')

    # landmarks
    parts.append('  <section class="tp-lms">\n')
    parts.append(f'    <h2 id="landmarks">The landmarks of {e(t["name"])}</h2>\n')
    parts.append(f'    <p class="sub">{e(intro)}</p>\n')
    if ms:
        parts.append('    <ol class="lm-list">\n')
        for m in ms:
            parts.append(f'      <li class="lm" id="{e(m["anchor"])}">\n')
            if m["photo"]:
                p = m["photo"]
                dim = f' width="{p["w"]}" height="{p["h"]}"' if p.get("w") else ""
                parts.append(
                    '        <figure class="lm-shot">\n'
                    f'          <img src="../img/landmarks/{p["pack"]}/{p["file"]}"{dim} loading="lazy"\n'
                    f'               decoding="async" alt="{e(m["name"])} on {e(with_article(t["name"]))}">\n'
                    # ⛔ The credit sits with the image. CC BY-SA is not satisfied by a credits page alone.
                    f'          <figcaption>Photo: {e(p["credit"])}</figcaption>\n'
                    '        </figure>\n')
            parts.append('        <div class="lm-body">\n')
            # Escape each field, THEN join with the entity. Escaping the joined string turns the
            # separator into a literal "&middot;" on the page.
            bits = []
            if m["km"] is not None:
                bits.append(e(f'{m["km"]:,.0f} km in'))
            if TYPE_WORD.get(m["type"]):
                bits.append(e(TYPE_WORD[m["type"]]))
            if bits:
                parts.append(f'          <p class="lm-meta">{" &middot; ".join(bits)}</p>\n')
            parts.append(f'          <h3>{e(m["name"])}</h3>\n')
            if m["story"]:
                parts.append(f'          <p class="lm-story">{e(m["story"])}</p>\n')
            parts.append('        </div>\n      </li>\n')
        parts.append('    </ol>\n')
    parts.append('  </section>\n\n')

    # honest CTA
    parts.append(
        '  <section class="tp-cta">\n'
        f'    <h2>Walking {e(with_article(t["name"]))}</h2>\n'
        f'    <p>{e(cta)}</p>\n'
        '    <p><a class="btn" href="../index.html#get">Get Watch Walks</a></p>\n'
        '    <p class="sub"><a href="../faq.html">Questions</a> &middot; '
        '<a href="../compatibility.html">Which watches work</a> &middot; '
        '<a href="../attribution.html">Photograph credits in full</a></p>\n'
        '  </section>\n\n')

    if related:
        parts.append('  <section class="tp-rel">\n'
                     f'    <h2>Other trails in {e(t["continent"])}</h2>\n'
                     '    <ul class="rel-list">\n')
        for r in related:
            parts.append(f'      <li><a href="{r["slug"]}.html">{e(r["name"])}</a> '
                         f'<span>{r["km"]:,} km &middot; {e(r["region"])}</span></li>\n')
        parts.append('    </ul>\n'
                     '    <p class="sub"><a href="../trails.html">See all 41 trails</a></p>\n'
                     '  </section>\n')

    parts.append('\n</main>\n\n')
    parts.append(ftr)
    parts.append(FOOTER_TAIL)
    return "".join(parts)


# ── the shared stylesheet for these pages ────────────────────────────────────────────────────────
PAGE_CSS = """/* Per-trail page styles. Generated pages only — styles.css is untouched, so its cache buster
   (v=20260717) stays valid for every existing page.

   ⚠️ EVERY COLOUR HERE IS A styles.css TOKEN. Hardcoding one broke a page on 2026-09-01; the dark
   theme is entirely token-driven, so a literal colour is a page that is unreadable at night.
   The single exception is --tc, the trail's own identity colour, set inline on <main> from the app's
   TrailArt map — and it is used only as a spine and a tint, never as text, so it cannot fail contrast. */

.tp { padding-bottom: 24px; }

.bc { font-size: 13px; color: var(--subtle); padding: 20px 0 0; }
.bc a { color: var(--subtle); text-decoration: underline; text-underline-offset: 2px; }
.bc a:hover { color: var(--text); }
.bc span[aria-hidden] { padding: 0 4px; }

.tp-hero { border-top: none; padding: 22px 0 30px; }
.tp-hero h1 {
  font-size: clamp(30px, 4.6vw, 46px); font-weight: 800; letter-spacing: -0.02em;
  line-height: 1.08; margin-top: 10px;
}
.tp-hero h1 .tag { vertical-align: middle; margin-left: 8px; }
.tp-blurb { font-size: 19px; color: var(--text); margin-top: 14px; max-width: 40em; }
.tp-hero .lead { max-width: 42em; margin-top: 14px; }

.tp-stats {
  list-style: none; display: flex; flex-wrap: wrap; gap: 10px; margin: 26px 0 0;
}
.tp-stats li {
  flex: 1 1 150px; padding: 14px 16px; border-radius: var(--r-card);
  background: linear-gradient(90deg, color-mix(in srgb, var(--tc, var(--accent)) 10%, var(--bg2)), var(--bg2) 70%);
  border: 1px solid color-mix(in srgb, var(--tc, var(--accent)) 30%, var(--line));
  border-left: 4px solid var(--tc, var(--accent));   /* the trail's own spine, as in the app */
}
.tp-stats b { display: block; font-family: var(--font-display); font-size: 24px; line-height: 1.1; }
.tp-stats span { display: block; margin-top: 4px; font-size: 13px; color: var(--subtle); }

.tp-map {
  display: block; width: 100%; height: auto; margin-top: 26px;
  border-radius: var(--r-panel); border: 1px solid var(--line); box-shadow: var(--sh-card);
}

.tp-lms { border-top: 1px solid var(--line); padding: 44px 0 10px; }
.tp-lms h2, .tp-cta h2, .tp-rel h2 { font-size: clamp(22px, 3vw, 30px); letter-spacing: -0.01em; }
.tp-lms .sub, .tp-cta .sub, .tp-rel .sub { color: var(--subtle); font-size: 15px; margin-top: 8px; }

.lm-list { list-style: none; margin: 30px 0 0; display: grid; gap: 26px; }
/* The site header is sticky, so a link to #roncesvalles lands with the landmark's own heading tucked
   underneath it. Measured against the real header height, not guessed. */
.lm, .tp-lms h2 { scroll-margin-top: 84px; }
.lm {
  display: grid; grid-template-columns: 300px 1fr; gap: 22px; align-items: start;
  padding-bottom: 26px; border-bottom: 1px solid var(--line);
}
.lm:last-child { border-bottom: none; }
.lm-shot { margin: 0; }
/* ⛔ The photograph is served exactly as licensed: nothing is drawn over it, and the credit below is
   part of the licence, not decoration. object-fit crops the frame, it does not alter the file. */
.lm-shot img {
  /* Natural aspect ratio, never a fixed height with object-fit: cover. A crop is a display decision
     we do not get to make on somebody else's photograph, and a 300x200 box was cutting the top and
     bottom off every portrait shot in the library. Ragged column heights are the editorial layout
     BRAND §3 asks for anyway. */
  display: block; width: 100%; height: auto; max-height: 400px; object-fit: contain;
  border-radius: var(--r-card); border: 1px solid var(--line); background: var(--bg3);
}
.lm-shot figcaption { margin-top: 7px; font-size: 12px; line-height: 1.45; color: var(--subtle); }
.lm-meta {
  font-size: 12px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase;
  color: var(--accent);
}
.lm-body h3 { font-size: 21px; margin-top: 5px; }
.lm-story { margin-top: 9px; font-size: 16px; line-height: 1.65; color: var(--text); max-width: 44em; }

.tp-cta { border-top: 1px solid var(--line); padding: 44px 0; }
.tp-cta p { max-width: 44em; margin-top: 12px; font-size: 17px; line-height: 1.6; }
.tp-rel { border-top: 1px solid var(--line); padding: 40px 0 10px; }
.rel-list { list-style: none; margin: 22px 0 0; display: grid; gap: 8px; grid-template-columns: repeat(2, 1fr); }
.rel-list li { padding: 11px 14px; border: 1px solid var(--line); border-radius: var(--r-card); background: var(--bg2); }
.rel-list a { font-weight: 700; }
.rel-list span { display: block; font-size: 13px; color: var(--subtle); margin-top: 2px; }

@media (max-width: 860px) {
  .lm { grid-template-columns: 1fr; gap: 14px; }
  .lm-shot { max-width: 420px; }
  .rel-list { grid-template-columns: 1fr; }
}
"""


# ── sitemap / robots / trails.html links ─────────────────────────────────────────────────────────
def write_sitemap(pages, dry):
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, pri in pages:
        body.append(f'  <url><loc>{loc}</loc><priority>{pri}</priority></url>')
    body.append('</urlset>')
    txt = "\n".join(body) + "\n"
    print(f"sitemap.xml: {len(pages)} urls")
    if not dry:
        open(os.path.join(WEB, "sitemap.xml"), "w", encoding="utf-8").write(txt)


def fix_robots(dry):
    """Extend, never replace — the existing file carries a Disallow whose comment explains a real
    incident (a debug-signed APK that was served publicly). Only ensure the Sitemap line is right."""
    p = os.path.join(WEB, "robots.txt")
    txt = open(p, encoding="utf-8").read()
    want = f"Sitemap: {SITE}/sitemap.xml"
    if want in txt:
        print("robots.txt: already points at the sitemap — left alone")
        return
    txt = txt.rstrip() + "\n" + want + "\n"
    if not dry:
        open(p, "w", encoding="utf-8").write(txt)
    print("robots.txt: sitemap line added")


def link_trails_page(bysl, dry):
    """Put a link to each new page inside its card on trails.html. Idempotent: any previous tc-more is
    stripped first, so running this twice does not stack two links."""
    p = os.path.join(WEB, "trails.html")
    txt = open(p, encoding="utf-8").read()
    txt = re.sub(r'<p class="tc-more"[^>]*>.*?</p>', "", txt, flags=re.S)

    added = [0]

    def fix(m):
        tid = m.group(1)
        block = m.group(0)
        s = bysl.get(tid)
        if not s:
            return block
        # No colour, no new class in styles.css — the anchor inherits the site's accent link colour,
        # so this cannot go stale against the v=20260717 cache buster.
        link = (f'<p class="tc-more" style="margin-top:12px;font-size:14px;font-weight:700">'
                f'<a href="trails/{s}.html">Read the {html.escape(m.group(2))} guide</a></p>')
        i = block.rfind("</div></article>")
        if i < 0:
            return block
        added[0] += 1
        return block[:i] + link + block[i:]

    # Each card is <article class="tcard" data-trail="ID" ...> ... <h3>NAME</h3> ... </article>
    def repl(m):
        return fix(m)

    pat = re.compile(r'<article class="tcard" data-trail="([a-z0-9-]+)".*?<h3>([^<]+)</h3>.*?</article>',
                     re.S)
    txt = pat.sub(repl, txt)
    print(f"trails.html: {added[0]} cards linked to their trail page")
    if not dry:
        open(p, "w", encoding="utf-8").write(txt)
    return added[0]


def add_missing_canonicals(dry):
    """8 existing pages ship with no canonical at all. Found while building the sitemap; a page with no
    canonical is a page that can be indexed under any query string as a duplicate of itself."""
    fixed = []
    for f in sorted(os.listdir(WEB)):
        if not f.endswith(".html") or f in NOINDEX:
            continue
        p = os.path.join(WEB, f)
        txt = open(p, encoding="utf-8").read()
        if 'rel="canonical"' in txt:
            continue
        m = re.search(r'^<meta name="description"[^>]*>$', txt, flags=re.M)
        if not m:
            print(f"  ! {f}: no <meta name=description> to anchor a canonical to — skipped")
            continue
        loc = SITE + "/" + ("" if f == "index.html" else f)
        ins = m.group(0) + f'\n<link rel="canonical" href="{loc}">'
        txt = txt[:m.start()] + ins + txt[m.end():]
        if not dry:
            open(p, "w", encoding="utf-8").write(txt)
        fixed.append(f)
    print(f"canonicals added to {len(fixed)} existing pages: {', '.join(fixed) or 'none'}")
    return fixed


# ── build ────────────────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="write nothing")
    ap.add_argument("--no-photos", action="store_true", help="skip the photo copy (~280 MB)")
    ap.add_argument("--strict", action="store_true", help="abort on any slopcheck hard fail")
    ap.add_argument("--only", default="", help="build one trail id, for a quick look")
    a = ap.parse_args()

    keys, bl = tile_keys(), blurbs()
    ts = trails()
    seen = {}
    for t in ts:
        t["slug"] = slugify(t["name"])
        t["blurb"] = scrub(bl.get(t["id"], ""))
        if t["slug"] in seen:
            raise SystemExit(f"slug collision: {t['slug']} ({t['id']} and {seen[t['slug']]})")
        seen[t["slug"]] = t["id"]

    bysl = {t["id"]: t["slug"] for t in ts}
    problems, copied, skipped_uncredited = [], 0, 0
    if not a.dry:
        os.makedirs(OUTDIR, exist_ok=True)
        open(os.path.join(WEB, "trailpage.css"), "w", encoding="utf-8").write(PAGE_CSS)

    built = []
    for t in ts:
        if a.only and t["id"] != a.only:
            continue
        ms = milestones(t["id"], keys.get(t["id"], ""))
        # resolve photo files: copy byte-for-byte, read real dimensions
        for m in ms:
            if not m["photo"]:
                continue
            pack = keys[t["id"]]
            m["photo"]["pack"] = pack
            dest = os.path.join(PHOTODIR, pack, m["photo"]["file"])
            if a.no_photos:
                m["photo"]["w"] = m["photo"]["h"] = None
                continue
            if not a.dry:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if not (os.path.exists(dest)
                        and os.path.getsize(dest) == os.path.getsize(m["photo"]["src"])):
                    shutil.copy2(m["photo"]["src"], dest)   # unmodified. see the licence note.
                    copied += 1
            sz = image_size(m["photo"]["src"])
            m["photo"]["w"], m["photo"]["h"] = (sz or (None, None))

        dur = prof.duration(t["km"])
        rel = [r for r in ts if r["continent"] == t["continent"] and r["id"] != t["id"]][:6]
        page = render(t, ms, rel, dur, a.strict, problems)
        if not a.dry:
            open(os.path.join(OUTDIR, t["slug"] + ".html"), "w", encoding="utf-8").write(page)
        withphoto = sum(1 for m in ms if m["photo"])
        withstory = sum(1 for m in ms if m["story"])
        built.append(t)
        print(f"  {t['slug']:32s} {len(ms):3d} landmarks  {withphoto:3d} photos  "
              f"{withstory:3d} stories  {t['km']:>5,} km  {dur}")

    print(f"\n{len(built)} trail pages, {copied} photographs copied unmodified")
    if skipped_uncredited:
        print(f"{skipped_uncredited} photographs skipped for having no credit")

    if a.only:
        return

    add_missing_canonicals(a.dry)
    link_trails_page(bysl, a.dry)

    pages = [(SITE + "/", "1.0")]
    for f in sorted(os.listdir(WEB)):
        if not f.endswith(".html") or f in NOINDEX or f == "index.html":
            continue
        pri = "0.8" if f in ("trails.html", "join-apple.html", "join-garmin.html",
                             "join-wearos.html") else \
              "0.7" if f in ("compatibility.html", "faq.html") else \
              "0.6" if f in ("contact.html", "links.html") else \
              "0.5" if f.startswith("setup-") else "0.3"
        pages.append((f"{SITE}/{f}", pri))
    for t in ts:
        pages.append((f"{SITE}/trails/{t['slug']}.html", "0.9"))
    write_sitemap(pages, a.dry)
    fix_robots(a.dry)

    if problems:
        print(f"\n!! {len(problems)} generated passages failed slopcheck:")
        for lbl, hard in problems:
            print(f"   {lbl}: {hard}")
    else:
        print("\nslopcheck: every generated passage passed the hard checks")


if __name__ == "__main__":
    main()
