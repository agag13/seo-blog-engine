#!/usr/bin/env python3
"""Facts gate: block product claims the site cannot evidence.

Every product fact a site publishes has one of three statuses, and only one of
them is safe to write:

    EVIDENCED     a named source says it, and the source is linked
    BETA          true, but publishable only with the qualifier attached
    CONFLICTED    the client's own surfaces disagree with each other
    NOT PUBLISHED nobody has stated it publicly, so an article stating it is
                  the first public statement, which is a legal decision

A guard matches a claim shape, not an attribution, so it will sometimes fire on a
sentence about somebody else's product. That is the correct trade: a false
positive costs a reviewer ten seconds, and the miss it prevents cost a live
defect on a money page.

This gate exists because a leverage figure nearly shipped while four
contradictory versions of it sat on the client's own surfaces. Nobody was
careless; the number was simply in the brief and no mechanism said no.

The site's FACTS.md holds the ledger. Each fact is a `## heading` followed by a
`- status:` line, a `- source:` line, and a `- guard:` line holding a regex that
matches the claim in prose. Any draft matching the guard of a CONFLICTED or
NOT PUBLISHED fact is blocked, and the message names the fact and its source.

Usage
-----
    python3 facts_check.py drafts/perps-explained.mdx
    python3 facts_check.py --json drafts/*.mdx

Exit codes
----------
    0   no unevidenced product claims found
    1   the site has no FACTS.md, or a fact carries no guard, so the gate
        could not do its job. Reported, never silent.
    2   the draft states a CONFLICTED or NOT PUBLISHED fact

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import site_config  # noqa: E402

BLOCKING = {"CONFLICTED", "NOT PUBLISHED", "NOT_PUBLISHED", "UNPUBLISHED"}
# Publishable, but only with the qualifier attached, so the gate warns and names it.
QUALIFIED = {"BETA", "PREVIEW", "PILOT"}
KNOWN = BLOCKING | QUALIFIED | {"EVIDENCED"}


def parse_facts(path: str) -> list[dict]:
    facts, cur = [], None
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            cur = {"fact": m.group(1).strip(), "status": None, "source": None, "guard": None}
            facts.append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^\s*[-*]\s*(status|source|guard)\s*:\s*(.+?)\s*$", line, re.I)
        if m:
            cur[m.group(1).lower()] = m.group(2).strip().strip("`")
    return facts


def check(path: str, facts: list[dict]) -> dict:
    raw = open(path, encoding="utf-8", errors="replace").read()
    findings = []
    for f in facts:
        status = (f.get("status") or "").strip().upper()
        guard = f.get("guard")
        if not guard:
            findings.append({"severity": "WARN", "fact": f["fact"],
                             "message": "No `guard:` regex, so this fact cannot be enforced. "
                                        "It is documentation, not a gate."})
            continue
        try:
            m = re.search(guard, raw, re.I)
        except re.error as exc:
            findings.append({"severity": "WARN", "fact": f["fact"],
                             "message": f"guard is not a valid regex: {exc}"})
            continue
        if not m:
            continue
        if status in BLOCKING:
            findings.append({
                "severity": "BLOCK", "fact": f["fact"], "match": m.group(0)[:120],
                "message": f"Draft states a {status} fact. Source of record: "
                           f"{f.get('source') or 'none recorded'}. Either evidence it and "
                           f"update FACTS.md, or take the claim out."})
        elif status in QUALIFIED:
            findings.append({
                "severity": "WARN", "fact": f["fact"], "match": m.group(0)[:120],
                "message": f"Status is {status}. Publishable only with the {status.lower()} "
                           f"qualifier attached to the claim. Confirm it is there, in the "
                           f"sentence itself and not only in a footnote."})
        elif status not in KNOWN:
            findings.append({"severity": "WARN", "fact": f["fact"], "match": m.group(0)[:120],
                             "message": f"Status is '{status or 'unset'}', which is not a known "
                                        f"status. Known: {', '.join(sorted(KNOWN))}."})
    return {"path": path, "findings": findings}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--facts", default=None, help="explicit path to FACTS.md")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    root = site_config.find_project_root(a.paths[0], a.project_root)
    fpath = a.facts or site_config.context_file(root, "FACTS.md")
    if not fpath or not os.path.exists(fpath):
        msg = (f"facts_check: no FACTS.md under {root}. The product-fact gate did NOT run. "
               f"Every product claim in this draft is unchecked.")
        if a.json:
            print(json.dumps({"error": "no-facts-file", "root": root, "message": msg}, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 1

    facts = parse_facts(fpath)
    reports = [check(p, facts) for p in a.paths if os.path.exists(p)]
    worst = 0
    for r in reports:
        if any(f["severity"] == "BLOCK" for f in r["findings"]):
            worst = 2
        elif r["findings"] and worst < 1:
            worst = 1

    if a.json:
        print(json.dumps({"facts_file": fpath, "fact_count": len(facts),
                          "reports": reports}, indent=2))
        return worst

    print(f"facts_check · {len(facts)} facts from {fpath}\n")
    for r in reports:
        blocks = [f for f in r["findings"] if f["severity"] == "BLOCK"]
        state = "BLOCKED" if blocks else ("warn" if r["findings"] else "clean")
        print(f"{r['path']}   [{state}]")
        for f in r["findings"]:
            print(f"   {f['severity']:<5} {f['fact']}")
            print(f"         {f['message']}")
            if f.get("match"):
                print(f"         > ...{f['match']}...")
        print()
    print({0: "PASS", 1: "PASS with gaps in the ledger", 2: "FAIL, unevidenced claim"}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
