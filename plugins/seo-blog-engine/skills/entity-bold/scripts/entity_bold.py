#!/usr/bin/env python3
"""
Entity keyword bolding for the SEO blog engine.

Bolds the FIRST plain-text occurrence of each entity in a markdown file, skipping
heading lines, existing bold, and link anchors. Entities = the laws / platforms /
tools / brand terms a page should be semantically associated with.

Usage:
  python3 entity_bold.py --content post.md --entities entities.txt [--inplace] [--dry-run]

entities.txt: one entity phrase per line, in priority order. If omitted, a small
built-in candidate list is used and every match is reported for you to confirm.
"""
import argparse, re, sys

BUILTIN_HINTS = [
    # generic, high-signal ORM/legal/platform entities — override with --entities per project
    "DPDP Act", "IT Rules", "IT Act", "Bharatiya Nyaya Sanhita", "grievance officer",
    "safe harbour", "Right to be Forgotten", "cybercrime.gov.in", "StopNCII",
    "Google Business Profile", "Trustpilot", "Glassdoor", "AmbitionBox", "Justdial",
]

def bold_first(md, entities):
    lines = md.split("\n")
    done = []
    for ent in entities:
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("#"):        # skip headings
                continue
            if "**" + ent + "**" in ln:            # already bold
                break
            # skip if the only occurrence sits inside a markdown link anchor [ ... ]( ... )
            idx = ln.find(ent)
            if idx == -1:
                continue
            # crude link guard: is this occurrence inside [...] of a link on this line?
            before = ln[:idx]
            if before.count("[") > before.count("]"):
                continue
            lines[i] = ln[:idx] + "**" + ent + "**" + ln[idx + len(ent):]
            done.append(ent)
            break
    return "\n".join(lines), done

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--content", required=True)
    ap.add_argument("--entities")
    ap.add_argument("--inplace", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    md = open(a.content).read()
    if a.entities:
        ents = [l.strip() for l in open(a.entities) if l.strip() and not l.startswith("#")]
    else:
        ents = BUILTIN_HINTS
        print("No --entities file; using built-in hints. Confirm the matches below and "
              "supply a per-project entities.txt for real runs.", file=sys.stderr)
    new, done = bold_first(md, ents)
    print("bolded first occurrence of:", done or "(none matched)", file=sys.stderr)
    if a.dry_run:
        print("DRY-RUN — no file written", file=sys.stderr); return
    if a.inplace:
        open(a.content, "w").write(new)
        print("updated", a.content, file=sys.stderr)
    else:
        sys.stdout.write(new)

if __name__ == "__main__":
    main()
