# Watch Walks website — review & overhaul plan (2026-06-29)

Black-box conversion assessment + accuracy/theme review, after the big app update (every trail now an
on-demand purchasable PAD with satellite maps, Purchase→Install→Uninstall, 1 km/day target, cloud
backup). Measured against the shipped app reality, `BRAND.md` (locked), and conversion best practice.

## TL;DR
- **Theme consistency is already there.** `styles.css` tokens === the app's `Color.kt`/`Type.kt`
  (cream `#F4EDDF`, ink `#23211C`, pine `#1F5C3D`, gold `#E0A52E`, clay `#B4623B`, dusk dark mode;
  Fraunces + Hanken). The *only* visual-consistency gap is **stale screenshots** showing the old app.
- **The site is materially OUT OF DATE and in places now INACCURATE.** It still says one trail is live
  and nine are "Soon", never mentions satellite maps, doesn't reflect buying trails, and makes privacy
  claims that the new cloud-backup + Play Billing make **no longer strictly true** (a trust + legal risk).
- **Conversion is good but undersells a now-complete product.** Fixing the above is the biggest lever.

---

## A. ACCURACY — the site contradicts the shipped app (highest priority)

1. **Trails: 9 of 11 shown as "Soon" — they're all live now.** (`index.html:142-151`) All 10 paid trails
   exist as purchasable on-demand packs with satellite maps and live Play prices (e.g. Camino AUD 2.99).
   Showing them "Soon" reads as unfinished and **caps conversion to the one free trail**. → Show every
   trail as walkable, each with its **price** (Inca free, others from ~$1.49), linking to purchase.

2. **Satellite maps — the headline new feature — is missing entirely.** The map copy says "live route
   map" only. Real Sentinel-2 satellite imagery for every trail is a major differentiator and very
   visual. → New benefit + fresh map screenshots (satellite + route + pins).

3. **The purchase model isn't represented.** Komoot-style: free Inca, buy any trail once, install its
   offline pack, walk. No prices, no "buy once, yours forever", no Install/Uninstall story. → Add a
   short "How trails work" + pricing; this is table-stakes for a paid app's site.

4. **🔴 Privacy claims are now OVER-CLAIMED (fix first — trust + legal).** The privacy band asserts
   *"No accounts · No servers · No tracking · Your data never leaves your devices."* (`index.html:115-134`)
   The app now has **optional Google sign-in + Firebase/Firestore cloud backup** ("buy once, sync
   everywhere"), **Google Play Billing** purchases, and **Play Asset Delivery** downloads. "No servers /
   no accounts / never leaves your devices" is no longer accurate. → Reframe honestly and *still
   strongly*: "Private by default. No tracking, no ads, no profiling. Walk with no account at all — or
   turn on optional Google backup to sync purchases across devices. Purchases are handled by Google
   Play." Keep privacy as a strength without a false absolute.

5. **iPhone "to follow"** — iOS is scaffolded but not shipped; keep as "coming", don't imply available.

6. **Beta vs launch framing.** Site is beta-first ("Join the beta", store buttons `hidden`). The app is
   now feature-complete and purchasable. **Decision needed (JD):** flip to launch (reveal store buttons,
   show prices) or stay beta. Most of the value of this overhaul lands only if we flip to launch.

7. **Direct APK link** (`index.html:191`, raw.githubusercontent .apk) hurts trust and bypasses Play
   safety/updates. → Point to Google Play once public; drop the raw-APK CTA.

## B. SCREENSHOTS / VIDEO (BRAND.md hard rule: real device mockups everywhere)

Current shots predate satellite maps + the current journey UI. Replace with fresh real-device captures:
- Phone journey card with the **satellite map**, route, flag, milestone pins, 1-decimal distance.
- The **trail catalog** showing trails with prices + Purchase/Install/Uninstall.
- A **finisher badge** wall (keep) — re-shoot at current styling.
- Watch: Garmin + Wear progress ring + a landmark story (re-shoot current builds).
- Hero/`app-demo` video: re-capture to show the satellite map + buying/installing a trail.
- Keep the warm duotone grading + device frames per BRAND.md.

## C. CONVERSION (black-box, first-time visitor)

Strong: clear benefit-first hero + video, scannable 3-step, privacy as trust, repeated CTA, good IA.
Gaps that cost signups/sales:
- **No pricing visible** anywhere — a paid app must answer "what does it cost?" above the fold-ish.
- **Trails undersold** ("Soon") — fixing A1 is the single biggest conversion win.
- **No proof** — no ratings/testimonials/"as seen on". Add when available; for now a "made by a walker"
  founder note fits the brand.
- **One hero video, one CTA path.** Add a secondary low-friction CTA ("See the trails") and ensure the
  store/price CTA is reachable without scrolling to the bottom.
- **Benefit ladder** is feature-listy in places (the `feat` list). Re-lead each with the reader outcome
  per BRAND.md ("you get this → so you get this").
- **Headline** is strong and on-brand; keep. Subhead could name the satellite/terrain specifics.

## D. THEME CONSISTENCY (mostly DONE)

- Palette, type, dark mode: **already match the app** — no token changes needed.
- Only drift: **screenshots** (old app look) — covered in B. Ensure new imagery uses the same palette.
- Verify each secondary page (join-*, setup-*, privacy, thanks, attribution, watchvid) carries the same
  header/footer/tokens (spot-check; they share `styles.css`, so likely fine).

---

## Recommended order
1. **Fix the privacy over-claim** (B-risk, do immediately even before the rest).
2. **Decide beta→launch + pricing** (JD).
3. **Trails section → all live, with prices + purchase links.**
4. **Add satellite-maps benefit + purchase-model section.**
5. **Re-shoot all screenshots/video** from the current app (real device frames).
6. **Conversion polish** (pricing visible, benefit-led copy, secondary CTA, drop raw-APK).
7. Spot-check every page for theme + copy consistency against BRAND.md.

Implementation is a content/markup pass on `index.html` (+ a few new screenshots) — the design system
(`styles.css`) already carries the app theme, so this is mostly copy, the trails grid, one or two new
sections, and fresh imagery.
