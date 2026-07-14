#!/usr/bin/env python3
"""Generate the per-photograph credit list on attribution.html from the SHIPPED manifests.

WHY THIS EXISTS: the page used to say the landmark photos came from "Mapillary contributors". They do
not — they are ~874 photographs from Wikimedia Commons, each with a named author and a specific licence.
A public attribution page that misnames the source of every photograph is not a credit, it is an error,
and for CC BY-SA it is a licence breach.

CC BY-SA asks for the author, the source, and **a link to the licence** where reasonably practicable.
The in-app credit line names the licence but cannot link it, so the link lives here and Settings points
at this page.

Reads the truth from the packs (never a hand-kept list, which is how the Mapillary claim survived), and
rewrites ONLY the block between the CREDITS-AUTO markers in attribution.html.

    python _gen_attribution.py
"""
import json, os, re, glob, html
from collections import defaultdict

REPO = r"C:\Users\jwden\WatchApps"
WEB  = os.path.join(REPO, "watchwalks-web", "attribution.html")

# The licence deed each licence string points at. A credit that names a licence without linking it is
# the gap this page closes, so an unmapped licence is a HARD ERROR — never a silent omission.
LICENCE_URL = {
    "cc by-sa 4.0":     "https://creativecommons.org/licenses/by-sa/4.0/",
    "cc by-sa 3.0":     "https://creativecommons.org/licenses/by-sa/3.0/",
    "cc by-sa 2.5":     "https://creativecommons.org/licenses/by-sa/2.5/",
    "cc by-sa 2.0":     "https://creativecommons.org/licenses/by-sa/2.0/",
    "cc by-sa 1.0":     "https://creativecommons.org/licenses/by-sa/1.0/",
    "cc by-sa 3.0 de":  "https://creativecommons.org/licenses/by-sa/3.0/de/",
    "cc by-sa 2.0 de":  "https://creativecommons.org/licenses/by-sa/2.0/de/",
    "cc by 4.0":        "https://creativecommons.org/licenses/by/4.0/",
    "cc by 3.0":        "https://creativecommons.org/licenses/by/3.0/",
    "cc by 2.5":        "https://creativecommons.org/licenses/by/2.5/",
    "cc by 2.0":        "https://creativecommons.org/licenses/by/2.0/",
    "cc by 1.0":        "https://creativecommons.org/licenses/by/1.0/",
    "cc by":            "https://creativecommons.org/licenses/by/4.0/",
    "cc0":              "https://creativecommons.org/publicdomain/zero/1.0/",
    "gfdl 1.2":         "https://www.gnu.org/licenses/old-licenses/fdl-1.2.html",
    "gfdl":             "https://www.gnu.org/licenses/fdl-1.3.html",
    "fal":              "https://artlibre.org/licence/lal/en/",
    "public domain":    "https://commons.wikimedia.org/wiki/Commons:Licensing#Public_domain",
    "copyrighted free use": "https://commons.wikimedia.org/wiki/Template:Copyrighted_free_use",
    "attribution":      "https://commons.wikimedia.org/wiki/Template:Attribution",
    "no restrictions":  "https://commons.wikimedia.org/wiki/Commons:Licensing#Public_domain",
}

TRAIL_TITLE = {}   # pack key -> pretty trail name, read from the master


def pretty_names():
    """Pack key -> trail title, from the Kotlin master. The manifests carry no trail title."""
    src = os.path.join(REPO, "watchwalks-android", "app", "src", "main", "java",
                       "com", "watchwalks", "companion", "data", "SampleData.kt")
    names = {}
    if os.path.exists(src):
        txt = open(src, encoding="utf-8", errors="replace").read()
        for tid, title in re.findall(r'id\s*=\s*"([a-z0-9-]+)"[^\n]*?name\s*=\s*"([^"]+)"', txt):
            names[tid] = title
    return names


def licence_link(lic):
    key = (lic or "").strip().lower()
    url = LICENCE_URL.get(key)
    if not url:
        raise SystemExit(
            f"UNMAPPED LICENCE: {lic!r}\n"
            "Add it to LICENCE_URL with its deed. Do NOT ship a licence we cannot link — that is the\n"
            "exact gap this page exists to close."
        )
    return url


def main():
    titles = pretty_names()
    trails = defaultdict(list)
    total = 0

    # ⚠️ DEDUPE BY PACK KEY. A trail can have a manifest in BOTH its own pack module AND the app's
    # bundled assets (the South Pole has exactly that). Globbing both double-counted the trail and put
    # "882 photographs" on a page whose entire purpose is being accurate about the photographs. The true
    # figure, from `photo_rekey.py audit`, is 873. Count each pack ONCE.
    seen_keys = set()
    for man in glob.glob(os.path.join(REPO, "watchwalks-android", "*", "src", "main", "assets",
                                      "milestones", "*", "manifest.json")) + \
               glob.glob(os.path.join(REPO, "watchwalks-android", "app", "src", "main", "assets",
                                      "milestones", "*", "manifest.json")):
        data = json.load(open(man, encoding="utf-8"))
        key = data.get("key") or os.path.basename(os.path.dirname(man))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        for m in data.get("milestones", []):
            if not m.get("image"):
                continue
            total += 1
            trails[key].append({
                "landmark": m.get("name", "").strip(),
                "author":   (m.get("author") or "").strip(),
                "licence":  (m.get("license") or "").strip(),
                "source":   (m.get("source") or "Wikimedia Commons").strip(),
                "credit":   " ".join((m.get("credit") or "").split()),
            })

    if total == 0:
        raise SystemExit("Found ZERO photographs. An empty answer is a claim, not a fact — refusing to "
                         "write an attribution page that credits nobody.")

    out = []
    out.append(f'    <p>Every landmark photograph in the app, with its photographer and its licence. '
               f'There are <b>{total}</b> of them, across {len(trails)} trails. '
               f'Each licence below links to its full text.</p>\n')

    for key in sorted(trails, key=lambda k: titles.get(k, k).lower()):
        rows = sorted(trails[key], key=lambda r: r["landmark"].lower())
        title = titles.get(key, key.replace("-", " ").title())
        out.append(f'    <details class="credits">\n'
                   f'      <summary>{html.escape(title)} '
                   f'<span class="credits-n">{len(rows)} photo{"s" if len(rows) != 1 else ""}</span></summary>\n'
                   f'      <ul class="credit-list">\n')
        for r in rows:
            lic = r["licence"] or "public domain"
            url = licence_link(lic)
            author = html.escape(r["author"] or "Unknown photographer")
            out.append(
                f'        <li><b>{html.escape(r["landmark"])}</b> &mdash; {author}, '
                f'{html.escape(r["source"])}, '
                f'<a href="{url}" target="_blank" rel="noopener license">{html.escape(lic)}</a></li>\n'
            )
        out.append('      </ul>\n    </details>\n')

    block = "".join(out)
    page  = open(WEB, encoding="utf-8").read()
    new   = re.sub(r"(<!-- CREDITS-AUTO:START -->\n).*?(\s*<!-- CREDITS-AUTO:END -->)",
                   lambda m: m.group(1) + block + m.group(2), page, flags=re.S)
    if new == page:
        raise SystemExit("CREDITS-AUTO markers not found in attribution.html — nothing written.")
    open(WEB, "w", encoding="utf-8", newline="\n").write(new)
    print(f"attribution.html: wrote {total} photo credits across {len(trails)} trails")


if __name__ == "__main__":
    main()
