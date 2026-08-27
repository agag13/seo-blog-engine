# Dependencies

This plugin is the **orchestration + publishing layer**. It calls a set of
already-existing skills that do the writing, SEO, and quality work. Those skills
are installed separately so they stay updatable from their own sources and so we
respect their licenses.

## Skill families this engine calls

| Skill(s) | Family | License | Install from |
|---|---|---|---|
| `blog-write`, `blog-rewrite`, `blog-brief`, `blog-outline`, `blog-strategy`, `blog-cluster`, `blog-calendar` | blog engine | MIT | the `blog` toolset (vendor with its LICENSE, or install from its source) |
| `blog-factcheck`, `blog-analyze`, `blog-seo-check`, `blog-cannibalization`, `blog-schema`, `blog-image`, `blog-geo` | blog engine | MIT | same as above |
| `diagram-design` | diagram | MIT | same toolset |
| `humanizer` | anthropic-skills | (marketplace) | `anthropics/claude-plugins-official` |
| `keyword-research` | anthropic-skills | (marketplace) | `anthropics/claude-plugins-official` |

## Agents this engine uses
- `blog-researcher` — source discovery + tier-1/2 verification (drives `cms-publish`'s pre-publish fact-check).
- `blog-reviewer` — 100-point quality scoring.

## Two ways to satisfy the dependencies

**A. Reference (recommended while the blog engine has an upstream):**
Install the `blog`/`seo`/`diagram-design` toolset and the official marketplace
plugins on each machine. This plugin then calls them by name.

**B. Vendor the MIT engine into this repo (for a fully self-contained install):**
Copy the MIT-licensed `blog-*` / `seo-*` / `diagram-design` skill folders into
`plugins/seo-blog-engine/skills/`, and **keep each skill's own LICENSE file and
attribution**. Do NOT vendor the marketplace (non-MIT) skills — reference those.

## Runtime
- Python 3.11+ (publishing scripts, quality scoring)
- `requests` is optional — the WordPress adapter uses only the Python standard library.
