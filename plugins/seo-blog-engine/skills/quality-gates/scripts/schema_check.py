#!/usr/bin/env python3
"""Layer C gate: JSON-LD validity, and FAQPage answers matching the visible copy.

Three failure modes this catches, all of which have already happened in production:

  1. A FAQPage answer that drifts from the visible <details> copy. Google treats
     structured data that does not match the page as a markup violation, and it
     is trivially easy to edit one and not the other.
  2. BlogPosting with no `image`. Article rich results will not fire without it.
     The script surfaces it rather than letting it pass.
  3. A FAQ block belonging to a DIFFERENT article. Two surfaces is not enough:
     a shared scratchpad once replaced both the JSON-LD and the visible copy
     from the same wrong source, they agreed with each other, and a two-surface
     check returned OK. The gate therefore matches across THREE surfaces, the
     third being the sibling source file (.mdx/.md).

Usage
-----
    python3 schema_check.py out/what-is-a-crypto-bridge.html
    python3 schema_check.py --json out/*.html

Exit codes
----------
    0   valid, and the FAQ matches
    1   warnings (missing image, soft metadata issues)
    2   invalid JSON-LD, or a FAQ answer that does not match the page

Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import site_config  # noqa: E402

REPO = os.getcwd()
SITE = ""
# The third surface. Normally the sibling .mdx beside the .html, but a build that
# writes into a separate output directory has to say where the source is, or the
# one check that detects cross-article contamination silently stops running.
MDX_OVERRIDE = ""

# Types Google no longer produces rich results for. Keep them for AI extraction,
# but do not claim a rich result. Mirrors seo-schema's classification.
NO_RICH_RESULT = {"FAQPage", "HowTo"}


def text_of(fragment: str) -> str:
    """Visible text from an HTML fragment, whitespace-normalised."""
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def norm(s: str) -> str:
    """Comparison form. Collapses whitespace and unifies the quote and dash
    characters that differ between JSON-LD and rendered HTML."""
    s = html.unescape(s)
    s = (s.replace("’", "'").replace("‘", "'")
          .replace("“", '"').replace("”", '"')
          .replace(" ", " ").replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", s).strip()


def visible_faq(raw: str) -> list[tuple[str, str]]:
    """(question, answer) from the rendered <details>/<summary> FAQ block.

    The preview template also uses <details> for the internal SEO spec panel at
    the bottom of the page. That panel is not part of the published article, so
    everything from its container onward is cut before scanning. Matching on a
    `<div class="faq">...</div>` boundary is not reliable, because the FAQ block
    contains nested divs.
    """
    cut = re.search(r'(?is)<(?:div|section|aside)[^>]*class=["\'][^"\']*\bseospec\b', raw)
    scope = raw[:cut.start()] if cut else raw

    out = []
    for d in re.findall(r"(?is)<details[^>]*>(.*?)</details>", scope):
        q = re.search(r"(?is)<summary[^>]*>(.*?)</summary>", d)
        if not q:
            continue
        qt = text_of(q.group(1)).lstrip("▸▾▶ ").strip()
        if not qt or "seo spec" in qt.lower():
            continue
        body = re.sub(r"(?is)<summary[^>]*>.*?</summary>", "", d)
        out.append((qt, text_of(body)))
    return out


def check(path: str) -> dict:
    raw = open(path, encoding="utf-8", errors="replace").read()
    findings: list[dict] = []

    def add(sev, rule, msg):
        findings.append({"severity": sev, "rule": rule, "message": msg})

    blocks = re.findall(r'(?s)<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', raw)
    if not blocks:
        add("BLOCK", "no-jsonld", "No JSON-LD block found.")
        return {"path": path, "findings": findings, "types": []}

    nodes = []
    for i, b in enumerate(blocks):
        try:
            doc = json.loads(b)
        except json.JSONDecodeError as e:
            add("BLOCK", "invalid-json", f"JSON-LD block {i + 1} does not parse: {e}")
            continue
        nodes += doc.get("@graph", [doc]) if isinstance(doc, dict) else doc

    types = [n.get("@type") for n in nodes if isinstance(n, dict)]
    by_type = {}
    for n in nodes:
        if isinstance(n, dict) and isinstance(n.get("@type"), str):
            by_type.setdefault(n["@type"], []).append(n)

    # ---- BlogPosting ------------------------------------------------------
    for bp in by_type.get("BlogPosting", []) + by_type.get("Article", []):
        for field in ("headline", "datePublished", "author", "publisher", "description"):
            if not bp.get(field):
                add("BLOCK", "blogposting-missing", f"BlogPosting is missing `{field}`.")
        if not bp.get("image"):
            add("WARN", "blogposting-no-image",
                "BlogPosting has no `image`. Article rich results will not fire. "
                "Add it when the cover asset gets a production URL.")
        if bp.get("headline") and len(bp["headline"]) > 110:
            add("WARN", "headline-long",
                f"headline is {len(bp['headline'])} chars; Google truncates past ~110.")

    if not by_type.get("BlogPosting") and not by_type.get("Article"):
        add("WARN", "no-article-node", "No BlogPosting or Article node in the graph.")

    # ---- FAQPage byte-match ----------------------------------------------
    seen = visible_faq(raw)
    for fq in by_type.get("FAQPage", []):
        ents = fq.get("mainEntity", [])
        if not ents:
            add("BLOCK", "faq-empty", "FAQPage has no mainEntity.")
            continue
        if not seen:
            add("BLOCK", "faq-not-visible",
                f"FAQPage declares {len(ents)} questions but no visible FAQ block was found. "
                f"Structured data must reflect content on the page.")
            continue
        if len(ents) != len(seen):
            add("BLOCK", "faq-count-mismatch",
                f"FAQPage declares {len(ents)} questions, the page shows {len(seen)}.")

        vis = {norm(q): norm(a) for q, a in seen}
        for e in ents:
            q = norm(e.get("name", ""))
            a = norm((e.get("acceptedAnswer") or {}).get("text", ""))
            if q not in vis:
                add("BLOCK", "faq-question-missing",
                    f'Question in JSON-LD is not on the page: "{q[:70]}"')
            elif vis[q] != a:
                add("BLOCK", "faq-answer-mismatch",
                    f'Answer text differs from the visible copy for "{q[:55]}".\n'
                    f'           json: {a[:90]}\n'
                    f'           page: {vis[q][:90]}')
        # ---- third surface: the sibling .mdx ------------------------------
        # A two-way check (JSON-LD vs visible HTML) CANNOT detect cross-article
        # contamination, because a shared scratchpad can replace both surfaces
        # from the same wrong source and they still agree with each other.
        # That happened on 2026-09-01: an .html shipped with another article's
        # eight FAQs in BOTH places and this gate returned "OK faq-match".
        # See docs/batch-3-run-2026-09-01.md section 3.
        mdx_path = MDX_OVERRIDE or re.sub(r"\.html?$", ".mdx", str(path))
        orphans = []
        if os.path.exists(mdx_path) and mdx_path != str(path):
            mraw = open(mdx_path, encoding="utf-8", errors="replace").read()
            mraw = re.sub(r"(?s)\{/\*.*?\*/\}", " ", mraw)   # drop handover comments
            mbody = norm(re.sub(r"<[^>]+>", " ", mraw))
            for e in ents:
                a = norm((e.get("acceptedAnswer") or {}).get("text", ""))
                probe = a[:60]
                if probe and probe not in mbody:
                    orphans.append(norm(e.get("name", ""))[:70])
            if orphans:
                add("BLOCK", "faq-not-in-mdx",
                    f"{len(orphans)} FAQ answer(s) are in the HTML but NOT in the sibling MDX. "
                    f"This is the cross-contamination signature: the .html was built from "
                    f"another article's source.\n           "
                    + "\n           ".join(f'orphan: "{o}"' for o in orphans[:3]))
        elif not os.path.exists(mdx_path):
            add("WARN", "faq-no-mdx-sibling",
                f"No sibling MDX at {os.path.basename(mdx_path)}, so the three-way "
                f"FAQ check did not run. Two-way agreement alone cannot detect "
                f"cross-article contamination.")

        if len(ents) == len(seen) and not orphans and not any(
                f["rule"].startswith("faq-") for f in findings):
            add("OK", "faq-match",
                f"All {len(ents)} FAQ answers match across three surfaces: "
                f"JSON-LD, visible copy, and the sibling MDX.")

    # ---- page metadata ----------------------------------------------------
    canon = re.search(r'(?i)<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', raw)
    if not canon:
        add("BLOCK", "no-canonical", "No canonical link.")
    else:
        u = canon.group(1)
        if u.startswith("https://www."):
            add("BLOCK", "canonical-www",
                f"Canonical points at www. Apex is canonical: {u}")
        elif SITE and not u.startswith(SITE + "/"):
            add("WARN", "canonical-host", f"Canonical is off-host, expected {SITE}: {u}")
        elif not SITE:
            add("WARN", "canonical-unchecked",
                "No site.url in project.yaml, so the canonical host was not checked.")

    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    if t:
        n = len(text_of(t.group(1)))
        if n > 60:
            add("WARN", "title-long", f"<title> is {n} chars; SERP truncates near 60.")
    d = re.search(r'(?i)<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', raw)
    if d:
        n = len(d.group(1))
        if not 120 <= n <= 165:
            add("WARN", "description-length",
                f"meta description is {n} chars; aim for 120-165.")
    else:
        add("BLOCK", "no-description", "No meta description.")

    for ty in set(types) & NO_RICH_RESULT:
        add("INFO", "no-rich-result",
            f"{ty} no longer produces rich results in Google. Keep it, it still "
            f"feeds AI extraction, but do not report it as a rich-result win.")

    return {"path": path, "findings": findings, "types": sorted(set(map(str, types)))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--site", default=None, help="site root URL, e.g. https://example.com")
    ap.add_argument("--mdx", default=None,
                    help="the source draft, when the HTML was built into a different "
                         "directory. Without it the third-surface check falls back to "
                         "looking for a sibling .mdx, and reports if it found none.")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    global REPO, SITE, MDX_OVERRIDE
    REPO = site_config.find_project_root(a.paths[0], a.project_root)
    project = site_config.load_project(REPO)
    SITE = (a.site or site_config.site_url(project)).rstrip("/")
    MDX_OVERRIDE = os.path.abspath(a.mdx) if a.mdx else ""
    if MDX_OVERRIDE and len(a.paths) > 1:
        print("--mdx names one source, so it cannot be used with several HTML files.",
              file=sys.stderr)
        return 2

    worst, reports = 0, []
    for p in a.paths:
        if not os.path.exists(p):
            print(f"missing: {p}", file=sys.stderr)
            worst = 2
            continue
        r = check(p)
        reports.append(r)
        if any(f["severity"] == "BLOCK" for f in r["findings"]):
            worst = 2
        elif any(f["severity"] == "WARN" for f in r["findings"]) and worst < 1:
            worst = 1

    if a.json:
        print(json.dumps(reports, indent=2))
        return worst

    for r in reports:
        rel = os.path.relpath(r["path"], REPO) if r["path"].startswith(REPO) else r["path"]
        blocks = [f for f in r["findings"] if f["severity"] == "BLOCK"]
        state = "BLOCKED" if blocks else (
            "warn" if any(f["severity"] == "WARN" for f in r["findings"]) else "clean")
        print(f"{rel}   [{state}]")
        print(f"  graph: {', '.join(r['types']) or 'none'}")
        for f in r["findings"]:
            print(f"    {f['severity']:<5} {f['rule']}: {f['message']}")
        print()

    print({0: "PASS", 1: "PASS with warnings", 2: "FAIL"}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
