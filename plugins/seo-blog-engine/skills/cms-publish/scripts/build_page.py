#!/usr/bin/env python3
"""Build the sibling HTML that carries the visible FAQ and the JSON-LD.

This script exists because the strongest gate in the engine could not run.
`schema_check.py` matches every FAQ answer across three surfaces, and one of
those surfaces is an HTML file that nothing in the engine produced. The
publisher only ever *copied* an HTML file if one happened to exist already, so
on a normal article the schema gate reported NOT RUN and the pipeline carried on.

The design point, and it is the whole point:

    **Every surface is generated from one parse of one file.**

The MDX is read once. The frontmatter, the body and the FAQ pairs become objects
in memory, and the visible HTML FAQ and the FAQPage JSON-LD are both rendered
from those same objects. Two surfaces built from one source cannot disagree.

That changes what `schema_check.py` is for. It stops being the only thing between
us and a mismatch, and becomes a regression test that catches drift introduced
afterwards by a hand edit. That is a smaller and far more honest job for it.

**The output path is derived from the source filename and cannot be overridden
per file.** Only the directory is configurable. A build that cannot be told what
to call its output cannot be pointed at a sibling article's file, which is the
collision that once put one article's FAQ block into two others.

By default the HTML is written next to the MDX, because `schema_check.py` finds
the third surface by looking for a sibling `.mdx`. Use `--out` to write elsewhere
and pass `--mdx` to `schema_check.py` so the third surface is still checked.

What this renders is a faithful carrier for the copy and the structured data, not
a production template. The site's own build owns the real page.

Usage
-----
    python3 build_page.py --mdx drafts/what-is-a-perp-dex.mdx
    python3 build_page.py --mdx drafts/x.mdx --out out/ --json

Exit codes
----------
    0   built, nothing worth flagging
    1   built, with a warning that affects search or rich results
    2   refused. Nothing written
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GATES = os.path.abspath(os.path.join(HERE, "..", "..", "quality-gates", "scripts"))
for _p in (HERE, GATES):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import site_config  # noqa: E402


# --------------------------------------------------------------------------- inline

def _inline_pairs():
    """Markdown inline constructs, as (regex, html_repl, text_repl).

    Both columns are applied to the SAME input string, so the rendered HTML and
    the plain text used in JSON-LD are two views of one value rather than two
    independent transformations that could drift.
    """
    return [
        (re.compile(r"`([^`]+)`"), r"<code>\1</code>", r"\1"),
        (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>', r"\1"),
        (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>", r"\1"),
        (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])"), r"<em>\1</em>", r"\1"),
    ]


def inline_html(s: str) -> str:
    out = _html.escape(s, quote=False)
    for pat, hrep, _ in _inline_pairs():
        out = pat.sub(hrep, out)
    return out


def inline_text(s: str) -> str:
    """Plain text form. This is what goes into JSON-LD, and it is exactly what
    `schema_check.text_of()` will recover from the rendered HTML."""
    out = s
    for pat, _, trep in _inline_pairs():
        out = pat.sub(trep, out)
    return re.sub(r"\s+", " ", _html.unescape(out)).strip()


# --------------------------------------------------------------------------- parse

FAQ_HEADING = re.compile(r"(?im)^#{2,3}\s+.*\bFAQ\b.*$")


def strip_comments(body: str) -> str:
    return re.sub(r"(?s)\{/\*.*?\*/\}", "", body)


def split_faq(body: str) -> tuple:
    """Return (body_without_faq, [(question, answer), ...]).

    House format, already in use: an `## ... FAQ` heading, then each question on
    its own line in bold, then its answer as the following paragraph.
    """
    m = FAQ_HEADING.search(body)
    if not m:
        return body, []

    head, tail = body[:m.start()], body[m.end():]
    # A later top-level heading ends the FAQ section.
    nxt = re.search(r"(?m)^##\s+(?!.*\bFAQ\b)", tail)
    faq_src, after = (tail[:nxt.start()], tail[nxt.start():]) if nxt else (tail, "")

    pairs = []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", faq_src) if b.strip()]
    for b in blocks:
        lines = [ln for ln in b.splitlines() if ln.strip()]
        if not lines:
            continue
        q = re.match(r"^\s*\*\*(.+?)\*\*\s*$", lines[0])
        if not q:
            continue
        answer = " ".join(ln.strip() for ln in lines[1:]).strip()
        if answer:
            pairs.append((q.group(1).strip(), answer))
    return head + after, pairs


def render_body(body: str) -> str:
    """Markdown to HTML, deliberately small. Inline SVG passes through untouched,
    because a diagram in the source is part of the article."""
    out, i = [], 0
    chunks = re.split(r"(?s)(<svg\b.*?</svg>|```.*?```)", body)
    for chunk in chunks:
        i += 1
        if not chunk.strip():
            continue
        if chunk.lstrip().startswith("<svg"):
            out.append(chunk)
            continue
        if chunk.lstrip().startswith("```"):
            code = re.sub(r"(?s)\A```[a-z]*\n?|```\Z", "", chunk)
            out.append("<pre><code>%s</code></pre>" % _html.escape(code))
            continue
        for block in re.split(r"\n\s*\n", chunk):
            block = block.strip()
            if not block:
                continue
            h = re.match(r"^(#{1,6})\s+(.*)$", block)
            if h:
                lvl = len(h.group(1))
                out.append("<h%d>%s</h%d>" % (lvl, inline_html(h.group(2).strip()), lvl))
                continue
            if re.match(r"^\s*[-*]\s+", block):
                items = [inline_html(re.sub(r"^\s*[-*]\s+", "", ln).strip())
                         for ln in block.splitlines() if ln.strip()]
                out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % x for x in items))
                continue
            if re.match(r"^\s*\d+\.\s+", block):
                items = [inline_html(re.sub(r"^\s*\d+\.\s+", "", ln).strip())
                         for ln in block.splitlines() if ln.strip()]
                out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % x for x in items))
                continue
            if block.startswith(">"):
                q = " ".join(re.sub(r"^>\s?", "", ln) for ln in block.splitlines())
                out.append("<blockquote><p>%s</p></blockquote>" % inline_html(q.strip()))
                continue
            if block.lstrip().startswith("|"):
                out.append(render_table(block))
                continue
            if block.lstrip().startswith("<"):
                out.append(block)
                continue
            out.append("<p>%s</p>" % inline_html(" ".join(
                ln.strip() for ln in block.splitlines())))
    return "\n".join(out)


def render_table(block: str) -> str:
    rows = [r.strip() for r in block.splitlines() if r.strip().startswith("|")]
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    cells = [c for c in cells if not all(re.fullmatch(r":?-{2,}:?", x or "") for x in c)]
    if not cells:
        return ""
    head, body = cells[0], cells[1:]
    th = "".join("<th>%s</th>" % inline_html(c) for c in head)
    tb = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline_html(c) for c in r)
                 for r in body)
    return ("<div class=\"tablewrap\"><table><thead><tr>%s</tr></thead>"
            "<tbody>%s</tbody></table></div>" % (th, tb))


# --------------------------------------------------------------------------- emit

CSS = """:root{color-scheme:light dark}
body{margin:0 auto;max-width:44rem;padding:2rem 1.25rem;
 font:16px/1.65 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:2rem;line-height:1.2}h2{margin-top:2.25rem}
code{font-size:.9em}pre{overflow-x:auto;padding:1rem;background:#0001;border-radius:6px}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%}
th,td{border:1px solid #8884;padding:.5rem .6rem;text-align:left;vertical-align:top}
details{border-top:1px solid #8884;padding:.75rem 0}
summary{cursor:pointer;font-weight:600}
details>p{margin:.6rem 0 0}
figure{margin:1.5rem 0}svg{max-width:100%;height:auto}
.built{margin-top:3rem;font-size:.8rem;opacity:.6;border-top:1px solid #8884;padding-top:1rem}
"""


def build(mdx_path: str, project: dict, out_dir: str | None) -> dict:
    raw = open(mdx_path, encoding="utf-8", errors="replace").read()
    fm, body = site_config.frontmatter(raw)
    body = strip_comments(body)
    body, faq = split_faq(body)

    slug = fm.get("slug") or os.path.splitext(os.path.basename(mdx_path))[0]
    site = project.get("site") or {}
    site_name = site.get("name") if isinstance(site, dict) else None
    base = site_config.site_url(project)
    root_slugs = str((site or {}).get("root_slugs", "")).lower() in ("true", "1", "yes")
    url = "%s/%s/" % (base, slug) if root_slugs else "%s/blog/%s/" % (base, slug)

    warnings = []
    title = fm.get("title") or slug
    desc = fm.get("description") or ""
    if not desc:
        warnings.append("no `description` in frontmatter, so the page has no meta description.")
    if not fm.get("pubDate"):
        warnings.append("no `pubDate` in frontmatter. BlogPosting requires datePublished.")
    if not base:
        warnings.append("no site.url in project.yaml, so the canonical URL is relative "
                        "and the schema gate cannot check its host.")

    image = fm.get("cover") or ""
    if image.startswith("./") or image.startswith("../"):
        # A repo-relative cover has no production URL yet. Say so rather than
        # emitting a path that will 404 inside structured data.
        warnings.append("`cover` is a repo-relative path (%s), so BlogPosting ships with "
                        "no `image` and Article rich results will not fire. Supply a "
                        "production URL before publish." % image)
        image = ""
    elif not image:
        warnings.append("no `cover` in frontmatter. BlogPosting has no `image`, so Article "
                        "rich results will not fire.")

    author = fm.get("author") or ""
    if not author:
        warnings.append("no `author` in frontmatter.")
    else:
        warnings.append("byline is set to %r. A named author with no bio and no photo on "
                        "the live site scores worse than no named author at all. Confirm "
                        "both exist before publish." % author)

    # ---- the single source the two surfaces are rendered from ----------------
    faq_objs = [{"q_html": inline_html(q), "q_text": inline_text(q),
                 "a_html": inline_html(a), "a_text": inline_text(a)} for q, a in faq]

    faq_html = ""
    if faq_objs:
        items = "\n".join(
            "<details><summary>%s</summary><p>%s</p></details>"
            % (f["q_html"], f["a_html"]) for f in faq_objs)
        faq_html = '\n<section class="faq">\n<h2>FAQ</h2>\n%s\n</section>' % items
    else:
        warnings.append("no FAQ block found in the MDX, so no FAQPage is emitted. The "
                        "three-surface FAQ check has nothing to compare.")

    graph = [n for n in (
        blogposting(title, desc, fm, url, author, image, site_name),
        breadcrumbs(base, title, url, root_slugs),
        {"@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": f["q_text"],
                         "acceptedAnswer": {"@type": "Answer", "text": f["a_text"]}}
                        for f in faq_objs]} if faq_objs else None,
    ) if n]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph},
                        indent=2, ensure_ascii=False)

    page = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">{ogimg}
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{jsonld}
</script>
<style>{css}</style>
</head>
<body>
<article>
<h1>{h1}</h1>
{body}{faq}
</article>
<p class="built">Built by seo-blog-engine build_page.py from {src}. Draft, not the
production template. Edit the MDX, never this file: the FAQ here is generated from it and
schema_check.py will block if the two drift apart.</p>
</body>
</html>
""".format(lang=(site.get("locale") or "en").split("-")[0] if isinstance(site, dict) else "en",
           title=_html.escape(title, quote=True), desc=_html.escape(desc, quote=True),
           url=_html.escape(url, quote=True),
           ogimg=('\n<meta property="og:image" content="%s">' % _html.escape(image, quote=True))
                 if image else "",
           jsonld=jsonld, css=CSS, h1=inline_html(title),
           body=render_body(body), faq=faq_html,
           src=_html.escape(os.path.basename(mdx_path)))

    dest_dir = out_dir or os.path.dirname(os.path.abspath(mdx_path))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, slug + ".html")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)

    return {"slug": slug, "html": dest, "mdx": os.path.abspath(mdx_path),
            "faq_count": len(faq_objs), "canonical": url, "warnings": warnings}


def blogposting(title, desc, fm, url, author, image, site_name) -> dict:
    n = {"@type": "BlogPosting", "headline": title, "description": desc,
         "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "url": url}
    if fm.get("pubDate"):
        n["datePublished"] = fm["pubDate"]
        n["dateModified"] = fm.get("updatedDate") or fm["pubDate"]
    if author:
        n["author"] = {"@type": "Person", "name": author}
    if site_name:
        n["publisher"] = {"@type": "Organization", "name": site_name}
    if image:
        n["image"] = image
    return n


def breadcrumbs(base, title, url, root_slugs) -> dict | None:
    if not base:
        return None
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"}]
    if not root_slugs:
        items.append({"@type": "ListItem", "position": 2, "name": "Blog",
                      "item": base + "/blog/"})
    items.append({"@type": "ListItem", "position": len(items) + 1, "name": title,
                  "item": url})
    return {"@type": "BreadcrumbList", "itemListElement": items}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mdx", required=True, help="the draft source file")
    ap.add_argument("--out", default=None,
                    help="output DIRECTORY. The filename always comes from the source. "
                         "Default: alongside the MDX, so the three-surface check works.")
    ap.add_argument("--json", action="store_true")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    if not os.path.exists(a.mdx):
        print("missing: %s" % a.mdx, file=sys.stderr)
        return 2

    root = site_config.find_project_root(a.mdx, a.project_root)
    project = site_config.load_project(root)
    rep = build(a.mdx, project, a.out)

    if a.json:
        print(json.dumps(rep, indent=2))
        return 1 if rep["warnings"] else 0

    print("build_page · %s" % rep["slug"])
    print("  wrote     %s" % rep["html"])
    print("  canonical %s" % rep["canonical"])
    print("  FAQ       %d question(s), rendered into the visible block and the "
          "JSON-LD from one source" % rep["faq_count"])
    for w in rep["warnings"]:
        print("  WARN      %s" % w)
    if a.out:
        print("\n  --out was used, so the HTML is not beside the MDX. Pass --mdx %s to "
              "schema_check.py or its third-surface check will not run." % rep["mdx"])
    return 1 if rep["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main())
