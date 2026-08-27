---
name: cms-publish
description: Publish a finished blog draft to the website's CMS as a DRAFT (never straight to live). Reads the site + CMS config from project.yaml and secrets from .env. WordPress REST is supported now (scripts/wordpress_publish.py); Strapi and Ghost adapters follow the same interface. Use when the user says "publish to WordPress/CMS", "push the draft", "send to <site>", after a post has passed the fact-check + SEO gates.
---

# CMS Publish

Push one finished article to the site's CMS **as a draft**, so a human can review and go
live. CMS-agnostic: the adapter is chosen from `project.yaml -> cms.type`.

## Preconditions (enforce these)
1. `project.yaml` and `.env` exist in the working directory (else run `project-init`).
2. The post has passed the gates the site requires (see `project.yaml -> gates`):
   fact-check for legal/medical/financial topics, plus SEO check. Do NOT publish a post
   that failed a required gate.
3. `cms.default_status` is `draft`. This skill never sets `publish` — a human does that in
   the CMS. Refuse "publish live" requests; explain the review gate.

## WordPress (supported now)
Auth = an Application Password (WP Admin → Users → Profile → Application Passwords),
stored in `.env` as `WP_USER` + `WP_APP_PASSWORD`.

Run:
```
python3 scripts/wordpress_publish.py \
  --project ./project.yaml \
  --content ./post.md \
  --meta ./post.meta.json \
  [--featured ./hero.png] [--update <post_id>] [--dry-run]
```
- `--content` accepts markdown (converted to WordPress block HTML) or `.html` (used as-is).
- `--meta` is JSON: title, slug, excerpt, seo_title, seo_description, category, author, tags, published_date.
- Always run `--dry-run` first and show the user the resolved payload (title, slug, status,
  category id, byte count) before the real call.
- The script creates the post with `status=draft` and returns the post id + the WP edit URL.

## SEO meta caveat (WordPress)
Yoast / RankMath titles + descriptions are plugin meta. The script sets them via the REST
`meta` map in `project.yaml -> cms.fields`, which works only if the site exposes those meta
keys to REST (Yoast/RankMath ≥ recent versions, or a small mu-plugin). If the site rejects
them, the script warns and the reviewer sets them in the CMS. Never fail the whole publish
over SEO meta.

## Other CMS
- **Strapi**: `POST/PUT /api/articles?status=draft`; body byte-exact in the mapped `body_html`
  field; token from `.env STRAPI_API_TOKEN`. (Adapter: `scripts/strapi_publish.py` — port the
  WordPress adapter's interface.)
- **Ghost**: Admin API (`/ghost/api/admin/posts/`), token `GHOST_ADMIN_API_KEY`.
- **markdown**: write an `.mdx`/`.md` file into the site repo's content dir for a JAMstack build.

## After publish
Report the draft URL, remind the reviewer it is not live, and hand off to `tracker-gen`
(to log it) and, once live, `request-indexing`.
