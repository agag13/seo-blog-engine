#!/usr/bin/env python3
"""Claims gate: every load-bearing claim is cited, and the source actually says it.

Fact-checking is reported as the real bottleneck in AI content work, to the point
where practitioners say checking the output takes longer than writing it would
have. That is true of the *judgment* half. It is not true of the rest, and most
of the rest is what actually goes wrong.

So this splits the job the same way the engine splits everything else:

    deterministic          -> this script, with a blocking exit code
    genuinely a judgment   -> a short VERIFY list a human reads

What is deterministic, and it is more than people expect:

    1. does a claim carrying a number have a citation at all
    2. does the cited URL resolve                  (links_check already does this)
    3. **does the claimed value actually appear on the cited page**
    4. is the source recent enough for a present-tense claim
    5. is the draft's hedge stronger than the source's hedge

Three failure modes this exists for, all of which really happened:

  * **A real URL that does not say the thing.** The commonest hallucination is
    not an invented link, it is a correct-looking link to a page that never made
    the claim. Check 3 catches it and needs no judgment.
  * **True, but stale.** "Bridges are the largest category of DeFi loss" was
    true in 2022 and false by 2025. The source exists and says it, so a string
    match passes. This is the dangerous one, because it looks verified. Check 4.
  * **Qualifier drift.** The source said "some", the draft says "most". Same
    topic, same source, different claim. Check 5.

**On qualitative claims.** Regex finds numbers. It does not find "most X are Y",
which is exactly the shape of the two worst errors on the reference account. So
the model extracts those into a ledger, and this script enforces that every
ledger entry has a citation and a verdict. Extraction is judgment; coverage is
arithmetic, and coverage is what gets enforced.

Ledger format, `<slug>-claims.json`, written by the fact-check skill:

    [{"text": "...", "url": "https://...", "kind": "qualitative",
      "recency_months": 18}]

Usage
-----
    python3 claims_check.py drafts/x.mdx
    python3 claims_check.py drafts/x.mdx --ledger scratch/x-claims.json
    python3 claims_check.py drafts/x.mdx --source-cache scratch/sources --json

Exit codes
----------
    0   every claim checked, every one supported
    1   warnings, or a source could not be fetched
    2   an uncited claim, or a source that does not support the claim

Stdlib only. `--source-cache` lets a skill pre-fetch pages with a real extractor
(Tavily, DataForSEO on-page) for sites that block a plain fetch; the script reads
the cache first and falls back to fetching directly.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html as _html
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import site_config  # noqa: E402
from schema_check import norm  # the comparison form is already defined once  # noqa: E402

UA = "seo-blog-engine-claimscheck/1.0"
TIMEOUT = 25

# Strength ladder. A draft may always be weaker than its source, never stronger.
HEDGES = [
    (0, ["few", "rarely", "a minority of", "occasionally"]),
    (1, ["some", "several", "certain", "can", "may", "might", "sometimes"]),
    (2, ["many", "often", "frequently", "commonly", "typically", "usually"]),
    (3, ["most", "the majority of", "generally"]),
    (4, ["all", "every", "always", "never", "no ", "none", "the largest",
         "the biggest", "the leading", "the only"]),
]

# A sentence carrying one of these is load-bearing and needs a source.
NUMBER = re.compile(
    r"(?<![\w.])(?:"
    r"[$£€₹]\s?\d[\d,]*(?:\.\d+)?\s?(?:[kmbt]n?|billion|million|trillion|thousand|crore|lakh)?"
    r"|\d[\d,]*(?:\.\d+)?\s?%"
    r"|\d[\d,]*(?:\.\d+)?\s?(?:billion|million|trillion|thousand|crore|lakh)"
    r"|\b(?:19|20)\d{2}\b"
    r"|\b\d[\d,]{2,}(?:\.\d+)?\b"
    r")", re.I)

ATTRIBUTION = re.compile(
    r"\b(?:according to|per|says|said|reports?|found that|study|survey|research)\b", re.I)

MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6,
        "b": 1e9, "bn": 1e9, "billion": 1e9, "t": 1e12, "tn": 1e12,
        "trillion": 1e12, "lakh": 1e5, "crore": 1e7}


# --------------------------------------------------------------------------- text

def strip_scaffold(raw: str) -> str:
    raw = re.sub(r"(?s)\A---\n.*?\n---\n", "", raw)      # frontmatter
    raw = re.sub(r"(?s)\{/\*.*?\*/\}", " ", raw)          # handover comments
    raw = re.sub(r"(?s)```.*?```", " ", raw)              # code fences
    raw = re.sub(r"(?is)<svg\b.*?</svg>", " ", raw)       # diagrams
    return raw


def sentences(text: str):
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para or para.startswith(("#", ">", "|")):
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'\[])", para):
            s = s.strip()
            if s:
                yield s


def line_of(raw: str, needle: str) -> int | None:
    i = raw.find(needle[:60])
    return raw.count("\n", 0, i) + 1 if i >= 0 else None


def hedge_rank(text: str):
    """Strongest hedge in the text, as (rank, word). None if unqualified."""
    best = None
    low = " " + text.lower() + " "
    for rank, words in HEDGES:
        for w in words:
            # Both ends must be word boundaries. Without the trailing guard,
            # "every" matches inside "everyone" and the strongest hedge on the
            # ladder fires on an ordinary sentence.
            if re.search(r"(?<![\w])" + re.escape(w.strip()) + r"(?![\w])", low):
                if best is None or rank > best[0]:
                    best = (rank, w.strip())
    return best


# --------------------------------------------------------------------------- numbers

def number_variants(token: str) -> list:
    """Every plausible way a source could spell the same figure.

    `$3.4bn` must match `3.4 billion` and `$3,400,000,000`, or the check
    generates false blocks and gets switched off within a week.
    """
    t = token.strip()
    out = {t, t.replace(",", ""), t.replace("$", "").replace("£", "")
           .replace("€", "").replace("₹", "").strip()}

    m = re.match(r"^[$£€₹]?\s?([\d,]+(?:\.\d+)?)\s*([a-z]+)?%?$", t.strip(), re.I)
    if not m:
        return sorted(x for x in out if x)
    raw_num, unit = m.group(1).replace(",", ""), (m.group(2) or "").lower()
    try:
        val = float(raw_num)
    except ValueError:
        return sorted(x for x in out if x)

    if unit in MULT:
        full = val * MULT[unit]
        out.add(f"{raw_num} {unit}")
        for name, mult in MULT.items():
            if abs(mult - MULT[unit]) < 1e-9 or mult == MULT[unit]:
                out.add(f"{raw_num} {name}")
        if full.is_integer():
            out.add(f"{int(full):,}")
            out.add(str(int(full)))
    else:
        out.add(raw_num)
        if val.is_integer():
            out.add(f"{int(val):,}")
            out.add(str(int(val)))
    return sorted(x for x in out if x)


def claim_tokens(text: str) -> list:
    return [m.group(0) for m in NUMBER.finditer(text)]


# --------------------------------------------------------------------------- fetch

def cache_path(cache_dir: str, url: str) -> str:
    return os.path.join(cache_dir, hashlib.sha1(url.encode()).hexdigest() + ".txt")


def fetch(url: str, cache_dir: str | None):
    """(state, text, note). state is one of ok / unfetchable."""
    if cache_dir:
        p = cache_path(cache_dir, url)
        if os.path.exists(p):
            return "ok", open(p, encoding="utf-8", errors="replace").read(), "cache"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(3_000_000).decode(r.headers.get_content_charset() or "utf-8",
                                            errors="replace")
    except urllib.error.HTTPError as e:
        return "unfetchable", "", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return "unfetchable", "", type(e).__name__

    body = re.sub(r"(?is)<(script|style|nav|footer)[^>]*>.*?</\1>", " ", body)
    text = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", body)))
    if len(text.strip()) < 400:
        # A near-empty extraction is almost always a JS-rendered page, not a page
        # that says nothing. Calling that NOT_FOUND would be a false accusation.
        return "unfetchable", text, "thin extraction, probably JS-rendered"
    return "ok", text, "direct"


def source_date(text: str):
    m = re.search(r"\b(20[12]\d)-(\d{2})-(\d{2})\b", text) or re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+(20[12]\d)\b",
        text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (ValueError, IndexError):
        return None


# --------------------------------------------------------------------------- claims

def extract_claims(raw: str) -> list:
    """Claims a regex can find: anything carrying a figure or an attribution."""
    body = strip_scaffold(raw)
    out = []
    for s in sentences(body):
        toks = claim_tokens(s)
        attributed = bool(ATTRIBUTION.search(s))
        if not toks and not attributed:
            continue
        urls = re.findall(r"\]\((https?://[^)\s]+)\)|href=[\"'](https?://[^\"']+)", s)
        url = next((a or b for a, b in urls), None)
        out.append({"text": s, "url": url, "kind": "stat" if toks else "attribution",
                    "tokens": toks, "source": "auto"})
    return out


def load_ledger(path: str) -> list:
    doc = json.load(open(path, encoding="utf-8"))
    items = doc if isinstance(doc, list) else doc.get("claims", [])
    for c in items:
        c.setdefault("kind", "qualitative")
        c.setdefault("tokens", claim_tokens(c.get("text", "")))
        c["source"] = "ledger"
    return items


def nearby_url(raw: str, claim_text: str):
    """A citation on the following line still counts, because sources are often
    placed under the sentence rather than inside it.

    But the window stops at the paragraph break. Scanning past it lets an
    uncited claim borrow the next paragraph's citation, which is worse than
    having no check at all: it reports a bare assertion as sourced.
    """
    i = raw.find(claim_text[:60])
    if i < 0:
        return None
    window = raw[i:i + len(claim_text) + 400]
    brk = window.find("\n\n", len(claim_text) - 1)
    if brk >= 0:
        window = window[:brk]
    m = re.search(r"\]\((https?://[^)\s]+)\)|href=[\"'](https?://[^\"']+)|(?<![\w(])(https?://\S{6,})",
                  window)
    if not m:
        return None
    return next((g for g in m.groups() if g), None)


def check(path: str, ledger: str | None, cache_dir: str | None,
          default_recency: int) -> dict:
    raw = open(path, encoding="utf-8", errors="replace").read()
    claims = extract_claims(raw)
    if ledger:
        claims += load_ledger(ledger)

    findings, verify_list = [], []
    fetched: dict = {}

    def add(sev, rule, msg, claim=None):
        findings.append({"severity": sev, "rule": rule, "message": msg,
                         "claim": (claim or "")[:150],
                         "line": line_of(raw, claim) if claim else None})

    for c in claims:
        text = c.get("text", "")
        url = c.get("url") or nearby_url(raw, text)

        if not url:
            add("BLOCK", "claim-uncited",
                "Load-bearing claim with no source. Cite it, or take the figure out.",
                text)
            continue

        if url not in fetched:
            fetched[url] = fetch(url, cache_dir)
        state, body, note = fetched[url]

        if state == "unfetchable":
            add("WARN", "source-unfetchable",
                f"Could not read {url} ({note}). This is NOT evidence the claim is "
                f"wrong, and it is not evidence it is right either. Re-fetch with a "
                f"real extractor into --source-cache, or verify by hand.", text)
            verify_list.append({"claim": text, "url": url, "why": "unfetchable"})
            continue

        hay = norm(body).lower()

        # ---- 3. does the page actually carry the figure -----------------------
        missing = []
        for tok in c.get("tokens") or []:
            if not any(norm(v).lower() in hay for v in number_variants(tok)):
                missing.append(tok)
        if missing:
            add("BLOCK", "value-not-in-source",
                f"{', '.join(missing)} does not appear on {url}. Either the source "
                f"does not say this, or the citation points at the wrong page.", text)
            continue

        # ---- 4. stale but true ------------------------------------------------
        months = c.get("recency_months", default_recency)
        yr = source_date(body)
        if yr and months:
            age_months = (datetime.date.today().year - yr) * 12
            if age_months > months:
                add("BLOCK", "source-too-old",
                    f"The figure is on the page, but the source reads as {yr}, about "
                    f"{age_months // 12} years old against a {months}-month limit for "
                    f"this claim. True once is not true now, and a stale claim with a "
                    f"working citation is the hardest kind to spot.", text)
                continue

        # ---- 5. qualifier drift ----------------------------------------------
        dh = hedge_rank(text)
        if dh:
            idx = hay.find(norm(next(iter(c.get("tokens") or [""]), "")).lower())
            window = body[max(0, idx - 400):idx + 400] if idx >= 0 else body[:1500]
            sh = hedge_rank(window)
            if sh and dh[0] > sh[0]:
                add("BLOCK", "qualifier-stronger-than-source",
                    f'Draft says "{dh[1]}", the source around this figure says '
                    f'"{sh[1]}". Publishing a stronger claim than the source supports '
                    f"is the failure mode that matters; a weaker one never is.", text)
                continue

        if c.get("kind") == "qualitative":
            verify_list.append({"claim": text, "url": url,
                                "why": "qualitative, needs a human read"})

    if not claims:
        add("WARN", "no-claims-found",
            "No load-bearing claims were found. Either the draft carries no evidence, "
            "which is its own problem, or extraction missed them.")

    return {"path": path, "claims": len(claims), "findings": findings,
            "verify": verify_list, "sources": len(fetched)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--ledger", default=None,
                    help="<slug>-claims.json from the fact-check skill, carrying the "
                         "qualitative claims a regex cannot find")
    ap.add_argument("--source-cache", default=None,
                    help="directory of pre-fetched source pages, for sites a plain "
                         "fetch cannot read")
    ap.add_argument("--recency-months", type=int, default=36,
                    help="default age limit for a cited source (default 36). Per-claim "
                         "`recency_months` in the ledger overrides it.")
    ap.add_argument("--json", action="store_true")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    reports = [check(p, a.ledger, a.source_cache, a.recency_months)
               for p in a.paths if os.path.exists(p)]
    worst = 0
    for r in reports:
        if any(f["severity"] == "BLOCK" for f in r["findings"]):
            worst = 2
        elif r["findings"] and worst < 1:
            worst = 1

    if a.json:
        print(json.dumps({"verdict": worst, "reports": reports}, indent=2))
        return worst

    for r in reports:
        blocks = [f for f in r["findings"] if f["severity"] == "BLOCK"]
        state = "BLOCKED" if blocks else ("warn" if r["findings"] else "clean")
        print(f"claims_check · {r['path']}   [{state}]")
        print(f"  {r['claims']} claim(s), {r['sources']} source(s) fetched\n")
        for f in r["findings"]:
            loc = f":{f['line']}" if f.get("line") else ""
            print(f"  {f['severity']:<5} {f['rule']}{loc}")
            print(f"        {f['message']}")
            if f["claim"]:
                print(f"        > {f['claim']}")
            print()
        if r["verify"]:
            print(f"  VERIFY list, {len(r['verify'])} item(s) a human reads:")
            for v in r["verify"]:
                print(f"    - {v['why']}: {v['claim'][:90]}")
            print()
    print({0: "PASS", 1: "PASS with unverified sources",
           2: "FAIL, a claim is uncited or unsupported"}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
