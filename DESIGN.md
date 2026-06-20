# Watch Walks — Design System ("Field Journal")

The single source of truth for the look & feel of the **website and companion app** (the Garmin /
Wear OS watch apps are out of scope). Read this before touching any UI. The goal: **premium,
warm, editorial, and unmistakably *not* AI-generated.**

## Direction
A beautifully made **field journal you collect stamps in** — the calm and reward of a long walk.
Headspace-calm meets editorial outdoor. It is *ours* because it leans on what the product already
is: trails, terrain, postcards, milestones. Tactile, paper-like, with topographic motifs.

## Anti-slop ban list (never ship these)
- ❌ Inter / Roboto / system-ui / Arial as the brand face. ❌ purple/indigo "blurple" gradients.
- ❌ uniform rows of identical rounded-rect cards with the same radius + soft shadow.
- ❌ everything centered with even, predictable spacing. ❌ emoji or stock Material icons as the icon set.
- ❌ flat slate-gray palettes, pure #fff / #000. ❌ the "pill button + 3 feature cards + testimonial" template.

## Type
- **Display — Fraunces** (variable, optical). Headlines, eyebrows, numerals, trail names. Use real
  weight (600–700) and let large sizes breathe. Optical size scales with font size. Warm, characterful.
- **Text — Hanken Grotesk** (variable). Body, UI, labels. 400 body / 500–600 emphasis.
- Self-hosted (`fonts/fraunces-var.woff2`, `fonts/hanken-var.woff2`) — no Google CDN (privacy brand).
- Scale (web, fluid): display clamp(40px,6vw,76px)/1.02; h2 clamp(28px,3.6vw,42px); lead 19–21px;
  body 16–17px; small 13–14px. Tight letter-spacing on display (−0.02em), normal on text.
- App (Compose): bundle the same two fonts in `res/font`; map to a custom Typography.

## Colour (warm, earthy — keep the green+gold equity)
Light ("paper"):
- `--paper` #F4EDDF (warm cream base) · `--paper-2` #FBF6EC (raised) · `--ink` #23211C (near-black text)
- `--pine` #1F5C3D (deep forest green, primary) · `--pine-deep` #143E29 · `--moss` #2E8B57
- `--gold` #E0A52E (accent / achievement) · `--clay` #B4623B (secondary warm) · `--line` #E2D6BF (hairlines)
- `--subtle` #7A6F5C (muted brown-grey text)
Dark ("dusk"): `--paper` #14160F · `--paper-2` #1C2016 · `--ink` #F3EFE2 · `--pine` #3FB477 ·
`--gold` #E9B450 · `--clay` #CC7A52 · `--line` #2A2C1F · `--subtle` #A7A08C.
No pure white/black; no slate/blue-gray.

## Texture & motif (the ownable signature)
- **Paper grain**: a subtle tiling noise over backgrounds (very low opacity).
- **Topographic contour lines**: thin pine/gold contour rings as section dividers, card frames,
  background flourishes, and behind the hero. This is the recurring brand mark.
- **Hillshade terrain**: reuse the map's warm hillshade as a texture in heroes/footers.
- **Imagery**: real trail photography graded to a warm duotone (paper shadows / pine or gold lights).
  Until licensed photography exists, lean on contour + hillshade + the watch render + illustrated trail art.

## Shape, space, depth
- Radius: 14px (controls/cards), 22px (large panels/postcards), 999px (pills). Not everything rounded.
- Spacing rhythm 4px base but with *intentional* large steps (8/14/22/36/64) — vary it, create tension.
- Elevation: soft, warm shadows (rgba(40,30,15,.14)) + 1px `--line` border. Sparingly.
- Layout: **editorial** — asymmetry, varied section rhythm, big type, off-grid moments, full-bleed terrain.
  Avoid the symmetric card grid; alternate left/right, mix sizes.

## Components with personality (recipes, not just tokens)
- **Button**: pine→pine-deep vertical gradient, Hanken 600, radius 999, `--paper` text; ghost = 1px line.
- **Eyebrow**: Fraunces 600, gold, letter-spacing .08em, small caps feel.
- **Postcard (milestone)**: paper-2 card, 22px radius, a torn-edge/stamp corner, contour watermark,
  Fraunces name in pine, Hanken story, a small gold "stamp" when reached.
- **Progress ring**: engraved feel — pine track on paper, gold/pine indicator, Fraunces numeral center.
- **Map**: framed "window" — inset border, soft inner shadow, rounded 22.
- **Badges**: a wall of enamel-pin / wax-stamp discs (not flat circles).
- **Icons**: ONE custom single-stroke line set (1.75px), pine/ink. No emoji, no Material.

## Motion
Restrained, organic: 180–260ms, ease-out with a touch of overshoot. Scroll-reveals on web (fade+rise
8–16px). Elevate existing celebration moments. Respect `prefers-reduced-motion`.

## Process (how we avoid slop)
Component-first (perfect one, lock it, then scale) · reference-driven (Headspace warmth, a field-journal/
outdoor editorial site, one personality ref) · screenshot-iterate every step · this file is authoritative.
