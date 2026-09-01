---
name: cms-publish
description: Push a finished, gate-passed article to its destination as a DRAFT. Two targets - a code-based site (Next.js, Astro) receives an .md/.mdx file plus a sibling .html carrying the JSON-LD, uncommitted and undeployed; a WordPress site is pushed through the Novamira MCP as a draft post. Never publishes live. Use when the user says "publish this", "push the draft", "send it to WordPress", or a pipeline reaches its publish step.
---

# CMS publish

**One rule that never bends: publish as a draft.** Going live is a human action, in the CMS,
by a person who looked at the page. That rule was already here and it stays.

**Second rule: the gates run first.** `run_gates.py` must exit 0 or 1 before this skill does
anything. A verdict of 2 does not reach this step, and since v2 that includes a gate that
could not run.

**Third rule: build before you gate.** `build_page.py` produces the sibling HTML carrying
the JSON-LD. Without it the schema gate has nothing to read, which is not the same as the
schema being fine.

## Which target

Read `project.yaml → cms.type`.

| `cms.type` | Target | What happens |
|---|---|---|
| `markdown` | code-based site | two files written into `cms.output_dir`. No commit, no deploy |
| `wordpress` | Novamira MCP | one draft post, plus SEO meta where the site's plugin supports it |
| `strapi`, `ghost` | not built | say so plainly and stop |

## Target 1, code-based sites (Next.js, Astro, Hugo, Eleventy)

```bash
python3 scripts/build_page.py       --mdx drafts/<slug>.mdx
python3 scripts/markdown_publish.py --mdx drafts/<slug>.mdx --out <site>/content/blog
```

`build_page.py` generates the HTML; `markdown_publish.py` moves the pair into the site,
writing **two** files:

- `<slug>.mdx`, the article source with frontmatter intact
- `<slug>.html`, the sibling carrying the JSON-LD and the visible FAQ

**The sibling HTML is not optional and it is not decoration.** `schema_check.py` matches
every FAQ answer across three surfaces, and this file is one of them. Shipping the source
alone means the schema gate has nothing to check, which is not the same as the schema being
fine.

**Do not commit and do not deploy.** On a code-based site "live" is a commit, so the engine
does not make one. The script reports `committed: false, deployed: false` and names the two
paths. A human reviews and commits.

It refuses to overwrite an existing file unless `--force` is passed, and warns when the
frontmatter does not carry `draft: true`, because the site's own build may not be as careful
as this script is.

## Target 2, WordPress through the Novamira MCP

### Check which server connects, at runtime, before publishing

**Every site has its own Novamira server**, so a machine usually has several configured and
**they are not all up**. That is normal rather than an incident: some are local, some are
retired. When this was built, three were configured and only one answered; the other two
failed to connect, one with `ENOTFOUND`.

So: call `mcp-adapter-discover-abilities` on **the server this site's `project.yaml` points
at**, before anything else. If it answers, that server is live, and the ability list tells
you what this particular install supports, which genuinely differs: one site runs Rank Math,
another Yoast, another neither.

**A dead server is reported, never skipped.** Say which server, say what the failure was,
and stop. Do not fall back to a different site's server, and do not carry on to the next
pipeline step as if the publish happened. An article that silently did not publish is worse
than one that failed loudly, because nobody goes looking for it.

### Publishing

1. `novamira/create-post` with `status: "draft"`. Never `publish`.
2. SEO meta through whichever plugin the install actually has. On the verified server that
   is **Rank Math**, so `novamira/rank-math-edit-post-seo` for the title, meta description
   and focus keyword, and `novamira/rank-math-edit-post-schema` for the schema type. Yoast
   sites take the Yoast fields instead. Read the discovery output; do not assume.
3. Return the edit URL.

## Byline, and the thing that makes it worse than nothing

If the article carries a named author, the site must also carry that author's **bio and
photo**. Measured on the reference account, a named author without them scored roughly
**8 points worse on authoritativeness than no named author at all**.

So: publish with a byline only when the bio and the photo exist. If they do not, either
publish unbylined or warn loudly in the report. Do not add a name and hope.

## Guardrails

- Draft status only. Every target. No exceptions and no flag to override it.
- Gates first. A verdict of 2 does not reach this skill.
- One article per run.
- Never publish a page whose sibling HTML is missing, without saying that the schema and
  the three-surface FAQ match went unverified.
- Never commit or deploy on a code-based site.
