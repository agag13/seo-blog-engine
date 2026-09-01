# Getting started

Hand this file to whoever is setting the engine up. It is the whole list.

**Read the shape first, because it decides where everything goes.** The engine is shared
and installed once per person. The context is per website and lives in that website's own
repo. Nothing about a client ever gets committed here.

```
this repo, installed once per teammate       each website, its own folder / repo
  the skills                                   BRAND.md, VOICE.md
  the templates                                PARTNERS.md, FACTS.md
  the gate scripts                             project.yaml
                                               config/voice-fingerprint.yaml
                                               .env          <- secrets, gitignored
```

There are four steps. Step 3 is the only one that takes real time, and it is the one that
decides whether the gates can actually block anything.

---

## Step 1 · Each teammate's machine, once

| Need | How | Check |
|---|---|---|
| Claude Code | already installed | `claude --version` |
| This plugin | `/plugin marketplace add agag13/seo-blog-engine` then `/plugin install seo-blog-engine` | the skills appear |
| The skills this engine calls | see [`DEPENDENCIES.md`](DEPENDENCIES.md) | `blog-write`, `blog-factcheck`, `blog-analyze`, `diagram-design` resolve |
| Python 3.9 or newer | usually already there | `python3 --version` (verified working on 3.9.6; 3.11 preferred) |
| **PyYAML** | `pip3 install pyyaml` | **not optional in practice** |

**On PyYAML.** Without it the voice gate cannot read the fingerprint, so it falls back to
built-in bands. It prints that it did, so it is not silent, but a gate comparing against
numbers nobody measured is a gate that passes almost anything. Install it.

Everything else in the gate scripts is standard library, deliberately, so a gate never
fails to run because of a missing dependency.

---

## Step 2 · Connect the MCP servers

Two kinds, and the difference matters.

### Shared, connect once

- **DataForSEO** — does most of the work. Live SERPs, volume, difficulty, trends.
- **Tavily** — the fallback for search, and **the only route for anything geo-specific**,
  because the built-in web search is US-only.

### Per website, and this is each site's own problem

**WordPress goes through Novamira, and every website gets its own connection.** One site,
one Novamira install, one MCP server entry. There is no shared WordPress credential and
there should not be.

Whoever owns a site connects that site's server themselves. The engine does not hold a
list, does not guess, and does not fall back to a different site's server if one is down.
What it does instead, before every publish, is ask:

```
mcp-adapter-discover-abilities   on the server this site's project.yaml points at
```

If it answers, that server is live and the reply also lists what that particular install
supports, which genuinely differs between sites: one may run Rank Math, another Yoast,
another neither. If it does not answer, **the publish stops and says which server failed**.
It never silently skips the publish step, because an article that quietly did not publish
is worse than one that failed loudly. Nobody goes looking for the quiet one.

This is not hypothetical. On the machine this was built on, three Novamira servers were
configured and **one answered, two did not**, one of them `ENOTFOUND`. That is normal, not
an incident: each site has its own, and some are local or retired. The one that answered
reported WordPress 7.1, PHP 8.2.29 and Rank Math active, which is how the engine knew to
write Rank Math fields rather than Yoast ones.

Re-check at run time, every time. A server that answered last week is not evidence about
today.

Code-based sites (Next.js, Astro) need **no** MCP connection at all. They get files written
into the repo, uncommitted.

### Known broken, so nobody wastes an afternoon on them

- **Ahrefs MCP** — unauthorised. Needs an OAuth flow in an interactive session. A
  background or non-interactive run cannot fix it.
- **Apify route to Ahrefs** — HTTP 403 `Monthly usage hard limit exceeded`. The account is
  on the **free plan**, so this is a hard limit and not a quota. It returned 403 on the
  last day of one month and again on day one of the next. **Waiting is not a plan.**

Full detail in [`PROVIDERS.md`](PROVIDERS.md).

---

## Step 3 · Onboard one website

Run `project-init` from inside that website's folder. It interviews you and writes the
files. Then somebody has to actually fill them, and this is the part that cannot be
automated, because it is all information the client has and the engine does not.

| File | Who supplies the content | Without it |
|---|---|---|
| `project.yaml` | you | nothing runs |
| `BRAND.md` | client, plus your reading of their site | drafts are generic |
| `VOICE.md` | you, from their published writing | tone guidance only, enforces nothing |
| `config/voice-fingerprint.yaml` | **measured** from 10+ of their published pieces | the voice gate compares against defaults |
| `PARTNERS.md` | **the client must confirm this list** | the partner rule never fires |
| `FACTS.md` | you, by auditing the client's own surfaces | every product claim ships unchecked |
| `.env` | whoever holds the credentials | direct API calls fail; MCP calls still work |

`examples/worked-example/` in this repo is a complete filled-in set. Read it before
writing a new one. It is the fastest way to see the level of specificity that actually
changes a draft, and its own README explains why `doctor.py` deliberately reports it as
not-ready.

### The three that people skip, and what skipping each one costs

**`PARTNERS.md`.** Who this client will never be written competitively against. Ask for
domains too. On the reference account this blocked entire article types, and three partners
turned up ranking on target SERPs inside one week. An incomplete list here does not fail
loudly. It surfaces weeks later as a keyword you have to drop after the research is done.

**`FACTS.md`.** Every product fact, marked EVIDENCED, BETA, CONFLICTED, or NOT PUBLISHED,
with its source. **Expect the client's own surfaces to contradict each other.** On the
reference account one number appeared four times across four of the client's own pages with
an 8x spread, including a product page that contradicted its own meta description. Those
become CONFLICTED, and the gate blocks them, so the contradiction gets resolved by the
client instead of guessed at by a writer.

**The fingerprint.** Measure it. Do not assert it. The template ships with placeholder
bands and `confidence: low` precisely so nobody mistakes them for measurements. Guessed
bands block good copy and pass bad copy, and the predictable next step is that somebody
turns the gate off.

The band that matters most is the share of one-sentence paragraphs, with a hard ceiling on
paragraph length. **The measured gap is cadence, not rule compliance.** Copy can pass every
hard rule and still read corporate.

---

## Step 4 · Check the setup, then run

```bash
python3 <plugin>/skills/quality-gates/scripts/doctor.py
```

Run it from inside the website's folder. It reports READY / warn / STOP per item and tells
you what to do about each one.

```
0   ready
1   runnable, but at least one gate cannot check anything
2   not ready
```

**Exit 1 is the state to pay attention to.** It means the pipeline will run and produce an
article, and one of the gates is standing there with nothing to compare against. That is
the failure mode this whole setup exists to prevent, so read the warnings rather than
noting the article came out fine.

One thing to know before the first run: **a gate that could not run stops the pipeline.**
If the report says NOT RUN, that is a failure and not a note. Either give the gate what it
needs, or name it in `--allow-skipped` so the decision is on the record.

Then, for the first article:

```
/blog-pipeline <topic or URL>
```

It starts with `intake`, which asks whether this is a rewrite or a fresh piece, and for a
fresh piece the keyword, the site, and the objective. **It waits for approval before doing
any work.** That is deliberate.

---

## What each person needs to obtain

| Thing | Who from | Needed for |
|---|---|---|
| DataForSEO access | existing account | SERP, volume, difficulty. **Most of the work** |
| Tavily access | existing account | fallback search, and anything geo-specific |
| Novamira on the client's WordPress | install per site, client's admin | WordPress publishing |
| Ahrefs | **decision pending.** Authorise the connector, fund Apify, or buy the seat | the second difficulty source |
| SerpAPI, Apify, Moz | optional | second credentials, so one exhausted key does not end a provider |

**Multiple credentials per provider is the point of the `.env` shape.** Keys are numbered
`_1`, `_2`, `_3`, and the engine rotates on failure and logs which one served each call.
A single key hitting its quota is exactly how the Ahrefs route was lost on the reference
account.

### The one open decision

Until Ahrefs is restored, every difficulty figure comes from **one source**. That is not
fatal, and it is honest as long as briefs say so, which they do. But the two sources
genuinely disagree: one keyword read **KD 9 on DataForSEO and KD 46 on Ahrefs**. Somebody
should decide which of the three fixes to take.

---

## What is not in this repo, and never will be

- **Secrets.** `.env` is gitignored. Only `.env.example` is committed.
- **Any client's content, facts, or approvals.** Those live in that client's own repo.
- **The task tracker, the reporting dashboard, and client comms.** Different tools.

## The rules that do not bend

1. **Nothing publishes live.** Every target writes a draft. On a code-based site that means
   the engine does not commit and does not deploy.
2. **The gates block, they do not score.** A score of 78 reads as "good enough" and the
   article ships. Only a non-zero exit code stops it.
3. **A gate that could not run is never a gate that passed.** The runner reports it as
   NOT RUN and raises the verdict.
4. **Never guess a number when a provider fails.** Write down that it failed.
5. **Re-pull keyword data at brief time, every time.** A stored board is a candidate list,
   not a data source. Four of four keywords re-pulled after three weeks carried a wrong
   figure, and every error flattered the keyword.
