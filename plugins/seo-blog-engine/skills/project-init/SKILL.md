---
name: project-init
description: Onboard a NEW website into the SEO blog engine. Interviews for brand, voice, site, and CMS, then writes BRAND.md, VOICE.md, project.yaml, and a gitignored .env.example into the current website's project folder. Use when the user says "set up a new site/client", "onboard <brand>", "init blog project", or starts work in an empty project folder with no project.yaml.
---

# Project Init

Set up one website's per-project context so the rest of the engine can run against it.
The engine skills read this context from the **current working directory** — so run
this from inside that website's own folder (its own git repo), never inside the engine repo.

## Steps

1. **Confirm the folder.** Ensure you are in the website's project folder, not the engine
   plugin. If a `project.yaml` already exists, ask before overwriting.

2. **Interview** (ask only what you cannot infer; keep it tight):
   - Brand name, homepage URL, logo URL, sameAs profiles, mission, distinctive POV,
     what the brand is NOT, top competitors.
   - Audience: who, expertise, emotional state, active problems, common misconceptions.
   - Editorial rules: always-do, never-do, taboo phrases, required disclosures.
   - Voice: pronoun stance, sentence/paragraph ceilings, headline patterns, readability target.
   - Topic scope: core pillars, partial, out-of-scope.
   - CMS: type (wordpress/strapi/ghost/markdown), API base, SEO plugin (Yoast/RankMath),
     author id map, allowed categories.
   - Cadence + timezone + GSC property.

3. **Write the four files** into the project folder, from the engine's `templates/`:
   - `BRAND.md`     (from `templates/BRAND.md.template`, filled in)
   - `VOICE.md`     (from `templates/VOICE.md.template`, filled in)
   - `project.yaml` (from `templates/project.yaml.template`, filled in)
   - `.env.example` (from `templates/env.example`) — and remind the user to copy it to
     `.env` and fill secrets. NEVER write real secrets to disk here.

4. **Write/append `.gitignore`** in the project folder to ignore `.env` and `.env.*`
   (keep `.env.example`).

5. **Report** a short summary and the exact next command (usually `pipeline-run` or a
   `blog-write` on the first topic). Confirm the CMS `default_status` is `draft`.

## Guardrails
- Do not invent brand facts. If the user does not know a field, leave a clear TODO.
- Never place API tokens in `project.yaml` or any committed file — only in `.env`.
- One website per project folder. Do not mix two brands' context in one folder.
