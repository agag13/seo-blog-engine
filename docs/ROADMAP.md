# Roadmap

Where the engine is, and what is deliberately not built yet.

**Now: v2.** Five blocking gates, an intake conversation, a research provider chain, a page
builder, two publish targets, and a setup doctor. Being tested on real articles.

---

## How we will know v3 is working

Not by counting features. One question: **how many real defects does the engine catch that
would otherwise have shipped?**

Every defect that actually happened becomes a fixture. The README carries one number,
*catches N of N known defects*, and CI stops it going down.

Today that number is **3 of 11**, which is the honest starting line:

| Defect, all of these really happened | Caught | Fixture |
|---|---|---|
| Cross-article FAQ contamination | yes | yes |
| FAQ answer drift between surfaces | yes | yes |
| Brand-owned SERP behind an easy difficulty score | yes | yes |
| Product claim that the client's own surfaces contradict | yes | no |
| A partner written about as a competitor | yes | no |
| Keyword data stale enough to flatter a keyword | yes | no |
| Em dash, superlative, banned structure | yes | no |
| Inline SVG scored as prose | fixed | **no** |
| A gate silently comparing against built-in defaults | fixed | **no** |
| The schema gate not running at all | fixed | **no** |
| `.gov` SERP taken for an easy win | rule only | no |

The last three are fixes with no test. They can come back and nobody would notice.

Two more numbers worth watching:

- **How often `--allow-skipped` is used.** A gate skipped every day is a badly designed gate
  or a broken pipeline. This is the escalation-rate idea from human-in-the-loop automation,
  and it applies here exactly.
- **Time from `project-init` to a green `doctor.py`** for a new site. Onboarding friction.

---

## v3

### 1. Defect corpus and an eval set, covering prompts as well as scripts

The gates protect articles. Nothing protects the gates, and nothing at all protects the
skills.

**The skills are prompts, and prompt edits change behaviour silently.** A widely reported
figure from practitioners: a one-line system-prompt change dropped output quality from 84%
to 52%. v2 edited three `SKILL.md` files with zero verification of the result, because there
is no way to verify it.

So the corpus has to cover both:

- **Scripts**: each fixture is an input plus an expected verdict. Fast, deterministic, CI.
- **Skills**: a small set of real, previously-failed runs, replayed after any `SKILL.md`
  change, comparing the decision the skill reaches rather than the prose it produces.

This is one job, not two, and it is the thing that makes every later change measurable.

### 2. External claim verification

`facts_check.py` covers **product** facts, from the site's own `FACTS.md`. Claims about the
outside world, statistics, cited sources, are still entirely manual.

This is reported repeatedly as the real bottleneck in AI content work, to the point where
practitioners say checking the output takes longer than writing it would have. Any
automation here pays for itself immediately.

### 3. Reddit and X as research inputs

Both for the same two jobs:

- **Discourse research at brief time.** What people actually say about a topic in the last
  30 days, in their own words. This is where the objections and the phrasing come from, and
  it is a different signal from what ranks.
- **Prior art before building.** Checking whether somebody has already solved a problem, and
  what went wrong for them.

Access status as of 2026-09-01: Composio carries a `reddit` toolkit
(`REDDIT_SEARCH_ACROSS_SUBREDDITS`, `REDDIT_RETRIEVE_POST_COMMENTS`) but it has **no active
connection**. Reddit content is readable today through Tavily, which is how the research
behind this roadmap was done. X has no connected route.

### 4. Everything else, in order

- **Track `--allow-skipped` usage** into a run log, so the escalation rate is a number.
- **Port a voice-measuring script.** The engine tells people to measure their cadence bands
  and ships no tool to measure them, so most sites will run on template defaults.
- **A scratchpad helper** that namespaces artefacts to the article slug, rather than a rule
  written in prose that a parallel agent will not read.
- **Byline-without-bio and diagram-without-prose checks.** Both are documented as things the
  gates cannot see.
- **Cannibalization** against the site's own live pages.
- **Wire `providers.py` into real calls.** Today it is a config shape and a rotation helper
  that nothing calls; the MCP connectors carry their own auth, so there is nothing yet to
  rotate.
- **Audit trail per run**, so a decision can be reconstructed months later.

---

## Standing decisions that are not ours to make

- **Ahrefs is dark.** The MCP connector is unauthorised and needs an interactive OAuth run;
  the Apify route is on a free plan whose hard limit does not reset. Until one is fixed,
  every difficulty figure is single-source, and the briefs say so.
- **Strapi and Ghost adapters** are unbuilt. WordPress and code-based sites are supported.
- **`brand-loader`, `entity-bold`, `tracker-gen`** are untouched from v0.1.0 and unaudited.
