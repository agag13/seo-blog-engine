#!/usr/bin/env python3
"""Publish target for code-based sites (Next.js, Astro, Hugo, Eleventy).

Writes two files and stops:

    <out>/<slug>.mdx    the article source, frontmatter intact
    <out>/<slug>.html   the sibling carrying the JSON-LD and the visible FAQ

**It does not commit and it does not deploy.** That is the same rule the
WordPress adapter follows by only ever creating drafts. Going live is a human
action, and on a code-based site "live" means a commit, so the engine does not
make one.

The sibling HTML is not decoration. `schema_check.py` matches every FAQ answer
across three surfaces, and the HTML is the second of them. Emitting the source
without it means the schema gate cannot run, which is not the same as passing.

Usage
-----
    python3 markdown_publish.py --mdx drafts/x.mdx --out content/blog
    python3 markdown_publish.py --mdx drafts/x.mdx --out content/blog --html-only

Exit codes
----------
    0   both files written
    1   written, with a warning worth reading
    2   refused. Nothing written.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GATES = os.path.abspath(os.path.join(HERE, "..", "..", "quality-gates", "scripts"))
if GATES not in sys.path:
    sys.path.insert(0, GATES)
from site_config import frontmatter  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mdx", required=True)
    ap.add_argument("--html", help="the sibling HTML. Default: same basename next to --mdx")
    ap.add_argument("--out", required=True, help="destination directory in the site repo")
    ap.add_argument("--slug", help="override the slug. Default: the source basename")
    ap.add_argument("--force", action="store_true", help="overwrite an existing file")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if not os.path.exists(a.mdx):
        print(f"missing: {a.mdx}", file=sys.stderr)
        return 2

    raw = open(a.mdx, encoding="utf-8", errors="replace").read()
    fm, _ = frontmatter(raw)   # shared with build_page, so both read a draft alike
    slug = a.slug or fm.get("slug") or os.path.splitext(os.path.basename(a.mdx))[0]

    warnings = []
    status = (fm.get("draft") or "").lower()
    if status not in ("true", "1", "yes"):
        warnings.append("frontmatter does not carry `draft: true`. This target never "
                        "publishes live, but the site's own build might.")

    html_src = a.html or (os.path.splitext(a.mdx)[0] + ".html")
    have_html = os.path.exists(html_src)
    if not have_html:
        warnings.append(f"no sibling HTML at {html_src}. Build it first with "
                        f"build_page.py, or the JSON-LD and the three-surface FAQ match "
                        f"were never verified for this article.")

    os.makedirs(a.out, exist_ok=True)
    written = []
    for src, ext in ((a.mdx, os.path.splitext(a.mdx)[1] or ".mdx"),
                     (html_src if have_html else None, ".html")):
        if not src:
            continue
        dst = os.path.join(a.out, slug + ext)
        if os.path.exists(dst) and not a.force:
            print(f"refusing to overwrite {dst}. Pass --force if that is intended.",
                  file=sys.stderr)
            return 2
        shutil.copyfile(src, dst)
        written.append(dst)

    out = {"slug": slug, "written": written, "committed": False, "deployed": False,
           "warnings": warnings,
           "next": "Review, then a human commits. The engine does not commit or deploy."}
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"markdown_publish · {slug}")
        for w in written:
            print(f"  wrote {w}")
        for w in warnings:
            print(f"  WARN  {w}")
        print("\n  not committed, not deployed. A human does that.")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
