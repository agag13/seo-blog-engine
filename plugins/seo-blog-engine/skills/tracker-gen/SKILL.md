---
name: tracker-gen
description: Generate or update a single-file HTML "command center" dashboard for a website — a Content tab with purpose, publish/update counts, pending-by-owner, the article table with CMS review links, and a 30-day tracker. Use when the user says "build/update the dashboard", "content tracker", "command center", or after a batch of drafts is pushed.
---

# Tracker Gen

Produce one self-contained HTML dashboard the team can share (publish as an Artifact, or
serve the file). It is the at-a-glance state of the content operation for one site.

## What it renders (top of the Content view first)
1. **Purpose** — what the content operation is for, and the owner roles for this site
   (from `project.yaml -> gates`).
2. **Counts** — to publish / to update / held / total staged (computed from the article list).
3. **Pending by owner** — just numbers per person (creator = done; reviewer + publisher = N).
4. **Artifacts attached** — links to this dashboard, the pipeline handover, and any briefs.
5. **Article table** — id, title, keyword, status (Draft/Held/Live), and the CMS review URL.
6. **30-day tracker** — target vs scheduled, per-stage (drafted / reviewed / published / indexed).

## Data source
Read the article list from the site's tracking file (`content/tracker.json` or the
per-post `*.meta.json` files) + `project.yaml`. Do not hardcode counts — compute them so
the dashboard stays honest as posts move.

## Build rule (do not skip)
The dashboard is one HTML file with one `<script>` holding the data object plus tab render
functions built from nested template literals. **A single template-literal or brace slip
breaks the whole script and blanks EVERY tab.** Before publishing/republishing:
1. Extract the `<script>` and run `node --check`.
2. Eval it with a no-op DOM proxy and call every tab's `build()`, asserting each returns a
   non-empty string.
Only ship once all tabs render clean. Keep the favicon and title stable across updates.

## Styling
Neutral editorial palette; the site's brand accent from `project.yaml`. Borders not shadows.
Theme-aware background. Keep it scannable — a handover doc, not a data dump.
