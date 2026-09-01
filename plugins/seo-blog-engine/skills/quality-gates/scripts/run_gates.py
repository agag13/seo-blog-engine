#!/usr/bin/env python3
"""Run every enforcement gate over one article and return a blocking exit code.

Advisory scorers do not change behaviour. A 100-point score that says 78 gets
read as "good enough" and the article ships. Only a non-zero exit code stops it,
so this runner exists to give `pipeline-run` exactly one thing to check.

Gates, in the order they run:

    serp     serp_gate.py     did the live SERP allow this keyword at all
    voice    voice_check.py   cadence bands, banned structures, partners
    facts    facts_check.py   product claims against the FACTS.md ledger
    links    links_check.py   internal links resolve or are declared forward-links
    schema   schema_check.py  JSON-LD valid, FAQ byte-matched across three surfaces

A gate that could not run is never treated as a gate that passed. Missing config
raises the run to at least "incomplete", and the summary says which gate was
blind and why.

Usage
-----
    python3 run_gates.py --mdx drafts/x.mdx --html out/x.html \\
                         --serp scratch/x.serp.json --keyword "what is a perp dex"
    python3 run_gates.py --mdx drafts/x.mdx --json

Exit codes
----------
    0   every gate that ran, passed
    1   warnings only, or a gate could not run
    2   at least one gate blocked. The article does not ship.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"


def run(name: str, script: str, args: list[str]) -> dict:
    cmd = [PY, os.path.join(HERE, script), *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"gate": name, "code": 1, "ran": False,
                "note": "timed out after 300s; treat as NOT RUN, not as passed",
                "stdout": "", "stderr": ""}
    return {"gate": name, "code": p.returncode, "ran": True,
            "cmd": " ".join(cmd), "stdout": p.stdout, "stderr": p.stderr}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mdx", help="the draft source file (.mdx/.md)")
    ap.add_argument("--html", help="the rendered HTML carrying the JSON-LD")
    ap.add_argument("--serp", help="saved live SERP JSON for the target keyword")
    ap.add_argument("--keyword")
    ap.add_argument("--profile", help="voice profile id override")
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--external-links", action="store_true",
                    help="also probe outbound citations (slower)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = ["--project-root", a.project_root] if a.project_root else []
    results, skipped = [], []

    if a.serp:
        kw = ["--keyword", a.keyword] if a.keyword else []
        results.append(run("serp", "serp_gate.py", [a.serp, *kw, *root]))
    else:
        skipped.append(("serp", "no --serp given. The keyword was never checked against a live "
                                "SERP, which is the check that killed three of twelve keywords "
                                "that all looked easy on difficulty alone."))

    if a.mdx:
        prof = ["--profile", a.profile] if a.profile else []
        results.append(run("voice", "voice_check.py", [a.mdx, *prof, *root]))
        results.append(run("facts", "facts_check.py", [a.mdx, *root]))
        ext = ["--external"] if a.external_links else []
        results.append(run("links", "links_check.py", [a.mdx, *ext, *root]))
    else:
        skipped.append(("voice/facts/links", "no --mdx given"))

    if a.html:
        results.append(run("schema", "schema_check.py", [a.html, *root]))
    else:
        skipped.append(("schema", "no --html given. JSON-LD and the three-surface FAQ match "
                                  "were not verified."))

    worst = 0
    for r in results:
        worst = max(worst, min(r["code"], 2))
    if skipped:
        worst = max(worst, 1)

    if a.json:
        print(json.dumps({"verdict": worst, "gates": results,
                          "skipped": [{"gate": g, "why": w} for g, w in skipped]}, indent=2))
        return worst

    print("=" * 72)
    for r in results:
        state = {0: "PASS", 1: "WARN", 2: "BLOCK"}.get(min(r["code"], 2), "?")
        print(f"[{state:^5}] {r['gate']}")
        body = (r["stdout"] or "").rstrip()
        if body:
            print("\n".join("        " + ln for ln in body.splitlines()))
        if r["stderr"].strip():
            print("\n".join("   err  " + ln for ln in r["stderr"].rstrip().splitlines()))
        print("-" * 72)
    for g, w in skipped:
        print(f"[NOT RUN] {g}\n        {w}")
        print("-" * 72)
    print({0: "ALL GATES PASS", 1: "INCOMPLETE or WARNINGS. Read above before shipping.",
           2: "BLOCKED. This article does not ship."}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
