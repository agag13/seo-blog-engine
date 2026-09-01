---
name: quality-gates
description: The blocking enforcement layer. Five scripts with non-zero exit codes that stop a bad article rather than scoring it: SERP rejection, voice cadence, product facts, link resolution, and three-surface schema matching. Use before any publish step, and whenever the user says "check this draft", "run the gates", "is this ready", or a pipeline reaches its review point.
---

# Quality gates

The engine could already write an article and publish it. It could not stop a bad one.
Every defect on the reference account was caught by these scripts or by a live SERP check.

**Advisory scorers do not change behaviour.** A hundred-point score that reads 78 gets read
as "good enough" and the article ships. Only a non-zero exit code stops it. Every script
here exits 2 on a block, and `pipeline-run` fails the run rather than noting it.

## The five gates

| Gate | Script | Blocks on |
|---|---|---|
| SERP | `serp_gate.py` | who ranks, before writing starts |
| Voice | `voice_check.py` | banned structures, partner framing, cadence bands |
| Facts | `facts_check.py` | product claims that are CONFLICTED or NOT PUBLISHED |
| Links | `links_check.py` | an internal link that 404s and was not declared |
| Schema | `schema_check.py` | invalid JSON-LD, or a FAQ answer that differs across three surfaces |

Run them together:

```bash
python3 scripts/run_gates.py \
  --mdx drafts/<slug>.mdx \
  --html out/<slug>.html \
  --serp scratch/<slug>.serp.json \
  --keyword "<target keyword>"
```

Exit 0 pass, 1 warnings or a gate that could not run, 2 blocked.

**A gate that could not run is never a gate that passed.** Missing `--serp` does not mean
the SERP was fine; the runner reports it as NOT RUN and raises the verdict to at least 1.

## Per-site configuration

Each gate resolves the site by walking up from the file being checked, looking for
`project.yaml` and then `.git`. Nothing is computed from the script's own location, because
that is how a gate silently compares against built-in defaults while appearing to pass.

| File | Used by | If missing |
|---|---|---|
| `project.yaml` | all | `site.url` absent means links cannot resolve, and the gate says so |
| `config/voice-fingerprint.yaml` | voice | falls back to built-in bands, and prints that it did |
| `PARTNERS.md` | voice, serp | the partner check does not run, and prints that it did not |
| `FACTS.md` | facts | exit 1 with "every product claim in this draft is unchecked" |

Worked examples for a real account: `examples/nika/`.

## Why each gate exists

### SERP rejection, `serp_gate.py`

Reject on **who ranks**, not on a difficulty score.

Forums, Reddit, Quora and small blogs near the top mean Google has no authoritative page to
reward: **build**. A `.gov` at position one, two or more `.gov` in the top ten, an
encyclopedia in the top three, four or more major-news results, or **one brand holding half
of page one** mean **stop**.

This killed three of twelve keywords that all looked easy. The clearest read difficulty 6,
the easiest figure on the board, and eight of nine results belonged to one brand. There was
no position to take. The fixture in `fixtures/coinbase-perpetual-futures.serp.json` is that
SERP, re-pulled live on 2026-09-01 and still true, and it is the regression test.

The gate also reads the AI Overview's cited domains, because an overview built from a
regulator is a stop signal even when the organic ten look survivable.

### Voice, `voice_check.py`

**Prose guidance in a VOICE.md does not work. A model reads past it. A number fails.**

The measured gap is cadence, not rule compliance. Copy can pass every hard rule and still
read corporate. On the reference corpus the founder ran **42.1% one-sentence paragraphs**
with **exactly one paragraph over 70 words across 297**; the shipped articles ran 11.7% and
62 out of 290. Same rules, different rhythm, and the rhythm is what readers feel.

The gate also strips inline SVG before building the cadence corpus. A diagram spec that
mandates inline SVG in the source would otherwise score attribute names as prose and depress
every article's lexical diversity. `<figcaption>` is real prose and stays.

Brand rules live in the site's fingerprint under `banned_structures`, each with an `id`, a
`pattern`, a `why`, and an optional `severity: warn` for the ones that are judgment calls. A
gate that blocks on a judgment call gets switched off.

### Facts, `facts_check.py`

Blocks any draft stating a fact the site's `FACTS.md` marks CONFLICTED or NOT PUBLISHED.

This is what stopped a leverage number publishing while four contradictory figures, an 8x
spread, sat on the client's own surfaces.

### Links, `links_check.py`

An internal link may 404 only if the draft's handover comment both says "forward-link" and
names that exact path. Anything else that 404s blocks.

### Schema, `schema_check.py`, and the three surfaces

Validates JSON-LD and byte-matches every FAQ answer across **three** surfaces: the JSON-LD,
the visible HTML, and the sibling source file.

**Two surfaces is not enough, and this is not theoretical.** A two-surface version returned
`OK faq-match` on two articles carrying a completely different article's FAQ block. A shared
scratchpad had replaced both surfaces from the same wrong source, so they agreed with each
other and the check passed. The third surface is the one that disagrees.

## Two operational rules that come with these gates

**Namespace every scratchpad artefact to the article slug.** Parallel agents share one
scratchpad. One agent's build script was silently overwritten mid-run by a sibling writing
the same filename; its HTML went stale while its source moved on, and a broken FAQPage
nearly shipped. It was caught only because the build printed another article's filename.

**Re-verify the three-surface match after the final edit, never before.** A match verified
before the last edit is a match that no longer means anything.

## Two more things the gates cannot see

- **A named author with no bio and no photo scores worse than no named author**, by roughly
  8 points on authoritativeness. If a byline is added, the bio and the photo are required.
- **An SVG diagram's content is invisible to answer engines.** If a diagram carries an
  argument, the same information must exist as prose or a table. On one build the single
  most extractable sentence in the article existed only inside the SVG.
