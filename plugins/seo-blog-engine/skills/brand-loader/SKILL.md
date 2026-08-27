---
name: brand-loader
description: Load the current website's BRAND.md, VOICE.md, and project.yaml into context before any writing, rewriting, briefing, or outlining, so the blog engine writes in THIS site's voice and rules instead of a generic default. Use at the start of any content task, or when the user says "load brand", "use the brand voice", or switches to a different site's folder.
---

# Brand Loader

The generic `blog-write` / `blog-rewrite` skills are brand-agnostic. This skill injects
the current site's identity so every draft obeys that site's audience, honesty rules,
taboo phrases, and voice.

## Steps

1. From the current working directory, read (if present):
   - `BRAND.md` — audience, positioning, editorial rules, taboo phrases, disclosures, topic scope.
   - `VOICE.md` — pronoun stance, lexical rules, headline patterns, voice fingerprint, readability.
   - `project.yaml` — site url, locale, categories, cadence, gates.
2. If any is missing, tell the user to run `project-init` first — do not fall back to a
   generic voice silently.
3. Hold these as the binding constraints for the rest of the session:
   - Enforce the **never-do** list and **taboo phrases** as hard fails in any draft.
   - Apply the **required disclosures** to the relevant topics.
   - Match the **voice fingerprint** and readability target.
   - Keep every claim inside the **topic scope**; refuse out-of-scope requests.
4. Confirm in one line which brand is loaded (name + locale) before proceeding.

## Notes
- This is a context-loader, not a generator. It changes HOW the writing skills behave.
- Re-run it when the working directory changes to a different website.
