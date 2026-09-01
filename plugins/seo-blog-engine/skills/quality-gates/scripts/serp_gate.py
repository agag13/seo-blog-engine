#!/usr/bin/env python3
"""SERP gate: reject a keyword on who ranks, not on a difficulty score.

Difficulty scores do not measure the thing that decides whether to build. On one
account three of twelve keywords that all looked easy were killed by the live
SERP, and the clearest was `coinbase perpetual futures`: difficulty 6, the
easiest figure on the board, and eight of nine organic results were coinbase.com.
There was no position to take. A second keyword read difficulty 5 and returned
sec.gov at 1 and investor.gov at 2.

So the rule is structural:

    BUILD   Reddit, Quora, Stack Exchange, forums and small blogs near the top.
            Nobody owns the SERP, and the exact phrase is thin in titles/URLs.
    STOP    .gov at 1, or two or more .gov in the top 10, or Wikipedia top 3,
            or one domain holding half of page one, or a partner ranking on it.

This script does not call an API. The agent pulls the SERP with whatever
provider answered (see research-chain) and saves the JSON; the script judges it
with an exit code the pipeline cannot argue with. That split matters, because
the judgement then does not vary with who is running it or which provider was up.

Input
-----
Either a DataForSEO `serp/google/organic/live/advanced` response, or a plain
list, or {"keyword": ..., "results": [...]} where each result carries at least
`url`, and optionally `title`, `domain`/`rank_absolute`.

Usage
-----
    python3 serp_gate.py --keyword "what is a perp dex" serp.json
    python3 serp_gate.py --json --keyword "coinbase perpetual futures" serp.json

Exit codes
----------
    0   BUILD
    1   BUILD with caution, read the warnings before committing the slot
    2   REJECT, do not build this keyword

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import site_config  # noqa: E402

# Forums and UGC near the top mean Google has no authoritative page to reward.
BUILD_SIGNALS = {
    "reddit.com", "quora.com", "stackexchange.com", "stackoverflow.com",
    "ethereum.stackexchange.com", "news.ycombinator.com", "medium.com",
    "substack.com", "dev.to", "discourse.org", "forum.", "community.",
}
# Institutional publishers. Not fatal alone; fatal in numbers or at position 1.
MAJOR_NEWS = {
    "nytimes.com", "wsj.com", "reuters.com", "bloomberg.com", "ft.com",
    "cnbc.com", "bbc.com", "bbc.co.uk", "theguardian.com", "forbes.com",
    "washingtonpost.com", "apnews.com", "economist.com", "cnn.com",
    "businessinsider.com", "techcrunch.com", "axios.com",
}
ENCYCLOPEDIC = {"wikipedia.org", "britannica.com", "investopedia.com"}


def host(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return re.sub(r"^www\.", "", h)


def registrable(h: str) -> str:
    """Good-enough eTLD+1 for grouping. Handles the common two-part suffixes."""
    parts = h.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"co.uk", "com.au", "co.in", "gov.uk", "org.uk"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


def load_results(path: str) -> tuple[str | None, list[dict]]:
    doc = json.load(open(path, encoding="utf-8"))
    kw = None

    # DataForSEO live/advanced envelope
    if isinstance(doc, dict) and "tasks" in doc:
        items = []
        for t in doc.get("tasks") or []:
            kw = kw or ((t.get("data") or {}).get("keyword"))
            for r in t.get("result") or []:
                kw = kw or r.get("keyword")
                items += [i for i in (r.get("items") or [])
                          if i.get("type") in (None, "organic")]
        return kw, items

    if isinstance(doc, dict):
        kw = doc.get("keyword")
        doc = doc.get("results") or doc.get("items") or []
    # A raw MCP response mixes ai_overview, people_also_ask and related_searches
    # in with the organic items. Judging those as ranking results would read a
    # PAA box as a competitor.
    return kw, [i for i in doc if not isinstance(i, dict) or i.get("type") in (None, "organic")]


def ai_overview_domains(path: str) -> list[str]:
    """Domains the AI Overview cites. A .gov-cited overview is a stop signal even
    when the organic ten look survivable."""
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    pool = doc.get("items") if isinstance(doc, dict) else None
    if not pool and isinstance(doc, dict):
        pool = [i for t in (doc.get("tasks") or []) for r in (t.get("result") or [])
                for i in (r.get("items") or [])]
    out = []
    for it in pool or []:
        if isinstance(it, dict) and it.get("type") == "ai_overview":
            for ref in it.get("references") or []:
                d = re.sub(r"^www\.", "", (ref.get("domain") or "").lower())
                if d and d not in out:
                    out.append(d)
    return out


def analyse(keyword: str, items: list[dict], partners: list[str],
            aio: list[str] | None = None) -> dict:
    rows = []
    for i, it in enumerate(items[:10], start=1):
        url = it.get("url") or it.get("link") or ""
        h = host(url) or (it.get("domain") or "").lower()
        rows.append({
            "pos": it.get("rank_absolute") or it.get("position") or i,
            "url": url,
            "domain": h,
            "reg": registrable(h),
            "title": (it.get("title") or "").strip(),
        })

    findings, verdict = [], 0

    def add(sev, rule, msg):
        nonlocal verdict
        findings.append({"severity": sev, "rule": rule, "message": msg})
        verdict = max(verdict, 2 if sev == "REJECT" else 1)

    if not rows:
        add("REJECT", "empty-serp",
            "No organic results parsed. A SERP that could not be read is not a SERP that passed.")
        return {"keyword": keyword, "results": rows, "findings": findings, "verdict": 2}

    gov = [r for r in rows if r["domain"].endswith((".gov", ".gov.uk", ".mil")) or ".gov." in r["domain"]]
    edu = [r for r in rows if r["domain"].endswith(".edu")]
    wiki = [r for r in rows if r["reg"] in ENCYCLOPEDIC]
    news = [r for r in rows if r["reg"] in MAJOR_NEWS]
    ugc = [r for r in rows
           if r["reg"] in BUILD_SIGNALS or any(s in r["domain"] for s in BUILD_SIGNALS)]

    if gov and min(r["pos"] for r in gov) == 1:
        add("REJECT", "gov-at-one",
            f"A .gov holds position 1 ({gov[0]['domain']}). This is regulator ground. "
            f"Hand it to newsjack or a legal-reviewed page, not an evergreen build.")
    elif len(gov) >= 2:
        add("REJECT", "gov-plural",
            f"{len(gov)} .gov results in the top 10 ({', '.join(r['domain'] for r in gov)}). "
            f"Google is answering this with the regulator.")
    elif gov:
        add("WARN", "gov-present",
            f"One .gov at position {gov[0]['pos']} ({gov[0]['domain']}). Survivable, but check "
            f"the AI Overview citations before committing: if it also cites .gov, stop.")
    if edu:
        add("WARN", "edu-present",
            f"{len(edu)} .edu result(s). Academic ground, usually a sign the query is being "
            f"read as research rather than as a how-to.")

    top_wiki = [r for r in wiki if r["pos"] <= 3]
    if top_wiki:
        add("REJECT", "encyclopedia-top-3",
            f"{top_wiki[0]['domain']} at position {top_wiki[0]['pos']}. A definitional query "
            f"already answered by an encyclopedia has no gap to fill.")
    elif wiki:
        add("WARN", "encyclopedia-present", f"{wiki[0]['domain']} ranks at {wiki[0]['pos']}.")

    if len(news) >= 4:
        add("REJECT", "news-dominated",
            f"{len(news)} of 10 are major news ({', '.join(r['reg'] for r in news[:4])}). "
            f"This is a news query, not an evergreen one.")
    elif len(news) >= 2:
        add("WARN", "news-present", f"{len(news)} major-news results in the top 10.")

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["reg"]] = counts.get(r["reg"], 0) + 1
    owner, n = max(counts.items(), key=lambda kv: kv[1])
    if n >= max(4, len(rows) // 2):
        add("REJECT", "single-brand-owns-page",
            f"{owner} holds {n} of {len(rows)} results. This is a navigational brand SERP: "
            f"Google is answering 'show me {owner}'. There is no position to take, whatever "
            f"the difficulty score says.")
    elif n >= 3:
        add("WARN", "domain-concentration", f"{owner} holds {n} of {len(rows)} results.")

    for p in partners:
        pl = p.lower().strip()
        hits = [r for r in rows if pl and (pl in r["reg"] or pl in r["title"].lower())]
        if hits:
            add("REJECT", "partner-on-serp",
                f"Partner '{p}' ranks here (position {hits[0]['pos']}, {hits[0]['domain']}). "
                f"Building this page puts the client in competition with its own partner.")

    if ugc:
        findings.append({"severity": "SIGNAL", "rule": "ugc-ranks",
                         "message": f"{len(ugc)} forum/UGC result(s) in the top 10 "
                                    f"({', '.join(r['reg'] for r in ugc)}). Google has no "
                                    f"authoritative page to reward. This is the build case."})

    aio = aio or []
    aio_gov = [d for d in aio if d.endswith((".gov", ".gov.uk", ".mil")) or ".gov." in d]
    if aio_gov:
        add("REJECT", "ai-overview-cites-gov",
            f"The AI Overview cites {', '.join(aio_gov)}. Even a survivable organic ten does not "
            f"beat the regulator being the answer engine's source.")
    elif aio:
        findings.append({"severity": "SIGNAL", "rule": "ai-overview-sources",
                         "message": f"AI Overview cites {len(aio)} domains: {', '.join(aio[:6])}. "
                                    f"These are the pages to displace, not the organic ten."})

    kw_norm = re.sub(r"\s+", " ", (keyword or "").lower()).strip()
    if kw_norm:
        in_title = sum(1 for r in rows if kw_norm in r["title"].lower())
        in_url = sum(1 for r in rows if kw_norm.replace(" ", "-") in r["url"].lower())
        findings.append({"severity": "SIGNAL", "rule": "exact-phrase",
                         "message": f"Exact phrase in {in_title}/{len(rows)} titles and "
                                    f"{in_url}/{len(rows)} URLs. Low counts mean Google is "
                                    f"rewarding nobody for the phrase itself."})
        if in_title >= 6:
            add("WARN", "phrase-saturated",
                f"{in_title} of {len(rows)} titles carry the exact phrase. The slot is "
                f"well served; information gain has to be real.")

    return {"keyword": keyword, "results": rows, "findings": findings, "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("serp_json", help="saved SERP response (DataForSEO envelope or plain list)")
    ap.add_argument("--keyword", default=None)
    ap.add_argument("--json", action="store_true")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    if not os.path.exists(a.serp_json):
        print(f"missing: {a.serp_json}", file=sys.stderr)
        return 2

    root = site_config.find_project_root(a.serp_json, a.project_root)
    partners = []
    pfile = site_config.context_file(root, "PARTNERS.md")
    if pfile:
        for line in open(pfile, encoding="utf-8", errors="replace"):
            m = re.match(r"^##\s+(.+?)\s*$", line)
            if m:
                partners.append(m.group(1).strip())

    kw_from_file, items = load_results(a.serp_json)
    rep = analyse(a.keyword or kw_from_file or "", items, partners,
                  ai_overview_domains(a.serp_json))

    if a.json:
        print(json.dumps(rep, indent=2))
        return rep["verdict"]

    label = {0: "BUILD", 1: "BUILD WITH CAUTION", 2: "REJECT"}[rep["verdict"]]
    print(f"serp_gate · \"{rep['keyword'] or '(no keyword given)'}\" · {len(rep['results'])} results")
    print(f"  partners loaded: {len(partners)}"
          + ("" if pfile else "  (no PARTNERS.md found, partner check did not run)"))
    print()
    for r in rep["results"]:
        print(f"  {str(r['pos']):>3}  {r['domain'][:38]:<38} {r['title'][:52]}")
    print()
    for f in rep["findings"]:
        print(f"  {f['severity']:<7} {f['rule']}")
        print(f"          {f['message']}")
    print(f"\n{label}")
    return rep["verdict"]


if __name__ == "__main__":
    sys.exit(main())
