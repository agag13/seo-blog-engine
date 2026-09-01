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

3. **Write the files** into the project folder, from the engine's `templates/`:

   | File | From | Note |
   |---|---|---|
   | `BRAND.md` | `BRAND.md.template` | audience, positioning, honesty rules |
   | `VOICE.md` | `VOICE.md.template` | readable prose. Not the gate |
   | `project.yaml` | `project.yaml.template` | site, CMS, gates |
   | `PARTNERS.md` | `PARTNERS.md.template` | **who this client never writes competitively about** |
   | `FACTS.md` | `FACTS.md.template` | **every product fact, with a status and a source** |
   | `config/voice-fingerprint.yaml` | `voice-fingerprint.yaml.template` | the measured bands. **The gate** |
   | `.env.example` | `env.example` | copy to `.env` and fill. NEVER write real secrets here |

   `examples/nika/` in the engine repo holds filled-in `PARTNERS.md` and `FACTS.md` from a
   real account. Read those for the shape before writing a new one.

4. **Interview for the two context files**, because they cannot be inferred:
   - **Partners.** "Who do you work with that we must never write competitively about?"
     Ask for domains too. This blocks whole article types, so an incomplete answer here
     surfaces later as a keyword that has to be dropped after the research is done.
   - **Facts.** Take the client's product claims and mark each EVIDENCED, BETA, CONFLICTED,
     or NOT PUBLISHED, with the source. Expect to find contradictions between the client's
     own surfaces; on one account a single number appeared four times with an 8x spread.
     Those become CONFLICTED, not a judgement call at writing time.

5. **Measure the voice, do not assert it.** The fingerprint template ships with placeholder
   bands and `confidence: low`. Fill it from a real corpus of the client's published writing
   before the first article, or the voice gate compares against defaults and says so.

6. **Write/append `.gitignore`** in the project folder to ignore `.env` and `.env.*`
   (keep `.env.example`).

7. **Report** a short summary and the exact next command, which is `intake`, not a write.
   Confirm the CMS `default_status` is `draft`, and say plainly which of `PARTNERS.md`,
   `FACTS.md` and the fingerprint are still placeholders, because each one that is a
   placeholder is a gate that cannot block anything.

## Guardrails
- Do not invent brand facts. If the user does not know a field, leave a clear TODO.
- Do not invent voice bands. A guessed band blocks good copy and passes bad copy.
- An empty `PARTNERS.md` or `FACTS.md` is honest. A speculative one is not.
- Never place API tokens in `project.yaml` or any committed file — only in `.env`.
- One website per project folder. Do not mix two brands' context in one folder.
