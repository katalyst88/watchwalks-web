#!/usr/bin/env python3
"""_gen_polarmap.py — build the South Pole card map from REAL SATELLITE IMAGERY, so it matches every
other trail card.

WHY IT IS SEPARATE FROM _gen_satmaps.py. That tool projects to Web Mercator and pastes satellite tiles.
Mercator is UNDEFINED at the poles (it clamps at |lat| 85.05; the last degree runs -89 to -90), so the
Pole was the one trail with no card map — exactly the gap a reader's eye finds. The app already solved
this: TrailGeo.isPolar() routes this trail to a purpose-built polar map. This draws the card the same
way: azimuthal equidistant about the pole, where a line of longitude is a straight radius and a parallel
is a circle — both TRUE, and equal ground distances are equal distances on the page.

THIS SCRIPT USED TO SAY, IN ITS OWN DOCSTRING: "It does not fake satellite imagery; there is none" and
"no tile provider carries imagery there". Both are false, and the card printed the claim on its face:
"no satellite imagery exists at the pole".

The pole is imaged. MODIS on Terra and Aqua flies a near-polar sun-synchronous orbit and photographs the
plateau every summer day, and NASA GIBS serves it in EPSG:3031 (Antarctic Polar Stereographic), which —
unlike Mercator — is *defined* at 90°S. Probed before writing a line of this: a 512x512 GetMap centred on
the pole comes back 100% covered, and the centre pixel — the Pole itself — is (241,240,238). White ice,
photographed from orbit.

Worse, the site was already CREDITING that imagery. attribution.html has long read "The South Pole ... its
map is polar-projected NASA GIBS MODIS imagery (public domain)" while this script fetched nothing at all
and drew a synthetic navy plate. The credits page thanked NASA for an image containing no NASA data. Now
it is true.

WHY THE PLATE IS PALE AND CONTRAST-STRETCHED. The raw imagery is mean luminance 247 with a standard
deviation of 4.3 — the polar plateau really is a featureless white plain, and dropped in raw it is a blank
white rectangle. The stretch below pulls that 4 percent of range across the histogram, which is what makes
the sastrugi and the ice-surface morphology visible. It reveals what is there; it does not invent. This is
ordinary practice for polar imagery and it is why the attribution says MODIFIED.

    python _gen_polarmap.py
"""
import io
import json
import math
import os
import re
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"C:\Users\jwden\WatchApps"
WEB = os.path.dirname(os.path.abspath(__file__))
IMGDIR = os.path.join(WEB, "img", "trailmaps")
TID = "south-pole-last-degree"
W, H = 680, 430
TRAIL = (0xBD, 0xD3, 0xDB)      # --tc off this trail's own card
CASING = (12, 22, 34)
AMBER = (0xF5, 0xA6, 0x23)      # the start pin every other card uses

# NASA GIBS, EPSG:3031. TIME is an austral-summer date: the pole has six months of night, and MODIS is a
# visible-light sensor, so a July request returns black. Terra's true-colour over the plateau in January
# is the picture a walker would see.
GIBS = ("https://gibs.earthdata.nasa.gov/wms/epsg3031/best/wms.cgi?"
        "SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
        "&LAYERS=MODIS_Terra_CorrectedReflectance_TrueColor"
        "&CRS=EPSG:3031&BBOX={s},{s},{n},{n}&WIDTH={px}&HEIGHT={px}"
        "&FORMAT=image/png&TIME=2026-01-15")

# ---- EPSG:3031: Antarctic Polar Stereographic (WGS84, standard parallel -71, central meridian 0) ------
# Hand-rolled because pyproj isn't on this box. VERIFIED before use, not assumed:
#   k0 at the pole  = 0.972769  vs the published 0.97276 for EPSG:3031
#   scale at -71    = 1.000014  (the standard parallel is true scale BY DEFINITION — this is the check)
#   (-90, 0)        -> (0.0, 0.0)   the pole lands exactly on the origin
_A = 6378137.0
_F = 1 / 298.257223563
_E = math.sqrt(2 * _F - _F * _F)


def _t(phi):
    return math.tan(math.pi / 4 + phi / 2) / (((1 + _E * math.sin(phi)) / (1 - _E * math.sin(phi))) ** (_E / 2))


_PHI_F = math.radians(-71.0)
_mF = math.cos(_PHI_F) / math.sqrt(1 - _E * _E * math.sin(_PHI_F) ** 2)
_K = math.sqrt((1 + _E) ** (1 + _E) * (1 - _E) ** (1 - _E))
_k0 = _mF * _K / (2 * _t(_PHI_F))


def to3031(lat_deg, lon_deg):
    """(lat, lon) -> EPSG:3031 easting/northing in metres. Greenwich runs to +y."""
    rho = 2 * _A * _k0 * _t(math.radians(lat_deg)) / _K
    lam = math.radians(lon_deg)
    return rho * math.sin(lam), rho * math.cos(lam)


def font(sz):
    for f in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def route():
    src = open(os.path.join(ROOT, r"watchwalks-android\app\src\main\java\com\watchwalks\companion\data\TrailGeo.kt"),
               encoding="utf-8").read()
    m = re.search(r'"' + TID + r'" to listOf\(', src)
    i, d = m.end(), 1
    while d:
        if src[i] == "(":
            d += 1
        elif src[i] == ")":
            d -= 1
        i += 1
    return [(float(a), float(b), float(c)) for a, b, c in
            re.findall(r"GeoPoint\(([-0-9.]+)f?,\s*([-0-9.]+),\s*([-0-9.]+)", src[m.end():i - 1])]


def milestones():
    p = os.path.join(ROOT, "trails", TID + ".json")
    return json.load(open(p, encoding="utf-8"))["milestones"] if os.path.exists(p) else []


def fetch_gibs(half_m, px=1600):
    """One GetMap over a box `half_m` metres either side of the pole. Returns None if GIBS is unreachable,
    so a network blip degrades to the drawn plate instead of writing a broken card."""
    url = GIBS.format(s=-int(half_m), n=int(half_m), px=px)
    try:
        with urllib.request.urlopen(url, timeout=90) as r:
            raw = r.read()
        if raw[:5] == b"<?xml" or b"ServiceException" in raw[:400]:
            print("  ! GIBS returned an exception document, not an image")
            return None
        return Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        print(f"  ! GIBS unreachable ({type(e).__name__}) — falling back to the drawn plate")
        return None


def plate_from_imagery(span_deg, R):
    """Reproject the EPSG:3031 photograph into this card's azimuthal-equidistant frame.

    The two projections are both azimuthal about the pole, so a point's ANGLE is identical in each and only
    its RADIUS differs — stereographic stretches away from the pole while equidistant does not. Over the
    last degree that difference is small but it is not zero, and getting it right is the whole reason the
    graticule can be trusted: sample by the true radius, not by assuming the two agree.
    """
    # The card's corners sit further from the pole than R does, so the fetched box has to cover the
    # CORNER radius or the plate has bald corners.
    corner_px = math.hypot(W / 2, H / 2)
    half_m = (corner_px / R) * span_deg * 111_694.0 * 1.02      # metres at the card's far corner
    src = fetch_gibs(half_m)
    if src is None:
        return None
    S = src.size[0]

    # Reveal what the sensor recorded: mean 247, stdev 4.3 raw. autocontrast with a small cutoff pulls the
    # ice-surface structure across the range; the blur first stops MODIS's per-pixel noise being stretched
    # into confetti along with it.
    src = src.filter(ImageFilter.GaussianBlur(0.6))
    # preserve_tone, and it is not a nicety. autocontrast stretches each RGB channel INDEPENDENTLY by
    # default, so on a near-neutral subject the three channels get three different curves and the ice
    # comes out sepia. Antarctic snow is white going blue in the shadows; the first render of this card
    # was cream, which is a colour the plateau has never been. preserve_tone stretches luminance and
    # carries the hue through unchanged.
    # The cutoff is gentle (0.5%) on purpose: MODIS composites the pole from converging orbital swaths,
    # and their seams radiate from the centre. They are real, but a hard stretch turns them into a
    # starburst that reads as a rendering fault rather than as the sky's own geometry.
    src = ImageOps.autocontrast(src, cutoff=0.5, preserve_tone=True)
    sp = src.load()

    out = Image.new("RGB", (W, H))
    op = out.load()
    cx, cy = W / 2.0, H / 2.0
    for py in range(H):
        for px_ in range(W):
            dx = px_ - cx
            dy = py - cy
            r = math.hypot(dx, dy)
            # image y grows downward and this card puts lon 0 at the BOTTOM (x = sin, y = cos), so the
            # bearing is atan2(dx, dy) — and EPSG:3031 puts lon 0 at +y (up). Hence the y flip below.
            lon = math.degrees(math.atan2(dx, dy))
            colat = (r / R) * span_deg                      # equidistant: radius IS colatitude, linearly
            lat = colat - 90.0
            if lat > -87.0:
                lat = -87.0
            ex, ny = to3031(lat, lon)
            ix = int((ex + half_m) / (2 * half_m) * (S - 1))
            iy = int((half_m - ny) / (2 * half_m) * (S - 1))
            if 0 <= ix < S and 0 <= iy < S:
                op[px_, py] = sp[ix, iy]
    return out


def frame(trk):
    """This card's polar frame: (span, R, proj). ONE definition, deliberately.

    ⚠️ IT IS SHARED WITH THE SVG OVERLAY (`_gen_route_overlay.polar_overlay_svg`), which draws the
    route as vector on top of the basemap this file rasterises. If the overlay re-derived this maths
    it would be right only by AGREEMENT — and the day someone tuned `* 1.13` here, the vector line
    would silently slide off the ice while every check stayed green. Importing this function makes
    the two register BY CONSTRUCTION. It is the same reason the mercator overlay imports
    `_gen_satmaps.merc()` instead of reimplementing it.

    Frames the WALK, not the hemisphere: co-latitude of the far end + a small margin, so the route
    fills the card the way a satellite card's route does.
    """
    far = max(90.0 + la for _, la, _ in trk)
    span = far * 1.13
    R = min(W, H) * 0.5 - 26

    def proj(lat, lon):
        r = ((90.0 + lat) / span) * R
        a = math.radians(lon)
        return W / 2 + r * math.sin(a), H / 2 + r * math.cos(a)

    return span, R, proj


def main():
    trk, ms = route(), milestones()
    if len(trk) < 2:
        sys.exit("no route")

    # --no-route: basemap only. The route + pins ship as an inline SVG overlay instead, exactly as
    # every mercator card now does, so the pole's line is vector-crisp like the other forty rather
    # than a raster line softened by the card's 2.19x downscale. Without this flag the route is baked
    # AND overlaid — two lines. See _gen_satmaps.py, which carries the same flag for the same reason.
    draw_route = "--no-route" not in sys.argv[1:]

    span, R, proj = frame(trk)

    img = plate_from_imagery(span, R)
    real = img is not None
    if not real:
        # Degrade honestly rather than write a card that lies the other way.
        img = Image.new("RGB", (W, H), (9, 16, 26))
    dr = ImageDraw.Draw(img, "RGBA")

    # Ink that reads on ICE. Every other card draws its route on dark ground; this one is the only white
    # plate in the catalogue, so the graticule and labels take dark ink instead of light — same card
    # language, inverted for the only surface in the world it has to sit on.
    grid = (10, 20, 30, 70) if real else (255, 255, 255, 46)
    spoke = (10, 20, 30, 42) if real else (255, 255, 255, 22)
    label = (28, 44, 58) if real else (150, 175, 190)
    capink = (44, 60, 74) if real else (120, 145, 162)

    f = font(11)
    # graticule — a parallel every 0.25 deg is ~27.8 km, so the walk is measurable
    for colat in (0.25, 0.50, 0.75, 1.00):
        rr = (colat / span) * R
        if rr > R * 1.02:
            continue
        dr.ellipse([W / 2 - rr, H / 2 - rr, W / 2 + rr, H / 2 + rr], outline=grid, width=1)
        dr.text((W / 2 + 5, H / 2 - rr - 13), f"{90 - colat:g}°S", fill=label, font=f)
    for lon in range(0, 360, 30):
        a = math.radians(lon)
        dr.line([W / 2, H / 2, W / 2 + R * 1.02 * math.sin(a), H / 2 + R * 1.02 * math.cos(a)],
                fill=spoke, width=1)

    # The grid and the ice are the BASEMAP and always render. Only the route + pins are gated, because
    # only they have a vector twin in the overlay.
    if draw_route:
        pl = [proj(la, lo) for _, la, lo in trk]
        dr.line(pl, fill=CASING + (255,), width=8, joint="curve")
        dr.line(pl, fill=TRAIL + (255,), width=4, joint="curve")

        # pins by the app's own rule: the route point nearest the milestone's km
        for m in ms:
            if m.get("km") is None:
                continue
            p = min(trk, key=lambda q: abs(q[0] - m["km"]))
            x, y = proj(p[1], p[2])
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=TRAIL, outline=CASING, width=2)

        sx, sy = proj(trk[0][1], trk[0][2])      # start: amber, as on every card
        dr.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=AMBER, outline=CASING, width=2)
        fx, fy = proj(trk[-1][1], trk[-1][2])    # finish: white
        dr.ellipse([fx - 8, fy - 8, fx + 8, fy + 8], fill=(255, 255, 255), outline=CASING, width=2)

    # The Pole label needs a plate of its own now — dark ink on bright ice, at 12px, wants separation.
    dr.text((W / 2 + 13, H / 2 - 8), "90°S  the Pole", fill=(20, 34, 46) if real else (226, 238, 245),
            font=font(12))
    cap = ("Azimuthal equidistant projection - MODIS Terra true colour, NASA GIBS"
           if real else "Azimuthal equidistant projection - imagery unavailable, surface drawn")
    dr.text((14, H - 24), cap, fill=capink, font=f)

    out = os.path.join(IMGDIR, TID + ".webp")
    img.save(out, "WEBP", quality=90, method=6)
    print(f"  {TID}: polar card map built ({len(trk)} route pts, {len(ms)} pins, "
          f"framed to {span:.2f}° co-latitude, imagery={'NASA GIBS MODIS' if real else 'NONE (drawn)'}) -> {out}")


if __name__ == "__main__":
    main()
