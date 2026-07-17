#!/usr/bin/env python3
# Emit the trail ROUTE + PINS as an inline SVG overlay that registers pixel-exactly on top of the
# satellite basemap raster (img/trailmaps/<id>.webp).
#
# WHY THIS EXISTS
# ---------------
# The route used to be BAKED INTO the .webp (see _gen_satmaps.build). Two costs:
#   1. SHARPNESS. The raster is 680x430 but the card renders it at ~311 CSS px (measured), so at
#      DPR1 the browser DOWNSCALES it 2.19x. A 4px hard-edged line inside a 7px white casing
#      survives that badly -- it thins to ~1.8px, the casing dilutes the colour, and WebP q82
#      ringing on a hard edge over noisy terrain finishes the job. Photographic hillside downscales
#      gracefully; a thin high-contrast line does not. THIS IS A DOWNSCALE PROBLEM, NOT AN UPSCALE
#      ONE -- the image is never upscaled on this page at any common DPR, so a 2x/@2x srcset would
#      not fix it (see audits/WEB_TRAILMAP_SHARPNESS_2026-07-17.md).
#   2. A STALE PALETTE, PERMANENTLY. _gen_satmaps reads colours live from _trail_colors, but the
#      shipped pixels were baked by an older run -- so the colour on disk can silently disagree with
#      the app and the only fix is a 41-image re-render. In SVG the colour comes from the DOM
#      (`var(--tc)`, already on .tcard), so it can never go stale again.
#
# REGISTRATION IS THE WHOLE JOB.
# _gen_trailmaps.svg_for() does NOT register -- it uses an equirectangular projection (x=lng*cos
# (lat0)) into a 300x190 viewBox, while the raster is WEB MERCATOR, tile-based, 680x430, centred on
# the route centre. Two different projections. This module therefore imports and reuses
# _gen_satmaps' OWN merc()/pick_zoom() and repeats its exact centring maths, so the overlay is
# correct BY CONSTRUCTION rather than by agreement.
import os, sys, json, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _gen_satmaps import merc, pick_zoom, load_track, SP, PIN_START, PIN_FINISH
from _trail_colors import C1

W, H, PAD = 680, 430, 0.10

# south-pole-last-degree's card is NOT a mercator basemap. Mercator is undefined at the poles (merc()
# clamps at |lat| 85.05 and the last degree runs -89 to -90), so that card is built by
# _gen_polarmap.py with a purpose-built POLAR projection. A mercator overlay would draw a line that
# belongs to no part of that image. It keeps its baked route until _gen_polarmap grows its own
# overlay. Excluding it here rather than in the caller so no future caller can forget.
POLAR = {"south-pole-last-degree"}


def project_px(track):
    """The EXACT projection _gen_satmaps.build() uses. Any change here must mirror it."""
    z = pick_zoom(track, W, H, PAD)
    xs = [merc(la, lo, z)[0] for _, la, lo in track]
    ys = [merc(la, lo, z)[1] for _, la, lo in track]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    ox, oy = cx - W / 2, cy - H / 2
    return [(x - ox, y - oy) for x, y in zip(xs, ys)], z, ox, oy


def rdp(pts, eps):
    """Ramer-Douglas-Peucker. Unlike the index-stride decimate() in _gen_trailmaps, this bounds the
    geometric error: no point of the original is ever further than `eps` px from the kept line, so
    the simplification can be stated as a number instead of hoped about."""
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        ax, ay = pts[i]; bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        den = math.hypot(dx, dy)
        best, bi = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if den == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / den
            if d > best:
                best, bi = d, k
        if best > eps:
            keep[bi] = True
            stack.append((i, bi)); stack.append((bi, j))
    return [p for p, k in zip(pts, keep) if k]


def max_deviation(orig, simp):
    """Worst distance from any original point to the simplified polyline (px in the 680x430 frame)."""
    def seg_d(p, a, b):
        px, py = p; ax, ay = a; bx, by = b
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))
    worst = 0.0
    for p in orig:
        worst = max(worst, min(seg_d(p, simp[i], simp[i + 1]) for i in range(len(simp) - 1)))
    return worst


def polar_overlay_svg(tid, eps=0.6, cls="tm-route tm-ice"):
    """The pole's vector route, in the pole's OWN projection.

    JD: "We need south pole to look the same even if it's created differently." It was the one card
    left with a BAKED route while the other forty had gone vector — so it alone would have sat there
    soft and stale, in a grid designed to be scanned side by side. Created differently, yes; it must
    not LOOK different.

    ⚠️ REGISTRATION IS THE WHOLE JOB, and mercator maths would put this line on open ocean. So we
    import `_gen_polarmap`'s OWN `route()`, `milestones()` and `frame()` rather than reimplementing
    any of them: the overlay and the raster then share one definition of where a point lands, and
    cannot drift apart the way a copied constant silently would.

    ⚠️ THE CASING FLIPS. Every other card draws a white casing on dark satellite; this is the only
    card on WHITE ICE, where white is invisible. The raster solved that with a dark casing
    (12,22,34) — the CSS class `tm-ice` does the same for the vector. The LINE colour needs nothing:
    the pole's --tc is already #BDD3DB, which is exactly the raster's TRAIL colour.
    """
    from _gen_polarmap import route as p_route, milestones as p_ms, frame as p_frame, W as PW, H as PH
    trk = p_route()
    if len(trk) < 2:
        return "", {"error": "polar route has %d points" % len(trk)}
    span, R, proj = p_frame(trk)

    pl = [proj(la, lo) for _, la, lo in trk]
    simp = rdp(pl, eps)
    dev = max_deviation(pl, simp)
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in simp)

    # ⚠️ PIN RULE COPIED EXACTLY FROM THE MERCATOR BRANCH ABOVE — same loop, same class derivation
    # (start/finish come from the milestone's TYPE, not from being first/last in the track), same
    # r=4.5. My first version drew mid pins for everything and then ADDED start/finish circles at
    # r=7: it double-painted the two end milestones and made the pole's pins visibly fatter than the
    # other forty. "Looks the same" is the whole requirement, so the rule has to be the same rule.
    pins, ms = [], p_ms()
    for m in ms:
        if m.get("km") is None:
            continue
        p = min(trk, key=lambda q: abs(q[0] - m["km"]))       # the app's own rule, as the raster uses
        px, py = proj(p[1], p[2])
        t = m.get("type")
        k = "start" if t == "start" else "finish" if t == "finish" else "mid"
        pins.append(f'<circle class="p-{k}" cx="{px:.1f}" cy="{py:.1f}" r="4.5"/>')

    svg = (
        f'<svg class="{cls}" viewBox="0 0 {PW} {PH}" preserveAspectRatio="none" aria-hidden="true" '
        f'focusable="false">'
        f'<path class="tm-casing" d="{d}"/>'
        f'<path class="tm-line" d="{d}"/>'
        f'<g class="tm-pins">{"".join(pins)}</g>'
        f'</svg>'
    )
    return svg, {"projection": "polar (shared frame() with _gen_polarmap)", "pts_full": len(pl),
                 "pts_kept": len(simp), "max_dev_px": round(dev, 3), "bytes": len(svg.encode()),
                 "pins": len(pins), "pin_src": "trails/%s.json" % tid}


def overlay_svg(tid, eps=0.6, cls="tm-route"):
    """Inline SVG for one trail. Colour comes from --tc (the DOM), never baked."""
    if tid in POLAR:
        # NOT skipped any more — the pole gets a vector route too, in its own projection.
        return polar_overlay_svg(tid, eps=eps)
    track = load_track(tid)
    if len(track) < 2:
        return "", {}
    proj, z, ox, oy = project_px(track)
    simp = rdp(proj, eps)
    dev = max_deviation(proj, simp)
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in simp)

    # Milestones are OPTIONAL. inca-trail -- the free trail and the hero of the site -- has NO
    # trails/inca-trail.json (its milestones live in SampleData.kt:1063 instead), which is why
    # `_gen_satmaps.py` CRASHES on it today. See the audit. Missing pins must not cost us the route.
    mpath = os.path.join(SP, tid + ".json")
    pins, pin_src = [], "none"
    if os.path.exists(mpath):
        pin_src = "trails/%s.json" % tid
        for m in json.load(open(mpath, encoding="utf-8"))["milestones"]:
            j = min(range(len(track)), key=lambda i: abs(track[i][0] - m["km"]))
            px, py = proj[j]
            t = m.get("type")
            k = "start" if t == "start" else "finish" if t == "finish" else "mid"
            pins.append(f'<circle class="p-{k}" cx="{px:.1f}" cy="{py:.1f}" r="4.5"/>')

    svg = (
        f'<svg class="{cls}" viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true" '
        f'focusable="false">'
        f'<path class="tm-casing" d="{d}"/>'
        f'<path class="tm-line" d="{d}"/>'
        f'<g class="tm-pins">{"".join(pins)}</g>'
        f'</svg>'
    )
    return svg, {"pts_full": len(proj), "pts_kept": len(simp), "max_dev_px": round(dev, 3),
                 "zoom": z, "bytes": len(svg.encode()), "pins": len(pins), "pin_src": pin_src}


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "inca-trail"
    svg, meta = overlay_svg(tid)
    print(json.dumps(meta, indent=2))
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_overlay_%s.svg" % tid), "w", encoding="utf-8").write(svg)
