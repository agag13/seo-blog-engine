---
name: pipeline-run
description: Run one blog article through the full engine end to end — draft to publish-ready draft — enforcing the two human gates. Orchestrates brand-loader, blog-write/rewrite, blog-factcheck, entity-bold, blog-seo-check, blog-cannibalization, and cms-publish. Use when the user says "run the pipeline", "process this topic/doc", "take <topic> to draft", or hands over a Google Doc for a configured site.
---

# Pipeline Run

The deterministic order the engine runs one article. It produces a CMS **draft** plus a
short REVIEW list; it never publishes live. Humans own the two gates.

## Preflight
- Ensure `project.yaml`, `BRAND.md`, `VOICE.md`, `.env` exist (else `project-init`).
- Load context with `brand-loader`.

## The run (stop and report at each gate)

1. **Draft** — `blog-write` (new) or `blog-rewrite` (existing). Answer-first, brand voice,
   honesty rules, FAQ. Structural validate: word count, banned words, 0 em dashes,
   headings, internal links resolve.
2. **SEO** — `blog-seo-check`: title/meta length, canonical, slug, heading hierarchy,
   internal/external links. `blog-cannibalization`: check the primary keyword against the
   site's live set; if it collides, decide consolidate vs differentiate (that DECISION is a
   human call — surface it, don't auto-merge live pages).
3. **Fact-check** — `blog-factcheck` (+ the `blog-researcher` agent). Produce the claim
   ledger with 0–1.0 scores. Split output into:
   - auto-cleared (verified) — nobody re-checks,
   - **VERIFY list** — low-confidence/uncited claims for the reviewer,
   - **LAWYER list** — for topics in `project.yaml -> gates.factcheck_required_for`.
   Fix any outright errors in the draft; keep the source's review markers as the trail.
4. **Polish** — `blog-analyze` (100-pt) + `humanizer` (AI-tells, readability). `entity-bold`.
   `blog-image` for hero + inline (dignity check on sensitive topics) — only if images are
   enabled for this project.
5. **Push draft** — `cms-publish` (draft status). Return the CMS edit URL.

### GATE 1 — human review (SEO owner)
Reviewer reads only the VERIFY/LAWYER list + the SEO summary, not the whole article. Pass →
continue; fail → back to step 1/3.

### Publish (technical owner)
Technical owner publishes the draft to a temp/preview URL and sets schema.

### GATE 2 — approve + go live (SEO owner)
Owner does live QA (schema renders, mobile), approves go-live, then `request-indexing`
(GSC) and logs results with `tracker-gen`. Results loop back to the next brief.

## Guardrails
- Never skip a required gate for a `factcheck_required_for` topic.
- Never set CMS status to `publish` — that is a human action in the CMS.
- One article per run; report cleanly so the reviewer can act in minutes.
