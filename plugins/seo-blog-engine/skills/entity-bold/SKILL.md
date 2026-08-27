---
name: entity-bold
description: Bold the first mention of each key entity (laws, platforms, tools, brand terms) in a blog draft, for reader scannability and semantic emphasis. Use as a late step before publish, when the user says "entity bold", "bold the key terms", or as part of pipeline-run.
---

# Entity Bold

Bold the first plain-text occurrence of the entities a page should be known for. Skips
headings, existing bold, and link anchors so it never breaks markup.

## Steps
1. Build the entity list for THIS post (highest-signal first): the laws/regulations, the
   platforms, the tools, the brand/product names, and the primary topic entity. Prefer
   terms that are NOT already links (links already carry emphasis).
2. Save them to `entities.txt` (one per line) — or pass an existing per-project list.
3. Run:
   ```
   python3 scripts/entity_bold.py --content post.md --entities entities.txt --inplace
   ```
   Use `--dry-run` first to see which entities matched.
4. Keep it restrained: ~5–10 entities per article. Over-bolding reads as spam and dilutes
   the signal. Do not bold the primary keyword on every occurrence — first mention only.
5. If the CMS copy is separate from the source, mirror the same bolds there (or re-publish
   from the updated source).

## Guardrails
- Never bold inside a link anchor or a heading.
- Do not invent entities the article does not actually discuss.
