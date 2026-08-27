# SEO Blog Engine

A reusable, **project-agnostic** ORM/SEO blog engine for Claude Code. The engine (skills)
stays constant across every client; each **website supplies only its own context** — brand,
voice, config, and secrets. Publish to any CMS, **WordPress first**.

> Packaging plan (diagram): https://claude.ai/code/artifact/cc131e78-b81f-4038-b260-f0d93604fffb

## The idea in one line

**Engine = shared. Context = per site.** Install this plugin once; for each website drop in
its `BRAND.md`, `VOICE.md`, `project.yaml`, and a gitignored `.env`, and the same engine
writes, fact-checks, SEO-checks, and publishes in that site's voice to that site's CMS.

```
this repo (the ENGINE — installed once)            each website (the CONTEXT — its own repo)
  plugins/seo-blog-engine/skills/*                   BRAND.md      audience, honesty rules
  templates/*   project.yaml / BRAND / VOICE / env   VOICE.md      tone, headline rules
  docs/DEPENDENCIES.md                               project.yaml  site · CMS · GSC · cadence
                                                     .env          secrets — GITIGNORED
```

## Install (each teammate, once)

```bash
# in Claude Code
/plugin marketplace add agag13/seo-blog-engine
/plugin install seo-blog-engine
```

Then install the skills this engine calls (writing, SEO, fact-check, diagram) —
see [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md).

## Onboard a new website

From inside that website's own project folder (not this repo):

```
project-init          # interviews you, writes BRAND.md / VOICE.md / project.yaml / .env.example
cp .env.example .env  # then fill in the CMS token / app password
```

## Run one article

```
/blog-pipeline <topic, or path to a brief / Google-Doc export>
```

`pipeline-run` executes in order and **stops at the human gates**:

1. Draft (`blog-write`/`blog-rewrite`, brand voice) →
2. SEO (`blog-seo-check`, `blog-cannibalization`) →
3. Fact-check (`blog-factcheck` + `blog-researcher`) → produces the VERIFY + LAWYER lists →
4. Polish (`blog-analyze`, `humanizer`, `entity-bold`, `blog-image`) →
5. `cms-publish` → CMS **draft** (never live).

**GATE 1** the SEO owner reviews the flagged list (not the whole article). **GATE 2** the SEO
owner approves go-live after the technical owner publishes to a temp URL. Then indexing +
`tracker-gen` logs results.

## What's in the engine

| Skill | Does |
|---|---|
| `project-init` | onboard a new website's context |
| `brand-loader` | load BRAND/VOICE/project.yaml so writing obeys the site |
| `cms-publish` | push a finished draft to the CMS (WordPress adapter included) |
| `entity-bold` | bold the first mention of key entities |
| `pipeline-run` | the end-to-end two-gate flow |
| `tracker-gen` | the shareable content dashboard |

Plus the MIT `blog-*` / `seo-*` / `diagram-design` skills it orchestrates (installed
separately — see `docs/DEPENDENCIES.md`).

## Publishing adapters

- **WordPress** — supported now (`skills/cms-publish/scripts/wordpress_publish.py`, stdlib-only,
  Application-Password auth, creates drafts, best-effort Yoast/RankMath meta).
- **Strapi / Ghost / markdown** — same interface, adapters to port next.

## Golden rules

- **Secrets never enter this repo.** `.env` is gitignored; the engine reads secrets from the
  environment. Only `.env.example` is committed.
- **Publish only to `draft`.** Going live is a human action in the CMS.
- **Required gates are non-negotiable** for legal/medical/financial topics (`project.yaml → gates`).

## License

MIT (this plugin). It depends on separately-licensed skills — see `LICENSE` and
`docs/DEPENDENCIES.md`.

## Roadmap

- [ ] WordPress adapter hardening (Yoast/RankMath REST meta, media alt, categories/tags create)
- [ ] Strapi + Ghost adapters
- [ ] `brand-loader` → auto-derive an entity list for `entity-bold`
- [ ] `request-indexing` skill (GSC) + a results-loop into `tracker-gen`
- [ ] vendor the MIT blog engine for a one-command self-contained install
