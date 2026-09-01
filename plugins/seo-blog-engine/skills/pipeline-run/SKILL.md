---
name: pipeline-run
description: Run one blog article through the full engine end to end - intake, research, SERP gate, draft, enforcement gates, publish-ready draft - failing the run when a gate blocks rather than scoring it. Orchestrates intake, research-chain, brand-loader, blog-write/rewrite, quality-gates, entity-bold, and cms-publish. Use when the user says "run the pipeline", "process this topic", "take <topic> to draft", or hands over a URL or a Google Doc for a configured site.
---

# Pipeline run

The deterministic order the engine runs one article. It produces a **draft** plus a short
REVIEW list; it never publishes live. Humans own the two gates that are judgment calls, and
scripts own the ones that are not.

**The change that matters: the pipeline fails, it does not score.** Every gate returns an
exit code, and a blocking exit code ends the run at that step. An advisory number gets read
as "good enough" and the article ships anyway; that is how every defect on the reference
account got as far as it did.

## 0. Intake, before anything else

Run **`intake`**. Rewrite or fresh, and for a fresh piece the keyword, the site, and the
objective. Confirm the plan and **wait for approval**.

Do not start research while the user is thinking about it. The plan changes the research.

## 1. Preflight

- `project.yaml`, `BRAND.md`, `VOICE.md`, `PARTNERS.md`, `FACTS.md`, `.env` exist. If not,
  `project-init`.
- `config/voice-fingerprint.yaml` exists and its `refresh_due` has not passed.
- Load context with `brand-loader`.
- `python3 quality-gates/scripts/providers.py` to see which credentials are configured.

A missing `PARTNERS.md` or `FACTS.md` does not stop the run, but it does mean two gates
cannot check anything, and the run report must say so.

## 2. Research and the SERP gate, before a word is written

Run **`research-chain`**. Pull the SERP and the metrics through the fallback chain and record
which provider answered each figure.

**Re-pull. Every time.** A stored keyword board is a candidate list, not a data source.

Then:

```bash
python3 quality-gates/scripts/serp_gate.py --keyword "<kw>" scratch/<slug>.serp.json
```

**Exit 2 ends the run.** Do not write the article. Go back to the user with what the SERP
showed and two or three alternatives. This is the cheapest possible place to stop, and it
killed three of twelve keywords on the reference account, including the one with the best
volume-to-difficulty figure on the whole board.

Exit 1 is a decision, not a veto. Surface the warnings and let the user decide.

## 3. Draft

`blog-write` for a fresh piece, `blog-rewrite` for a rewrite, in the site's brand voice.

**Namespace every scratchpad artefact to the article slug.** Parallel runs share one
scratchpad. A build script overwritten mid-run by a sibling once put another article's FAQ
block into two live articles.

If the article carries a diagram, the information the diagram argues must also exist as
prose or a table. **An SVG's content is invisible to answer engines.**

## 4. Build the page

The schema gate reads an HTML file, so one has to exist. Build it from the draft:

```bash
python3 cms-publish/scripts/build_page.py --mdx drafts/<slug>.mdx
```

That writes `drafts/<slug>.html` beside the source, carrying the visible FAQ and the
JSON-LD. **Both are generated from one parse of the MDX**, so they cannot disagree with
each other, and the filename comes from the source rather than from an argument, so a
build cannot be pointed at a sibling article's file.

Skipping this step is how the strongest gate in the engine ends up checking nothing.

## 5. The enforcement gates

```bash
python3 quality-gates/scripts/run_gates.py \
  --mdx drafts/<slug>.mdx --html drafts/<slug>.html \
  --serp scratch/<slug>.serp.json --keyword "<kw>"
```

| Exit | Meaning | What happens |
|---|---|---|
| 0 | every gate ran and passed | continue |
| 1 | warnings only, or a skip you acknowledged | continue, and put the warnings in the REVIEW list |
| 2 | a gate blocked, **or a gate could not run** | **the run fails here** |

**A gate that could not run blocks.** To go on without one you have to name it:
`--allow-skipped serp,schema`. There is no blanket override. Naming the gate puts the
decision in the command and in the log, so "we shipped without the schema check" is
something a person chose rather than something that happened.

**Re-run the gates after the final edit, never before.** The three-surface FAQ match verified
before the last edit means nothing after it.

## 6. Fact-check and polish

`blog-factcheck` with the `blog-researcher` agent. Split into auto-cleared, a **VERIFY** list,
and a **LAWYER** list for topics in `project.yaml → gates.factcheck_required_for`.

The coordinator is a source of error too. On one run the fact-check layer corrected two
premises that came from the brief itself, and both articles were stronger for it. A brief is
not evidence.

Then `blog-analyze`, `entity-bold`, and `blog-image` if images are enabled. These are
advisory and they are allowed to be, because the blocking work already happened.

## 7. Publish as a draft

`cms-publish`. Code-based site or WordPress, draft only, and check the MCP server connects
before claiming a WordPress publish happened.

### GATE 1, human review, SEO owner
Reviewer reads the VERIFY/LAWYER list and the gate warnings, not the whole article.

### Publish to a preview URL, technical owner

### GATE 2, approve and go live, SEO owner
Live QA, then `request-indexing` and log with `tracker-gen`.

## Guardrails

- Never skip intake.
- Never write an article whose SERP gate exited 2.
- Never set a CMS status to `publish`.
- Never treat a gate that could not run as a gate that passed. `--allow-skipped` records a
  decision; it is not a way past a red light.
- Never hand-edit the built HTML. Edit the MDX and rebuild. The gate will catch you.
- Never report a figure without the provider that answered for it.
- One article per run.
