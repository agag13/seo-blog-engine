# Orientation

Read this before anything else in the repo. Fifteen minutes, and you will know what
this is, why each part exists, and what is deliberately missing.

---

## What this is

A reusable SEO blog engine for Claude Code. **The engine is installed once and shared
across every client. Each website supplies only its own context** — brand, voice,
partners, product facts, CMS, secrets.

```
this repo, installed once per person       each website, in its own repo
  the skills                                 BRAND.md      audience, positioning
  the gate scripts                           VOICE.md      tone, prose only
  the templates                              PARTNERS.md   never write against these
  examples/worked-example/                   FACTS.md      claims + status + source
                                             project.yaml  site, CMS, gates
                                             config/voice-fingerprint.yaml
                                             .env          secrets, gitignored
```

Nothing about any client is ever committed here. A repo-wide search for client names
returns zero results, and that is enforced deliberately.

---

## The one idea, and everything follows from it

**The engine could always write an article and publish it. It could not stop a bad one.**

That is what this work fixed, and one principle runs through all of it:

> **Advisory scorers do not change behaviour. Only a blocking exit code does.**

A quality score of 78 gets read as "good enough" and the article ships. A gate that
exits 2 stops the run and cannot be argued with. So every check here is a script with
an exit code, never a paragraph of guidance a model can read past.

The corollary matters just as much:

> **A gate that could not run is never a gate that passed.**

If the SERP file is missing, or the HTML was never built, the run fails. To proceed
without a gate you have to name it, `--allow-skipped serp,schema`, so the decision
lands in the command and in the log rather than in nobody's memory.

---

## The six gates

All in `plugins/seo-blog-engine/skills/quality-gates/scripts/`. Run them together with
`run_gates.py`, which returns 0 pass, 1 warnings, 2 blocked.

| Gate | What it stops | Why it exists |
|---|---|---|
| `serp_gate.py` | building a keyword you cannot win | One keyword read difficulty 6, the easiest on the board, and 7 of 9 results belonged to one brand. There was no position to take |
| `voice_check.py` | copy that reads corporate | The gap was never rule compliance, it was cadence. The founder ran 42% one-sentence paragraphs; the articles ran 12% |
| `facts_check.py` | product claims the client cannot evidence | A leverage figure nearly published while four contradictory versions sat on the client's own pages, an 8x spread |
| `claims_check.py` | outside claims the source does not support | The commonest hallucination is not an invented link. It is a real link to a page that never made the claim |
| `links_check.py` | internal links that 404 | Unless declared as a forward-link in the draft's handover comment |
| `schema_check.py` | FAQ drift across surfaces | Two articles shipped carrying a **different article's** FAQ block, and a two-surface check passed them |

### The schema gate deserves a paragraph

It matches every FAQ answer across **three** surfaces: the JSON-LD, the visible HTML,
and the source file. Two is not enough, and that is not theoretical. A shared scratchpad
once replaced both the JSON-LD and the visible copy from the same wrong source, so they
agreed with each other and the check returned OK. The third surface is the one that
disagrees.

`build_page.py` now generates the visible FAQ and the JSON-LD from **one parse of one
file**, so they cannot drift by construction. That demotes the schema gate from sole
defence to regression test, which is a smaller and more honest job for it.

### The claims gate deserves one too

Fact-checking is reported everywhere as the bottleneck in AI content work. That is true
of the judgment half. It is not true of the rest, and the rest is most of what goes
wrong. Five checks, four needing no judgment at all:

1. a claim carrying a figure has a citation
2. the URL resolves
3. **the claimed value actually appears on the cited page**
4. the source is recent enough for a present-tense claim
5. the draft's hedge is not stronger than the source's

Checks 4 and 5 exist because of two errors that **look verified**. A claim that was true
in 2022 and false by 2025, where the source exists and says it. And a source saying
"some" that became a draft saying "most".

A source that cannot be read is **not** evidence the claim is wrong. It warns, goes on a
VERIFY list, and never silently passes.

---

## The rest of the engine

| Skill | Does |
|---|---|
| `intake` | The conversation before any work. Rewrite or fresh; then keyword, site, and **objective**. Waits for approval. This is a hard gate |
| `research-chain` | Providers in a fallback order, **recording which one answered**. Never guesses a number when a provider fails |
| `discourse-pull` | What people actually say, from the comment threads. Tavily finds them, Reddit gives the comments. Cached per site, so the same thread is never paid for twice |
| `quality-gates` | The six scripts above, plus `doctor.py` |
| `project-init` | Onboards a new website's context |
| `brand-loader` | Loads BRAND/VOICE/project.yaml so writing obeys the site |
| `cms-publish` | Pushes a **draft**. Code-based sites get files, WordPress goes through Novamira. Never live |
| `pipeline-run` | The end-to-end flow, failing on a blocking gate |
| `entity-bold`, `tracker-gen` | Untouched from v0.1.0 and unaudited |

### On the objective question in `intake`

It is the one people skip and the one that changes the article most. "Rank for X" and
"be cited by AI answers" produce different articles. On the reference account the second
mattered more, and a keyword with about ten searches a month was correctly built because
no ranking page carried the one line the answer engines needed.

---

## Start here, in this order

```bash
# 1. install
/plugin marketplace add agag13/seo-blog-engine
/plugin install seo-blog-engine
pip3 install pyyaml          # not optional in practice, see below

# 2. onboard one website, from inside that website's folder
project-init

# 3. find out what is still missing
python3 <plugin>/skills/quality-gates/scripts/doctor.py

# 4. watch a gate actually block, before writing anything real
python3 <plugin>/skills/cms-publish/scripts/build_page.py \
  --project-root examples/worked-example \
  --mdx examples/worked-example/drafts/failing-sample.mdx

python3 <plugin>/skills/quality-gates/scripts/run_gates.py \
  --project-root examples/worked-example \
  --mdx examples/worked-example/drafts/failing-sample.mdx \
  --html examples/worked-example/drafts/failing-sample.html \
  --allow-skipped serp
```

That last command is the fastest way to understand the whole repo. It produces 12 voice
blocks and 2 facts blocks against a deliberately broken draft. A block reads very
differently from a score, and that difference is the entire point.

**On PyYAML:** without it the voice gate cannot read the fingerprint and falls back to
built-in bands. It prints that it did, so it is not silent, but bands nobody measured
pass almost anything.

Fuller setup instructions: [`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md).

---

## Three things that will bite you

**The three context files people skip.** `PARTNERS.md` needs the client to confirm the
list — on the reference account three partners turned up ranking on target SERPs inside
one week, and each one was a keyword that had to be dropped after the research was done.
`FACTS.md` needs an audit of the client's own surfaces, and you should expect those
surfaces to contradict each other. The **fingerprint must be measured**, not asserted;
guessed bands block good copy and pass bad copy, and then somebody turns the gate off.

**Doctor exit 1 is the state to watch.** It means the pipeline will run, an article will
come out, and one of the gates is standing there with nothing to compare against.

**Stored keyword data goes stale fast, and always in the flattering direction.** Four of
four keywords re-pulled after three weeks carried a wrong figure and every single error
made the keyword look better than it was. The cause is a trailing twelve-month average
taken across a spike. Re-pull at brief time, every time.

---

## What is NOT built, on purpose

Named so they read as decisions rather than gaps. Full list in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

- **No tests, no CI.** The gates protect articles; nothing protects the gates, and
  nothing at all protects the skills. This is the top of the v3 list.
- **The skills are prompts, and prompt edits change behaviour silently.** Three
  `SKILL.md` files were edited with no way to verify the result. Practitioners report a
  one-line system-prompt change moving output quality from 84% to 52%.
- **`providers.py` is a config shape only.** Multi-credential rotation with a per-call
  log, wired into nothing. The MCP connectors carry their own auth, so there is nothing
  yet to rotate.
- **Strapi and Ghost adapters** are unbuilt. WordPress and code-based sites work.
- **Ahrefs is dark.** The MCP connector is unauthorised and needs an interactive OAuth
  run; the Apify route is on a free plan whose hard limit does not reset. Until one is
  fixed every difficulty figure is single-source, and the briefs say so rather than
  implying corroboration that never happened.

---

## How progress gets measured

Not by counting features. One number:

> **catches N of N known defects**

Every defect that really happened becomes a fixture with a saved input and an expected
verdict. Today it is an honest **3 of 11**. Three of the eleven are fixes with no test
behind them, which means they can come back and nobody would notice.

Two fixtures ship already: the SERP that killed an apparently easy keyword, and a claims
draft broken four different ways with its sources cached so it runs offline.

That claims fixture earned its place during development by catching two false positives
in opposite directions: "every" matching inside "everyone", and an uncited claim
borrowing the next paragraph's citation. One would have blocked clean copy, the other
would have waved through a bare assertion.

---

## House rules

1. Nothing publishes live. Every target writes a draft. On a code-based site that means
   the engine does not commit and does not deploy.
2. Gates block, they do not score.
3. A gate that could not run is not a gate that passed.
4. Never guess a number when a provider fails. Write down that it failed.
5. Re-pull keyword data at brief time, every time.
6. No secrets in this repo. Only `.env.example`, with every value empty.
