#!/usr/bin/env python3
"""Links gate: every link in a draft resolves, or is a declared forward-link.

"Never build a link to a page that returns a 404" is a hard rule. But a content
programme legitimately ships forward-links to sibling articles that are drafted
and not yet published. Those are fine, and the way they are legitimised is by
naming them in the draft's handover-notes comment.

So the rule this script enforces is:

    an internal link may 404 ONLY IF the {/* ... */} handover block both
    mentions the word "forward-link" and names that exact path.

Anything else that 404s is a bug and blocks.

Usage
-----
    python3 links_check.py drafts/what-is-a-crypto-bridge.mdx
    python3 links_check.py --external drafts/*.mdx   # also check outbound sources
    python3 links_check.py --json drafts/*.mdx

The site root comes from the site's project.yaml (`site.url`), resolved by
walking up from the file being checked. Override with --site.

Exit codes
----------
    0   every link resolves, or 404s are properly declared
    1   external source links failed (worth checking, not always our fault)
    2   an undeclared internal link is broken

Stdlib only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
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

# Both resolved per run in main(), never from __file__.
REPO = os.getcwd()
APEX = ""
HOST = ""
UA = "seo-blog-engine-linkcheck/1.0"
TIMEOUT = 20


def extract_links(raw: str) -> tuple[list[str], str]:
    """Return (links, handover_comment_text). Links come from markdown and href."""
    comment = "\n".join(re.findall(r"(?s)\{/\*(.*?)\*/\}", raw))
    body = re.sub(r"(?s)\{/\*.*?\*/\}", "", raw)
    body = re.sub(r"(?s)```.*?```", "", body)

    links = re.findall(r"\]\(([^)\s]+)", body)                    # markdown
    links += re.findall(r'href=["\']([^"\']+)', body)             # html
    links += re.findall(r"(?m)^\s*(?:-|\d+\.)\s+.*?(https?://\S+)", body)  # bare in lists

    out, seen = [], set()
    for u in links:
        u = u.rstrip(".,;)")
        if not u or u.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out, comment


def classify(url: str) -> str:
    if url.startswith("/"):
        return "internal"
    if url.startswith(("http://", "https://")):
        if not HOST:
            return "external"
        return ("internal" if re.match(r"https?://(www\.)?" + re.escape(HOST) + r"(/|$)", url)
                else "external")
    return "relative"


def absolutise(url: str) -> str:
    if url.startswith("/"):
        return APEX + url
    return url


def probe(url: str) -> tuple[int | str, str]:
    """HEAD, then GET if HEAD is not conclusive. Returns (status, note)."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(absolutise(url), method=method,
                                     headers={"User-Agent": UA, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, ("" if method == "HEAD" else "via GET")
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 501) and method == "HEAD":
                continue  # server dislikes HEAD, retry with GET
            return e.code, ""
        except urllib.error.URLError as e:
            if method == "GET":
                return "ERR", str(e.reason)[:60]
        except Exception as e:  # noqa: BLE001
            if method == "GET":
                return "ERR", str(e)[:60]
    return "ERR", "unreachable"


def check_file(path: str, do_external: bool) -> dict:
    raw = open(path, encoding="utf-8", errors="replace").read()
    links, comment = extract_links(raw)
    declares_forward = "forward-link" in comment.lower() or "forward link" in comment.lower()

    targets = []
    for u in links:
        kind = classify(u)
        if kind == "external" and not do_external:
            continue
        targets.append((u, kind))

    results = []
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(probe, u): (u, k) for u, k in targets}
            for f in concurrent.futures.as_completed(futs):
                u, k = futs[f]
                status, note = f.result()
                # Only meaningful for a link that is actually broken. Live links
                # are often named in the same comment block ("checked, returns 200").
                declared = (k == "internal" and status != 200 and declares_forward
                            and re.search(re.escape(u.replace(APEX, "")), comment))
                results.append({"url": u, "kind": k, "status": status,
                                "note": note, "declared_forward_link": bool(declared)})

    results.sort(key=lambda r: (r["kind"], str(r["status"]), r["url"]))
    return {"path": path, "declares_forward_links": declares_forward,
            "links_found": len(links), "checked": len(results), "results": results}


def verdict(rep: dict) -> int:
    worst = 0
    for r in rep["results"]:
        ok = r["status"] == 200
        if r["kind"] == "internal" and not ok:
            worst = max(worst, 0 if r["declared_forward_link"] else 2)
        elif r["kind"] == "external" and not ok:
            worst = max(worst, 1)
    return worst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--external", action="store_true",
                    help="also check outbound source citations (slower)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--site", default=None, help="site root URL, e.g. https://example.com")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    global REPO, APEX, HOST
    REPO = site_config.find_project_root(a.paths[0], a.project_root)
    project = site_config.load_project(REPO)
    APEX = (a.site or site_config.site_url(project)).rstrip("/")
    HOST = site_config.site_host({"site": {"url": APEX}})
    if not APEX:
        print("links_check: no site URL. Set site.url in project.yaml or pass --site. "
              "Root-relative internal links cannot be resolved without it.", file=sys.stderr)
        return 2
    print(f"links_check · site {APEX} · config {project.get('_source') or 'none found'}")

    worst, reports = 0, []
    for p in a.paths:
        if not os.path.exists(p):
            print(f"missing: {p}", file=sys.stderr)
            worst = 2
            continue
        rep = check_file(p, a.external)
        reports.append(rep)
        worst = max(worst, verdict(rep))

    if a.json:
        print(json.dumps(reports, indent=2))
        return worst

    for rep in reports:
        rel = os.path.relpath(rep["path"], REPO) if rep["path"].startswith(REPO) else rep["path"]
        ints = [r for r in rep["results"] if r["kind"] == "internal"]
        exts = [r for r in rep["results"] if r["kind"] == "external"]
        bad_int = [r for r in ints if r["status"] != 200 and not r["declared_forward_link"]]
        fwd = [r for r in ints if r["status"] != 200 and r["declared_forward_link"]]
        bad_ext = [r for r in exts if r["status"] != 200]

        state = "BLOCKED" if bad_int else ("warn" if bad_ext else "clean")
        print(f"{rel}   [{state}]")
        print(f"  {len(ints)} internal, {len(exts)} external checked "
              f"({rep['links_found']} links found)")

        for r in ints:
            if r["status"] == 200:
                mark = "ok  "
            elif r["declared_forward_link"]:
                mark = "fwd "
            else:
                mark = "FAIL"
            print(f"    {mark} {str(r['status']):>4}  {r['url']}"
                  + ("   [declared forward-link]" if r["declared_forward_link"] else ""))
        for r in exts:
            if r["status"] != 200:
                print(f"    warn {str(r['status']):>4}  {r['url']}  {r['note']}")

        if fwd and not bad_int:
            print(f"  {len(fwd)} declared forward-link(s). Ship those articles alongside "
                  f"this one, or drop the anchors.")
        if bad_int:
            print(f"  {len(bad_int)} broken internal link(s) NOT declared in the handover "
                  f"notes. Fix, or declare them as forward-links.")
        print()

    print({0: "PASS", 1: "PASS with external-source warnings",
           2: "FAIL, undeclared broken internal link"}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
