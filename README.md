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
this repo (the ENGINE — installed once)      each website (the CONTEXT — its own repo)
  plugins/seo-blog-engine/skills/*             BRAND.md       audience, honesty rules
  templates/*                                  VOICE.md       tone, headline rules
  examples/worked-example/  a filled-in one    PARTNERS.md    never write against these
  docs/DEPENDENCIES.md                         FACTS.md       every fact + status + source
  docs/PROVIDERS.md                            project.yaml   site · CMS · gates
                                               config/voice-fingerprint.yaml  measured bands
                                               .env           secrets — GITIGNORED
```

Two of those context files are new and they carry the rules the engine cannot infer.
**`PARTNERS.md`** is parsed, not read: a prose honesty rule does not stop an agent writing
"alternatives to X" about a partner. **`FACTS.md`** gives every product claim a status of
EVIDENCED, BETA, CONFLICTED or NOT PUBLISHED, and the last two block.

> **New here? Read [`ORIENTATION.md`](ORIENTATION.md) first** — what this is, what each
> part does and why, and what is deliberately not built yet. Fifteen minutes.
>
> **Setting it up? Then [`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md).**
> It is the complete list: what each person installs, which MCP servers are shared and which
> are per website, what the client has to supply, and how to check the setup before the first
> run. `examples/worked-example/` is a complete filled-in site context.

## Install (each teammate, once)

```bash
# in Claude Code
/plugin marketplace add agag13/seo-blog-engine
/plugin install seo-blog-engine
```

Then install the skills this engine calls (writing, SEO, fact-check, diagram) —
see [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md) — and `pip3 install pyyaml`, without which
the voice gate falls back to bands nobody measured.

## Onboard a new website

From inside that website's own project folder (not this repo):

```
project-init          # interviews you, writes the context files
cp .env.example .env  # then fill in the credentials

python3 <plugin>/skills/quality-gates/scripts/doctor.py
# 0 ready · 1 runnable but a gate cannot check anything · 2 not ready
```

`doctor.py` is the answer to "what still needs filling in". It reports READY / warn / STOP
per item with the fix for each. **Exit 1 is the state to watch**: the pipeline runs, an
article comes out, and one of the gates is standing there with nothing to compare against.

**WordPress is per site.** Each website has its own Novamira install and its own MCP server
entry; whoever owns the site connects it. The engine checks at run time which server answers
and reports a dead one rather than skipping the publish.

## Run one article

```
/blog-pipeline <topic, or path to a brief / Google-Doc export>
```

`pipeline-run` executes in order, **fails on a blocking gate**, and **stops at the human gates**:

0. **`intake`** — rewrite or fresh? keyword, site, objective. Confirm the plan, wait for approval →
1. **`research-chain`** — providers in order, recording which one answered →
2. **SERP gate** — reject on who ranks, before a word is written →
3. Draft (`blog-write`/`blog-rewrite`, brand voice) →
4. **`build_page`** — render the sibling HTML carrying the JSON-LD →
5. **`quality-gates`** — voice, facts, links, three-surface schema. Exit 2 ends the run →
6. Fact-check (`blog-factcheck` + `blog-researcher`) → the VERIFY + LAWYER lists →
7. Polish (`blog-analyze`, `humanizer`, `entity-bold`, `blog-image`) →
8. `cms-publish` → **draft** (never live).

**GATE 1** the SEO owner reviews the flagged list (not the whole article). **GATE 2** the SEO
owner approves go-live after the technical owner publishes to a temp URL. Then indexing +
`tracker-gen` logs results.

### The gates are the point

The engine could always write an article and publish it. It could not stop a bad one.

```bash
python3 .../cms-publish/scripts/build_page.py --mdx drafts/<slug>.mdx

python3 .../quality-gates/scripts/run_gates.py \
  --mdx drafts/<slug>.mdx --html drafts/<slug>.html \
  --serp scratch/<slug>.serp.json --keyword "<kw>"
# 0 all ran and passed · 1 warnings, or a skip you named · 2 blocked, OR a gate could not run
```

**Advisory scorers do not change behaviour.** A score of 78 reads as "good enough" and the
article ships. Only a non-zero exit code stops it.

**And a gate that could not run blocks.** To go on without one you have to name it,
`--allow-skipped serp,schema`, so the decision lands in the command and in the log rather
than in nobody's memory.

## What's in the engine

| Skill | Does |
|---|---|
| `intake` | the conversation before any work starts. Rewrite or fresh, keyword, site, **objective** |
| `research-chain` | providers in a fallback order, recording **which one answered** |
| `quality-gates` | the five blocking scripts. SERP, voice, facts, links, schema |
| `project-init` | onboard a new website's context |
| `brand-loader` | load BRAND/VOICE/project.yaml so writing obeys the site |
| `cms-publish` | push a draft to a code-based site or to WordPress. Never live |
| `entity-bold` | bold the first mention of key entities |
| `pipeline-run` | the end-to-end flow, failing on a blocking gate |
| `tracker-gen` | the shareable content dashboard |

Plus the MIT `blog-*` / `seo-*` / `diagram-design` skills it orchestrates (installed
separately — see `docs/DEPENDENCIES.md`).

## Publishing adapters

- **WordPress** — supported now (`skills/cms-publish/scripts/wordpress_publish.py`, stdlib-only,
  Application-Password auth, creates drafts, best-effort Yoast/RankMath meta).
- **Strapi / Ghost / markdown** — same interface, adapters to port next.

## Golden rules

- **Secrets never enter this repo.** `.env` is gitignored; the engine reads secrets from the
  environment. Only `.env.example` is committed. Every provider holds **several** credentials,
  numbered `_1`, `_2`, `_3`, because quota exhaustion on a single key is what took one
  provider out of an account entirely.
- **Publish only to `draft`.** Going live is a human action in the CMS.
- **Required gates are non-negotiable** for legal/medical/financial topics (`project.yaml → gates`).

## License

MIT (this plugin). It depends on separately-licensed skills — see `LICENSE` and
`docs/DEPENDENCIES.md`.

## Roadmap

- [ ] wire `providers.py` rotation into the MCP research calls, not just the config shape
- [ ] Ahrefs: authorise the OAuth connector in an interactive session, or fund a second route
- [ ] WordPress adapter hardening (Yoast/RankMath REST meta, media alt, categories/tags create)
- [ ] Strapi + Ghost adapters
- [ ] `brand-loader` → auto-derive an entity list for `entity-bold`
- [ ] `request-indexing` skill (GSC) + a results-loop into `tracker-gen`
- [ ] vendor the MIT blog engine for a one-command self-contained install
