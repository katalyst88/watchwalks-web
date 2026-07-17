# Web trailmap sharpness — 2026-07-17

Status: IN PROGRESS. Written as-I-go (session cap risk).

## Verified facts
- `img/trailmaps/*.webp`: 41 files, ALL 680x430 native, 2,328,002 B (2.22 MB). CONFIRMED.
- No `srcset` / `@2x` anywhere. CONFIRMED.

## ⚠️ THE BRIEF'S DIAGNOSIS IS WRONG — the images are NOT being upscaled
The brief says `width="680" height="430"` means 1:1 CSS px, so DPR2 stretches 680->1360.
**The HTML width attr is overridden by CSS.**

`styles.css:544`  `.tm { display:block; width:100%; height:auto; aspect-ratio:680/430; object-fit:cover; }`
`styles.css:510`  `.tgrid { grid-template-columns: repeat(auto-fill, minmax(300px,1fr)); gap:24px; }`
`styles.css:112`  `.wrap { max-width:1100px; padding:0 24px; }`  -> content 1052px

=> auto-fill picks 3 cols (3*300+2*24=948 <= 1052; 4 cols=1272 > 1052)
=> card width = (1052-48)/3 = **334.7 CSS px**

So on trails.html the map renders at ~335 CSS px:
- DPR 1 -> 680 native into 335 physical = **2x DOWNSCALE** (never upscaled)
- DPR 2 -> 680 native into 669 physical = **~1:1** (essentially exact)

**Therefore a 2x/srcset @2x is NOT the fix and would be near-pure waste** (DPR2 already ~1:1).

## ⚠️ SECOND BRIEF ERROR — `project()`/`decimate()` are NOT shared
The brief says the raster and `svg_for()` share projection, so the existing SVG fallback would register.
They use **two different map projections**:
- `_gen_trailmaps.py:99` `project()` = equirectangular, x=lng*cos(lat0), y=-lat, viewBox 300x190, pad-fit
- `_gen_satmaps.py:111` `merc()` = **Web Mercator**, tile-based, `pick_zoom()`, canvas centred on route
  centre, 680x430, ox=cx-W/2.
`svg_for()`'s output would NOT land on the baked line. Overlay must replicate `_gen_satmaps` mercator
maths at viewBox 0 0 680 430. (Also aspect differs: 300/190=1.5789 vs 680/430=1.5814.)

## Raster line geometry (from _gen_satmaps.build)
- white halo `width=7`, colour line `width=4`, drawn at 680 wide
- pins r=4.5 + 1.4 white ring
- At DPR1 those downscale to ~3.4px halo / ~2px line -> this is what reads soft.

## Next
- [ ] confirm rendered size + DPR behaviour in real Chrome (screenshot, don't trust arithmetic)
- [ ] check index.html hero img (line 75, no class) — may be the actual thing JD is looking at

## MEASURED IN A REAL BROWSER (puppeteer + Chrome, trails.html, 1440x1000)
```
{"dpr":1,"cssW":310.66,"cssH":196.44,"natW":680,"natH":430,"cols":"334.656px 334.672px 334.656px"}
{"dpr":2,"cssW":310.66,"cssH":196.44,"natW":680,"natH":430,"cols":"334.656px 334.672px 334.656px"}
```
Image renders at **310.66 CSS px** (card 334.66 minus padding). So:
- DPR1 -> 680 into 310.66 physical = **2.19x DOWNSCALE**
- DPR2 -> 680 into 621.3 physical = **1.09x DOWNSCALE**

**The image is NEVER upscaled at any common DPR. The brief's premise is refuted.**
=> **@2x / srcset is NOT the fix and would be near-pure waste** (DPR2 already has MORE pixels than
   it needs). Do not spend 2.3MB->5.8MB on it.

### Looked at the screenshots (Read tool), before_card_dpr1.png / before_card_dpr2.png
- DPR1: route is a faint, washed pinkish thread. The width-7 white casing dilutes the width-4
  colour line; downscaled 2.19x the casing dominates and the colour barely survives. **This is the
  "low res" JD is seeing.**
- DPR2: basemap is sharp (near 1:1) but the route reads as a lumpy beaded chain -- casing nearly as
  wide as the line + r=4.5 pins with a 1.4 white ring.
- **BASEMAP DOES NOT NEED 2x.** At both DPRs the terrain is downscaled and looks fine; photographic
  hillside downscales gracefully. Only the LINE is the problem. Confirmed by eye, not by theory.

## REGISTRATION PROOF -- overlay lands EXACTLY on the baked line
Weak first attempt (sampling raster "whiteness" at each vertex) gave 10-73% and looked like a
misregistration. **It was a bad test, not a bad projection**: the width-7 white casing is OVERDRAWN
by the width-4 colour line, so a vertex at the line's centre sits on COLOUR, not white. Recording it
because I nearly reported a false failure from it.

Real proof: monkeypatched `ImageDraw.line`/`ellipse` + stubbed `fetch_tile`/`Image.save` to capture
the EXACT polyline the real `_gen_satmaps.build()` draws, then compared vertex-for-vertex against
`_gen_route_overlay.project_px()`. No webp written, no tiles fetched, real code path.
```
alpamayo   pts=824    MAX VERTEX DELTA vs baked = 0.000000000 px
camino     pts=2228   MAX VERTEX DELTA vs baked = 0.000000000 px
shikoku    pts=5223   MAX VERTEX DELTA vs baked = 0.000000000 px
```
Registration is exact **by construction** (the overlay imports and reuses `_gen_satmaps`' own
`merc()`/`pick_zoom()` and repeats its centring), not by two scripts agreeing.

⚠️ This proves overlay == **fresh** bake. The SHIPPED rasters were baked from older data, so the
overlay must ship **with** the re-bake (Phase 2), never before it.

## Simplification error (RDP, eps=0.6, bounded not hoped)
| trail | full pts | kept | max dev (px @680) | svg bytes |
|---|---|---|---|---|
| inca-trail | 547 | 129 | 0.594 | 3,519 |
| alpamayo | 824 | 275 | 0.589 | 8,133 |
| camino | 2,228 | 80 | 0.597 | 4,504 |
| shikoku | 5,223 | 675 | 0.599 | 19,772 |
0.6px in the 680 frame = **0.27 CSS px** at the real 310.66px display size. Imperceptible.
(Brief guessed 1-2 KB/card; reality is 3.5-20 KB. Reported honestly below.)

## Other bugs found on the way
1. **`_gen_satmaps.py` CRASHES on `inca-trail`** -- the FREE trail and the site hero. It is in
   SampleData.kt (41 ids) but has **no `trails/inca-trail.json`** (its milestones live in
   SampleData.kt:1063). A full `python _gen_satmaps.py` run dies with FileNotFoundError.
   **Phase 2's bulk re-render will hit this.** Overlay generator made tolerant (route still drawn,
   pins skipped, `pin_src:"none"` flagged).
2. **`verify_web_parity.py` is ALREADY RED at baseline, before I touched anything** (exit 1,
   DRIFT 2): index.html total km not 28,460; inca-road card 600 km vs catalogue 810 km. That is the
   in-flight km-ladder work, not this change. It parsed 41 trails, so the <2-trail sanity floor did
   not trip. **The brief's "it must stay green" is not achievable -- it is not green now.**

## VISUAL PROOF (rendered in headless Chrome and LOOKED AT with the Read tool)
All in scratchpad `shots/`. Real `styles.css`, real `.tcard` markup, real measured 310.66px size.
- `reg_alpamayo.png` (DPR2, 680x430 native): overlay drawn as a 1.2px MAGENTA hairline over the
  SHIPPED baked raster -> the magenta sits centred inside the baked white casing for the whole route.
- `regzoom_alpamayo.png` (6x): at sub-pixel zoom the magenta tracks every wiggle of the baked line.
- `Z_before.png` / `Z_after.png` (6x, inca-trail): **before** = ragged, stair-stepped, speckled
  casing, blobby merged pins (downscaled lossy raster). **after** = clean continuous gold ribbon,
  smooth casing. Decisive.
- `X_before_dpr1.png` / `X_after_dpr1.png`: DPR1 card. After is a continuous ribbon; before is
  broken/noisy.
- `before_card_dpr2.png` (original trails.html) vs `A_after_alpamayo_dpr2.png`: before = lumpy
  beaded chain; after = clean ribbon with tight, distinct pins.

### A defect the screenshot caught that the code did not
First pass rendered every mid pin as a **white donut punched through the route**. The raster draws a
white disc at r+1.4 then the colour disc at r ON TOP (ring OUTSIDE); an SVG stroke is centred on the
radius, so it ate 1.4 INTO the pin -- and because a mid pin is the same colour as the line it sits
on, only the white ring was visible. Fixed with `paint-order: stroke`. **Reasoning said "same r,
same width, therefore identical"; the pixels said otherwise.**

## BYTES -- before/after, all 40 raster trails (south-pole excluded, see below)
| | bytes | MB |
|---|---|---|
| BEFORE: baked webp | 2,240,270 | 2.136 |
| AFTER: clean webp | 2,095,442 | 1.998 |
| AFTER: + inline SVG (gzipped) | 54,137 | 0.052 |
| **AFTER total** | **2,149,579** | **2.050** |
| **NET** | **+90,691 saved** | **-4.0%** |

**The fix is SMALLER, not bigger.** Removing the hard-edged line from the raster makes the webp
compress better (-144,828 B) by more than the gzipped SVG costs (+54,137 B). Only ONE trail is net
worse: john-muir-trail, by 452 bytes. Raw (ungzipped) it would be 24,785 B larger -- gzip is the
honest number since GitHub Pages always gzips HTML.
⚠️ `south-pole-last-degree` EXCLUDED: `_gen_satmaps.main()` deliberately skips the pole (mercator is
undefined there, no imagery exists), so my direct build() produced a 3 KB grey box and a fake 84 KB
"saving". **But an 87,732 B `south-pole-last-degree.webp` IS shipped and IS used** (the card falls
back to it because the file exists) -- a stale artifact from before that skip. Worth a look, separately.

## Answers to the brief's questions
- **Does the basemap also read soft / need 2x?** **NO.** Looked at it at both DPRs: terrain is fine
  (it is downscaled, never upscaled). A 2x set would cost ~2.5x of 2.1 MB for zero visible gain at
  DPR<=2. **Do not do it.** The line was the whole problem.
- **Can the overlay register?** Yes, exactly: 0.000000000 px, by construction.
- **Was the proposal right?** The *fix* was right; both stated *reasons* were wrong (it is a
  downscale not an upscale; the projections are not shared). It is right for better reasons than the
  brief gave, and it is a byte WIN rather than the predicted cost.

## What I changed (NOT deployed, NOT committed, NOT pushed)
1. **NEW `_gen_route_overlay.py`** -- emits the route+pins as inline SVG in the raster's exact
   680x430 mercator frame. Reuses `_gen_satmaps.merc()/pick_zoom()` so registration is structural.
   RDP simplification with a BOUNDED error (eps=0.6px @680 = 0.27 CSS px as displayed).
2. **`_gen_satmaps.py`** -- `build(..., route=False, out=...)` + `--no-route` flag = basemap only.
   Default behaviour unchanged. Missing-milestone-json no longer aborts the run.
3. **`_gen_trailmaps.py`** -- emits `<img class="tm">` + the overlay; **fixed the dead SP path**;
   guarded the missing json.
4. **`styles.css`** -- `.tm-wrap{position:relative}` + `.tm-route/.tm-casing/.tm-line/.tm-pins`.
   Colour from `var(--tc)`; start/finish keep BRAND s3 pine/gold (matches `_gen_satmaps.pin_color`).
   Line 5.5 / casing 9.5 viewBox units = ~2.5 / ~4.3 CSS px at the real display size.
   ⚠️ **Deliberate deviation, flag for JD:** the raster was 4/7 units = ~1.8/~3.2 CSS px. I went
   slightly heavier because a sub-2px line cannot read as crisp at any DPR. **Exact parity is 4/7 if
   JD prefers** -- one-line change.

## ⚠️ BUGS FOUND (all pre-existing; 3 block Phase 2)
1. **`_gen_trailmaps.py` WAS UNRUNNABLE** -- `SP` pointed at a DELETED session scratchpad
   (`%TEMP%/claude/.../ad05301a-.../scratchpad/story_pass`). **trails.html could not be regenerated
   at all.** `_gen_satmaps.py` carries a comment saying this exact bug was fixed -- it was fixed
   THERE ONLY, and the twin was left dead. `verify_web_parity.py` tells you to "re-run the
   generators" to clear drift; this one could not run. **FIXED -> `main()` now produces 41 cards.**
2. **`inca-trail` has no `trails/inca-trail.json`** -- the FREE trail, catalogue index 0, the site
   hero. Its milestones live in SampleData.kt:1063. Every web generator reads `trails/*.json`, so
   **a Phase 2 regen would silently ship the hero trail with 0 landmarks and NO pins** (its current
   shipped webp has pins baked from a json that has since been deleted). Generators now WARN loudly
   rather than crash. **NOT fixed: this is data, and the km-ladder agent is live in those files.**
   Fix is cheap -- pins need only km+type (placed by km -> nearest track point), and SampleData.kt
   has both; it has no lat/lng, but the overlay does not need any.
3. **`verify_web_parity.py` is RED at baseline and unchanged after my work** (exit 1, DRIFT 2:
   index.html total km; inca-road 600 vs 810 km). In-flight km-ladder work, not this change.
   **The brief's "it must stay green" was not achievable -- it was never green.**

## SEQUENCING -- do not ship half of this
The overlay only registers against a basemap built by `_gen_satmaps.py --no-route`. **Shipping the
CSS/HTML before re-rendering the rasters would draw BOTH lines** (old baked + new vector). The
registration proof is against a FRESH bake; the shipped webps are older. So:
**Phase 2, in one go:** `_gen_satmaps.py --no-route` (all 41) -> `_gen_trailmaps.py` -> verify -> ship.
Nothing here regenerates a shipped asset; every render went to a temp dir.

## ⛔ THE DEPLOY-BLOCKER I ALMOST SHIPPED INTO: `.gitignore` line 1 is `_*`
The repo ignores every underscore file and re-admits six generators by allowlist. **The new
`_gen_route_overlay.py` was not on it** -- it would have been silently never committed, and Phase 2's
clone would have died on ImportError with `_gen_trailmaps.py` unable to build a single card. The
gitignore's own comment warns about exactly this ("work that exists but is nowhere").

**And the same bug was ALREADY LIVE, unnoticed, for the module every generator imports.**
`_trail_colors.py` -- the ONE source of truth for trail colour, the fix for the four-hand-copied-
palettes drift -- starts with `_`, so it was eaten and never pushed. **PROVEN, not assumed:**
```
git archive origin/main | tar -x -C $TMP ; cd $TMP ; python -c "import _gen_satmaps"
  -> ModuleNotFoundError: No module named '_trail_colors'
```
**Every generator on the remote is dead on arrival.** The allowlist covered the entry points and
missed the import graph. `_gen_polarmap.py` (builds the South Pole card) was ignored the same way.
**FIXED:** `!_trail_colors.py`, `!_gen_polarmap.py`, `!_gen_route_overlay.py`. Secret-scanned first
(repo is PUBLIC): clean.
⚠️ Note the false positive I caught in my own test: `grep -c "_trail_colors.py"` returns 1 on
`origin/main` because **`_sync_trail_colors.py` contains that substring**. Use `grep -x`.

## ⛔ A BUG IN MY OWN INTEGRATION, caught by reading `_gen_polarmap.py`
`south-pole-last-degree`'s card is NOT mercator -- mercator is undefined at the poles, so that card
is built by `_gen_polarmap.py` with a POLAR projection. My first integration added the mercator
overlay to all 41 cards, which would have drawn a line belonging to no part of that image.
**FIXED:** `_gen_route_overlay.POLAR` skips it (in the module, so no future caller can forget); it
keeps its baked route. Verified: `_gen_trailmaps.main()` -> 41 cards, 41 basemaps, **40 overlays**.
This is also why the pole is excluded from the byte table above.

## FINAL STATE
- `_gen_trailmaps.main()` runs: **41 cards, 41 basemaps, 40 vector overlays**. (It could not run at all before.)
- `verify_web_parity.py`: **exit 1, DRIFT 2 -- byte-identical to baseline. Zero drift added.**
- **Nothing regenerated in `img/trailmaps/`. `trails.html` NOT rewritten. Nothing committed, nothing pushed.**
- Files touched: `.gitignore`, `_gen_satmaps.py`, `_gen_trailmaps.py`, `styles.css`,
  NEW `_gen_route_overlay.py`; now-visible `_trail_colors.py`, `_gen_polarmap.py`.
