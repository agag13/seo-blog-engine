---
name: intake
description: The conversation that happens before any article work starts. Establishes whether this is a rewrite or a fresh piece, and for a fresh piece the keyword, the destination site, and the objective. Confirms a short plan and waits for approval. Use at the start of every run, whenever the user says "write an article", "rewrite this page", "we need a post about X", or hands over a URL or a topic with no brief.
---

# Intake

The engine used to assume you already knew what you were writing. That assumption is where
the wrong article gets written well, which is the most expensive failure available.

**This is a hard gate, not a courtesy.** No research, no keyword pull, no draft until the
user approves the plan. If the user's first message already answers some of these questions,
do not ask them again; ask only what is missing.

## Question 1, always first

> **Rewrite an existing article, or write a fresh one?**

Everything after this branches on the answer.

### If rewrite

1. **Ask for the URL.** One URL. If they give several, take them one at a time; the gates
   run per article and so does this.
2. **Fetch it.** `tavily_extract` first, `on_page_content_parsing` as the fallback, plain
   WebFetch last. Record which one answered.
3. **Research from what is on the page**, not from what the topic suggests. Read the actual
   H1, the actual sections, the actual claims, the actual internal links. A rewrite brief
   built from assumptions about the topic will delete the one paragraph that was ranking.
4. **Report what you found before proposing changes:** current title and meta, heading
   structure, word count, what it currently claims, what it links to, and what is
   conspicuously absent.
5. If the fetch fails, **say so and stop.** Do not rewrite a page you could not read.

### If fresh

Ask all three. The third is the one that gets skipped, and it is the one that changes the
article most.

1. **Target keyword or topic.** If they give a topic, you will need to turn it into a
   keyword during research, and the SERP gate then decides whether it survives.
2. **Which website does this publish to?** This selects the whole per-site context:
   `project.yaml`, `BRAND.md`, `VOICE.md`, `PARTNERS.md`, `FACTS.md`, and the voice
   fingerprint. Getting this wrong means every gate checks against the wrong site.
3. **What is the objective?**

## On the objective question, since it is the one that gets skipped

"Rank for X" and "be cited by AI answers" produce different articles.

| Objective | What it changes |
|---|---|
| **Rank for the keyword** | length and depth compete with the incumbents, exact-phrase placement matters, internal links carry weight to the page, the SERP gate's verdict is close to decisive |
| **Be cited by answer engines** | extractable single-sentence claims, tight question-shaped headings, a byte-matched FAQ block, facts stated as plain attributes rather than adjectives, and a low-traffic keyword can still be worth building |
| **Convert existing traffic** | the offer and the objection handling matter more than the headline, and volume is nearly irrelevant |
| **Defend a term a competitor is taking** | speed over completeness, and the SERP gate reads as a warning rather than a veto |

On one account the second mattered more than the first, and a keyword with about ten
searches a month was correctly built because no ranking page carried the one line the
answer engines needed. That decision is impossible without having asked.

Also ask, when the client has any regulatory exposure: **which markets is this for?** A
site's `project.yaml` may carry `excluded_markets`, and a page written for a market the
client cannot address is waste at best.

## Confirm the plan, then stop

Play it back in a few lines. Not a document, not a brief. Something like:

```
Fresh article for <site>.
Keyword: <keyword>  (volume/difficulty not yet pulled)
Objective: <objective>, so the piece will <the one structural consequence>.
Next: pull the live SERP and run the SERP gate. If it rejects, I come back with
alternatives rather than writing.
Approve?
```

**Wait for approval.** Then hand to `research-chain`.

## Guardrails

- Never start research to "save time while they think about it". The plan can change the
  research, which is the whole reason the plan comes first.
- If the user declines to give an objective, record `objective: unstated` in the brief and
  say plainly that the article will be built to rank, because that is the default you fell
  back to. Do not pretend the question was answered.
- If the site is not yet onboarded, run `project-init` before proceeding.
- One article per run.
