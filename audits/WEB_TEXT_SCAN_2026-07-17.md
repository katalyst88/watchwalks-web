# Website text scan — trail-data claims vs SampleData.kt
Date: 2026-07-17. Scope: `watchwalks-web/` (READ-ONLY — JD mid-deploy; findings only, no edits).

Source of truth: `watchwalks-android/.../data/SampleData.kt` (41 trails).

## STATUS: in progress (written as I go — session caps have killed agents here)

---

## FINDING 0 (BLOCKER, found before any scanning) — `verify_web_parity.py` EXITS 2, NOT 1

JD's brief says "it is exit 1 at baseline (index.html total km + inca-road 600)". It is not.
Actual baseline run (`PYTHONIOENCODING=utf-8 python verify_web_parity.py`):

```
catalogue: 41 trails, 28,460 km, 1,117 landmarks  (SampleData.kt)
[1] trail count ......... (no fails)
[2] index.html headline .. FAIL total km (28,460)
[3] trails.html cards .... ABORT: found 0 trail cards ... It is NOT green — it is blind.
```

`check_cards()` hits its own SANITY FLOOR and calls `sys.exit(2)` immediately. Consequences:

- **The card regex `<article class="tcard" data-trail="...">` no longer matches the regenerated
  `trails.html`.** ~200 generated km/landmark claims are currently UNCHECKED by anything.
- **`check_brand()` (step 4) NEVER RUNS.** The "unlock" / "Dead Woman's Pass" ban is currently
  unenforced on every page. So is `check_generated_freshness()` (step 5).
- So "the parity checker is exit 1 on two known items" is itself a false result. Two whole checks
  are silently skipped. The sanity floor did its job — it refused to lie — but the exit code got
  read as the known-baseline failure.

Fix belongs to the generator/checker, not the HTML: re-point the card regex at whatever
`_gen_trailmaps.py` now emits. I re-implement cards + brand independently below so this scan is
not blind in the same place.

**Confirmed cause:** cards are still there (41 of them) but the attribute is gone. The markup is now
`<article class="tcard" style="--tc:#F4B04A">` — no `data-trail`. The checker requires
`<article class="tcard" data-trail="([^"]+)"`. Trail id is now only recoverable from the
`img/trailmaps/<id>.webp` src.

---

## CATALOGUE, VERIFIED INDEPENDENTLY (not taken on trust)

JD's numbers check out. Two independent parsers agree:

| | value | how confirmed |
|---|---|---|
| trails | **41** | my regex parse = 41; `awk` sum of a separate grep = 41 |
| total km | **28,460** | my parse = 28,460; independent `grep -oE ... \| awk '{s+=$1}'` = 28,460 |
| landmarks | **1,117** | `Milestone(` count inside brace-matched blocks |
| Africa | **7** | nile, atlas-traverse, kilimanjaro, mount-kenya, otter-trail, kilimanjaro-lemosho, gr-r2 |

inca-road = **810** in SampleData (was 600). appalachian 3536, pacific-crest 4265, manaslu-circuit 177,
tahoe-rim 265.

---

## MY CONTROLS (a scanner that matches nothing looks exactly like a clean site)

Seeded 6 defects into a **copy** of index.html + a multi-line HTML comment containing decoys.

| control | seeded | caught? |
|---|---|---|
| C1 km | `<b>999</b> km` (tag between number and unit — Trap 2) | ✅ flagged |
| C1 km | `Inca Road is 600 km` (stale total) | ✅ flagged |
| C2 words | unlock / Dead Woman's Pass / Dicks Pass / TODO / Lorem | ✅ all 5 |
| C3 counts | `36 trails`, `1,091 landmarks` | ✅ both |
| C4 delisted | `Fish River Canyon Trail` | ✅ |
| **NEGATIVE** | comment with `12345 km`, `99 trails`, `unlock`, `Dead Woman's Pass` | ✅ **correctly NOT reported** (Trap 1) |

Line numbers verified accurate (seeds at L35–39 reported as L35–39).

### ⚠️ My scanner FAILED ITS OWN FIRST CONTROL — and that is the point
The first control run reported `index.html L112: 28,250 km` and `L115: "36 trails" / "42 trails"`.
Those are **HTML comments** — the exact predecessor trap. Cause: I stripped comments **per-line**, so
every multi-line comment survived intact. A second bug: `strip_tags` collapsed multi-line tags and
**shifted every line number below them**, so my file:line citations would have been wrong.
Both fixed (strip whole-document, substitute newlines to preserve numbering) and re-controlled above.
**Had I skipped the control, this report would have opened with two false findings.**

---

## FINDINGS — TEXT

### `faq.html` — STALE TOTAL, AND IT SHIPS TO GOOGLE ⛔ highest impact

| line | says | catalogue | fixable |
|---|---|---|---|
| **38** | JSON-LD `"Forty-one, across all seven continents: **28,250 km** of route and 1,117 landmarks."` | **28,460 km** | HTML |
| **137** | prose `"Forty-one, across all seven continents: **28,250 kilometres** of route and 1,117 landmarks with a story."` | **28,460 km** | HTML |

L38 is inside `<script type="application/ld+json">` — this is the answer text Google ingests for the
FAQ rich result. **`verify_web_parity.py` cannot see this**: `check_headline_totals()` only ever opens
`index.html`. The JSON-LD is unchecked by anything, on any page.
(41 / 1,117 / "seven continents" are all CORRECT on both lines — only the km is stale.)

### `trails.html` L35 — the hand-written lead: banned word ×2 AND a stale count

```
Around three dozen of the world's great long walks, each a complete journey with its own route
and landmarks. Start free on the Inca Trail; unlock any other with a one-time purchase, yours to
keep. Each map below traces the real route, with a pin at every landmark whose story you unlock
as you walk.
```

1. **"unlock" ×2 — BANNED by the LOCKED BRAND.md.** Live right now on the trails page.
2. **"Around three dozen" = 36. The catalogue is 41.** This is the same stale count that cost a
   revision on 2026-07-16, just spelled in prose. **`check_trail_count()` cannot catch it** — it
   matches `\b(\d{2})\s+trails?\b` and a word-list of `thirty-six|forty-one|forty-two|thirty-nine`.
   "three dozen" is in neither. Suggest "Forty-one of the world's great long walks".
3. Both survive because `check_brand()` is step [4] and the run **dies at step [3]** (Finding 0).

### `attribution.html` — "Dicks Pass" ×2, banned by JD today

| line | text |
|---|---|
| 836 | `Dicks Pass — Joe Parks from Berkeley, CA, Wikimedia Commons, CC BY 2.0` |
| 1062 | `Dicks Pass — Rick McCharles, Wikipedia, CC BY 2.0` |

**Verified, not assumed** (I checked rather than guessing):
- It is a **real live milestone in two trails** — `tahoe-rim` @ 213.8 km and `pacific-crest`. Present in
  live `SampleData.kt` (4 hits), `trails/tahoe-rim.json`, `trails/pacific-crest.json`. **So it is inside
  the shipping app, not just the site.**
- It appears on the site **twice, in two sections**: under `Pct` (L836) and `Tahoerim` (L1062).
- **Not on `trails.html`** (0 hits) — pin labels don't carry it. attribution.html is the only page.
- ⚠️ A loose `grep "Dicks"` also hits `trails/torres-del-paine-w.json` — that is **`Lago Dickson`**, a
  different real place. **Not a violation.** My precise regex (`dick'?s\s+pass`) correctly excluded it;
  reporting it would have been a third false finding.

**THE FIX ALREADY HAS A PRECEDENT AND A MECHANISM — this is the actionable bit.**
`_gen_attribution.py` L53–66 carries JD's standing rule and a rename map:
```python
# JD's standing rule: "Dead Woman's Pass" never appears on a marketing surface — website, mockups, ...
    "Dead Woman's Pass": "Warmiwañusca",
```
That is exactly why Dead Woman's Pass is at **0 hits on every page while still living in the app** —
the app keeps the real name, the *marketing surface* renames it. `_gen_profiles.py` L35 honours the
same rule. **So Dicks Pass should get an entry in that same map + a regen — not a catalogue change and
not a hand edit.** I am not proposing the replacement string: unlike Warmiwañusca (the pass's genuine
Quechua name, which keeps the credit honest) Dicks Pass has no alternative real name I can source, and
inventing one would be fabricating geography. **JD's call.**

`check_brand()` has no "Dicks Pass" rule at all — it only bans `unlock` and `dead woman`. Worth adding
alongside the map entry, or the next regen silently puts it back.

### `index.html` L180–181 — the León caption is stale in TEXT **and** in PIXELS

| where | says | catalogue | fixable |
|---|---|---|---|
| L181 `<figcaption>` | "León cathedral, **447 km** along the Camino." | León = **468.4 km** | HTML |
| L180 `alt=` | "León, **447 km** along the Camino" | **468.4** | HTML |
| **`img/shot-story.webp`** | **burned in: "León · 447.1 km from start"** | **468.4** | ⛔ **RE-SHOOT** |

447 is not a rung anywhere in the Camino ladder. Nearest is Mansilla de las Mulas (448.9) — a
*different town*. Fixing the two HTML strings still leaves the picture contradicting them.

### `index.html` — trail totals that are all CORRECT (evidence the scanner works both ways)
L343–354 list 12 trails; **every km matches SampleData**: Inca 43, Camino 780, TMB 170, WHW 154,
Shikoku 1,200, Bibbulmun 1,000, Britain 1,745, Te Araroa 3,000, Appalachian 3,536, PCT 4,265,
Kungsleden 440, Nakasendo 530. L128 "4,265 km on the Pacific Crest, **the longest**" — correct, and
still the longest (PCT 4,265 > Route 66 3,940 > Appalachian 3,536).

---

## FINDINGS — IMAGES

**Only THREE non-trailmap images are live on the site**, all on index.html: `shot-story.webp`,
`shot-medals.webp`, `shot-journey.webp`. Verified by parsing `src`/`href`/`content` out of
comment-stripped HTML: **44 live image refs, 0 missing.**

⚠️ **Three "missing images" I nearly reported are FALSE** — `img/beta-banner.png`,
`img/garmin-banner.png`, `img/wearos-banner.png` are referenced **only inside HTML comments**
documenting their deliberate removal. My first pass grepped raw files and "found" 3 broken images.
**Trap 1 for the third time in one session.** Not defects.

### ⛔ ALL THREE LIVE SCREENSHOTS ARE STALE. All three need a re-shoot.

I opened every one (mtime is not evidence — all three are dated **2026-07-14**, recent, and all three
are wrong).

| image | shows | trail info | UI | verdict |
|---|---|---|---|---|
| `shot-story.webp` | Camino story card, León open | ❌ "León · **447.1 km** from start" (cat. **468.4**); spine "Frómista **343 km** in" (cat. **350.5**); "Carrión de los Condes **363 km** in" (cat. **370.0**) | ✅ current skin (Fraunces + cream/paper) | **RE-SHOOT** |
| `shot-medals.webp` | Medal wall, "Your collection" | ❌ **"12 of 36 trails conquered"** and **"Trail Medals — 12 of 36"** burned in. **Catalogue is 41.** | ❌ **4-tab bar** | **RE-SHOOT** |
| `shot-journey.webp` | Camino journey screen, day 79 | ❌ "**4.4 km** to Hospital de Órbigo" at 470 km — catalogue puts Órbigo at **500.2 km**, i.e. **30.2 km** away. (470/780 = 60.3% ✓ internally consistent, so it is the *ladder* that moved, not the arithmetic.) | ❌ **4-tab bar** | **RE-SHOOT** |

**`shot-medals.webp` is the worst of the three.** "12 of 36 trails conquered" is the *exact* stale
count that cost a revision on 2026-07-16 — it was fixed in the HTML tiles and **left burned into the
picture directly below them**. index.html now says 41 trails in text while the screenshot beside it
says 36. No text checker can ever see this.

**The 4-tab bar is outdated UI — verified against the app, not assumed:**
`ui/WatchWalksApp.kt:794` → `val labels = listOf("Journey", "Medals", "Explore")` — **three** tabs.
Both shots show **four**: Journey / Medals / Explore / **Settings**. The Settings tab no longer exists.
(Good news: the labels read **"Medals"**, not "Badges", and the skin is the current Fraunces/cream —
so these post-date the rebrand and the Badges→Medals rename. The rot is the tab bar + the numbers.
Note `WatchWalksApp.kt:790` still *comments* "a rosette for Badges" — stale comment, code is right.)

**The Camino ladder moved and nobody re-shot the Camino.** All three shots are Camino/medal screens
and all three disagree with the current camino ladder. JD's brief lists the rebuilt ladders as
appalachian / pacific-crest / manaslu-circuit / tahoe-rim — **camino is not on that list, but the
evidence says its rungs moved too** (León 447.1→468.4, Frómista 343→350.5, Carrión 363→370.0,
Órbigo ~474→500.2). Worth confirming why before re-shooting, or the new shots go stale again.

### CLEAN images (with the evidence that would have failed them)

| image | verdict | evidence it could have failed |
|---|---|---|
| `img/og-cover.png` (Jul 12) — the `og:image` on index + faq, i.e. **every shared link** | ✅ **CLEAN** | Opened it. Current skin (Fraunces + cream/paper, pine accent). Carries **no trail count, no km, no landmark count** — nothing that today's data change could invalidate. Copy is "Walk the world's greatest trails / Your everyday steps carry you down the Inca Trail. Free to start, no account, no GPS." Inca Trail **is** still free (`free = true`, index 0). No banned words. Domain badge reads `watchwalks.com` = matches CNAME. |
| `img/trailmaps/*.webp` (41) | ✅ present, ⚠️ pin accuracy not judged | All 41 referenced, 0 missing. Pin positions are a **km-scale** question (`audit_track_fit.py`), out of scope for a text scan and JD has just regenerated them. |

### ⛔ THE PLAY STORE LISTING SOURCE IS PRE-REBRAND — confirmed by opening the files

`playstore/render_shots.js` composites the Play listing **from `watchwalks-web/img/companion-*.png`**
(L35–56). Those files are dated **2026-06-19** and are **orphaned on the website itself** (0 live refs —
so this does NOT affect the site, only the storefront). I opened them:

**`companion-home.png`** — every failure mode at once:
- ❌ **Old skin**: Nunito rounded sans + **brand green** background. Current is Fraunces + cream/paper.
- ❌ **"Badges"** tab label (now **"Medals"**).
- ❌ **Miles**: "11 mi to Machu Picchu" — the site talks km throughout.
- ❌ Old app icon, old green gradient card, old progress-ring design.
- ❌ **A "Preview — Showing sample data" banner is being used as marketing.** That is a debug/preview
  state on a storefront screenshot.

**`companion-badges.png`** — worse:
- ❌ Headline **"Collect a badge for every trail"** — the whole page is built on the retired "badge" noun.
- ❌ **"2 of 11 trails conquered"** — the catalogue is **41**. This is the "undersells 41 trails as 11"
  problem, at its source.
- ❌ **Miles throughout** (1234 mi walked, 27 / 2197 / 2650 / 2448 / 1084 / 746 / 932 mi).
- ❌ **Inca Road "373 mi" = 600 km — TODAY'S stale number.** Current is **810 km (503 mi)**. Every other
  total converts correctly (2197 mi = 3536 km ✓, 2650 mi = 4265 km ✓, 1084 mi = 1745 km ✓,
  746 mi = 1200 km ✓, 932 mi = 1500 km ✓, 2448 mi = 3940 km ✓, 27 mi = 43 km ✓) — **inca-road is the
  only trail total that is wrong**, which is precisely the trail that moved today.
- ❌ **Badge art is a different design entirely**: flat grey/gold discs. Current medals are die-cut
  hexagon/shield/star shapes on ribbons, struck in bronze/silver/gold with prestige tiers
  (Trailhead/Wayfarer). Unearned state is a grey disc; current is a locked "Finish to earn" medal.

**Consequence, stated plainly: the Play listing cannot be refreshed from these files.** Re-running
`render_shots.js` today would republish the June app: green, Nunito, "Badges", miles, and an 11-trail
catalogue. **The `companion-*.png` set must be re-shot from the current app before the storefront is
touched.** (`apple-*.webp`, Jul 4, are likewise orphaned on the site — not audited here as they are
outside `watchwalks-web`'s live surface, but they are 11 days older than the current UI and the
coordinator reports the Apple set is already known-stale on 4 tabs / "Badges".)

---

## THE FULL DEFECT TABLE

| # | file:line | says | catalogue / truth | fix |
|---|---|---|---|---|
| 1 | `faq.html:38` (JSON-LD) | `28,250 km` | **28,460** | HTML — **ships to Google** |
| 2 | `faq.html:137` | `28,250 kilometres` | **28,460** | HTML |
| 3 | `trails.html:35` | "unlock" ×2 | BANNED (BRAND.md) | HTML (hand-typed lead) |
| 4 | `trails.html:35` | "Around three dozen" (=36) | **41** | HTML |
| 5 | `attribution.html:836` | "Dicks Pass" (Pct) | BANNED today | `_gen_attribution.py` rename map + regen |
| 6 | `attribution.html:1062` | "Dicks Pass" (Tahoerim) | BANNED today | same |
| 7 | `index.html:181` figcaption | "León cathedral, **447 km**" | **468.4** | HTML |
| 8 | `index.html:180` alt | "León, **447 km**" | **468.4** | HTML |
| 9 | **`img/shot-story.webp`** | León **447.1**, Frómista **343**, Carrión **363** | 468.4 / 350.5 / 370.0 | ⛔ **RE-SHOOT** |
| 10 | **`img/shot-medals.webp`** | **"12 of 36 trails conquered"** ×2 | **41** | ⛔ **RE-SHOOT** |
| 11 | **`img/shot-medals.webp`** | 4-tab bar (+Settings) | 3 tabs | ⛔ **RE-SHOOT** |
| 12 | **`img/shot-journey.webp`** | "4.4 km to Hospital de Órbigo" @470 | Órbigo @ **500.2** (30.2 km away) | ⛔ **RE-SHOOT** |
| 13 | **`img/shot-journey.webp`** | 4-tab bar (+Settings) | 3 tabs | ⛔ **RE-SHOOT** |
| 14 | **`verify_web_parity.py`** | `check_cards` regex needs `data-trail` | markup is now `style="--tc:"` | **exit 2 — checks [3][4][5] never run** |
| 15 | *(storefront, not site)* `img/companion-*.png` | pre-rebrand: green/Nunito, "Badges", miles, **11 trails**, Inca Road **600 km**, old badge art, "Preview/sample data" banner | 41 trails, 810 km, Fraunces/cream, Medals | ⛔ **RE-SHOOT before any Play listing refresh** |

**Note on #1/#2:** JD said index.html's total km is a known baseline failure being fixed now. **faq.html
is a different file and is NOT covered by the checker** (`check_headline_totals` opens index.html only)
— these two will survive the fix unless done deliberately. The JSON-LD one is the highest-impact text
defect on the site.

---

## PAGES THAT ARE CLEAN — and the evidence they could have failed

My scanner has proven teeth (see controls: it caught seeded 999 km behind a `<b>` tag, a seeded stale
600, 36 trails, 1,091 landmarks, 5 banned words and a de-listed trail). These pages were run through
the **same** scanner and came back clean:

| page | evidence it could have failed |
|---|---|
| `index.html` (**except** #7/#8) | 27 km-claims parsed. **All 12 trail totals at L343–354 match SampleData exactly** (Inca 43 … PCT 4,265). Inca strip verified rung-by-rung: "12 landmarks" = 12 ✓, "0 km" = KM82 ✓, "26 km in" = Runkurakay @26.0 ✓, "41 km in" = Sun Gate @41.0 ✓, "43 km"/Machu Picchu @43.0 ✓. "4,265 km on the PCT, **the longest**" ✓ (4,265 > 3,940 > 3,536). "Forty-one trails … seven continents" ✓. |
| `trails.html` (**except** #3/#4) | **All 41 generated cards re-checked independently** (I rebuilt the check the aborting one can't run): 41 km values + landmark counts, **41/41 agree**, 0 missing, incl. **inca-road = 810** ✓. The regenerated content is sound; only the hand-typed lead rotted. |
| `attribution.html` (**except** #5/#6) | Claims **919 photos across 41 trails**. Verified: 919 `<li>` rows across exactly 41 sections, and the per-section sum = 919 ✓. (Raw `<li><b>` = 924; the 5 extras are the map/satellite/elevation/typeface rows, not photos — **not** a discrepancy. An earlier naive split of mine "found" a Wonderland 15-vs-16 mismatch; proper `<details>` matching shows **no** mismatch. False positive, discarded.) Fonts row names **Fraunces + Hanken Grotesk** = current brand ✓. |
| `coming-soon.html`, `compatibility.html`, `contact.html`, `privacy.html`, `terms.html`, `thanks.html`, `join-{apple,garmin,wearos}.html`, `setup-{apple,garmin,wearos}.html` | All carry the "All 41 trails" footer link — **41 ✓ on every one**. No km claims, no stale counts, no banned words. |
| `_og.html` + all `<meta>`/`og:`/`twitter:` | og:image + twitter:image resolve to `og-cover.png` which exists and is clean. **13 URL refs, all `watchwalks.com`**, matching `CNAME` + `sitemap.xml` — no domain drift. |

**"coming soon" is NOT flagged as a defect.** It appears on index.html (L470/475) and the join pages
for Apple/Wear OS. Per `project_watchwalks_launch_state`, those stores are genuinely not public yet, so
the copy is **true**. Flagging it would have been a false finding.

**Also clean, verified rather than assumed:**
- **No de-listed African trail** (Fish River etc.) appears anywhere. Africa = **7** trails ✓.
- **"Dead Woman's Pass": 0 hits on every page** ✓ — it *is* in the live catalogue (inca-trail @19 km)
  but `_gen_attribution.py`'s rename map keeps it off the marketing surface. The rule works.
- `index.html:157` "**4,206 m** high point" vs the app story's "4,215 m" is **NOT a defect** — L162–163
  discloses it in the open: *"we read the highest pass at 4,206 m against a published 4,215 m."*
  The site is being honest about its own measurement. Reporting it would have been a false finding.
- "Pennine Way" / "Queen Charlotte Track" on attribution.html are **real milestone names** in the
  catalogue (Length of Britain / Te Araroa), not de-listed trails. False positives, discarded.
- `Lago Dickson` (torres-del-paine) is **not** a "Dicks Pass" hit. False positive, discarded.
- **0 broken image refs** (44 live refs). The 3 "missing" banners live only in comments.
- No lorem / TODO / XXX / FIXME / placeholder / TBD in any rendered text.

---

## SUMMARY

- **13 real defects on the site** (4 HTML text, 2 generator, 5 burned-in pixels across all 3 shots,
  + the checker itself), **1 storefront blocker**.
- **The generated content is fine. The hand-typed content and the pictures are where the rot is** —
  exactly as JD predicted, plus the images, which no checker can see.
- **Every live screenshot on the site is stale.** The most prominent is `shot-medals.webp` saying
  **36 trails** directly beneath HTML tiles that say 41.
- **4 false findings were caught and discarded before reaching this report** (3 comment-artefacts, the
  Wonderland row-count, plus Lago Dickson / Pennine Way / 4,206 m). My own scanner produced two of
  them and was fixed. The controls are what made the difference.

