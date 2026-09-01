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

**A gate that could not run blocks.** It is not a gate that passed, and until v2 it
was folded into the same exit code as "there are some warnings", which meant the
most important gate in the set could quietly check nothing and the article shipped
anyway.

To proceed without a gate you have to name it:

    --allow-skipped serp,schema

There is no blanket override on purpose. Naming the gate puts the decision in the
command and in the log, so "we shipped without the schema check" is a thing
somebody chose rather than a thing that happened.

Usage
-----
    python3 run_gates.py --mdx drafts/x.mdx --html drafts/x.html \\
                         --serp scratch/x.serp.json --keyword "what is a perp dex"
    python3 run_gates.py --mdx drafts/x.mdx --allow-skipped serp,schema --json

Build the HTML first, or the schema gate has nothing to read:

    python3 ../../cms-publish/scripts/build_page.py --mdx drafts/x.mdx

Exit codes
----------
    0   every gate ran and passed
    1   every gate ran; warnings only, or a skip you acknowledged
    2   a gate blocked, OR a gate could not run and was not acknowledged
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"

GATE_NAMES = {"serp", "voice", "facts", "links", "schema"}


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
    ap.add_argument("--allow-skipped", default="",
                    help="comma-separated gate names you are knowingly running without, "
                         "e.g. `serp,schema`. Anything not named here still blocks. There "
                         "is deliberately no blanket override: naming the gate puts the "
                         "decision in the command and in the log.")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    allowed = {g.strip() for g in a.allow_skipped.split(",") if g.strip()}
    unknown = allowed - GATE_NAMES
    if unknown:
        print(f"--allow-skipped names a gate that does not exist: {', '.join(sorted(unknown))}. "
              f"Known gates: {', '.join(sorted(GATE_NAMES))}.", file=sys.stderr)
        return 2

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
        for g in ("voice", "facts", "links"):
            skipped.append((g, "no --mdx given."))

    if a.html:
        src = ["--mdx", a.mdx] if a.mdx else []
        results.append(run("schema", "schema_check.py", [a.html, *src, *root]))
    else:
        skipped.append(("schema", "no --html given. Build it with cms-publish/scripts/"
                                  "build_page.py. Without it the JSON-LD is unchecked and "
                                  "the three-surface FAQ match, the one check that detects "
                                  "cross-article contamination, did not run."))

    # A gate that could not run is not a gate that passed. It blocks unless the
    # caller named it in --allow-skipped, which is the whole change in v2: the
    # engine used to fold "could not run" into the same exit code as "there are
    # warnings", and the pipeline continued on both.
    blocked = [r["gate"] for r in results if min(r["code"], 2) == 2]
    unacked = [g for g, _ in skipped if g not in allowed]
    acked = [g for g, _ in skipped if g in allowed]

    if blocked:
        worst, reason = 2, "a gate blocked: " + ", ".join(blocked)
    elif unacked:
        worst, reason = 2, ("a gate could not run and was not acknowledged: "
                            + ", ".join(unacked)
                            + ". Fix it, or re-run naming it in --allow-skipped.")
    elif any(min(r["code"], 2) == 1 for r in results) or acked:
        worst, reason = 1, "warnings only" + (
            ", plus acknowledged skips: " + ", ".join(acked) if acked else "")
    else:
        worst, reason = 0, "every gate ran and passed"

    if a.json:
        print(json.dumps({"verdict": worst, "verdict_reason": reason, "gates": results,
                          "skipped": [{"gate": g, "why": w,
                                       "acknowledged": g in allowed} for g, w in skipped]},
                         indent=2))
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
        tag = "SKIPPED" if g in allowed else "NOT RUN"
        print(f"[{tag}] {g}\n        {w}")
        if g in allowed:
            print(f"        Acknowledged via --allow-skipped. This gate checked nothing.")
        print("-" * 72)
    print({0: "ALL GATES PASS",
           1: "PASS WITH WARNINGS. Read above before shipping.",
           2: "BLOCKED. This article does not ship."}[worst])
    print(f"reason: {reason}")
    return worst


if __name__ == "__main__":
    sys.exit(main())
