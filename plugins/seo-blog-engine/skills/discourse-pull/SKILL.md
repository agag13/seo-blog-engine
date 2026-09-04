---
name: discourse-pull
description: Find out what people actually say about a topic, in their own words, and cache it so the same thread is never paid for twice. Tavily finds the threads, the Reddit API pulls the comment trees where the real objections live. Produces a DISCOURSE-<slug>.md the writer reads alongside the brief. Use after the SERP gate and before drafting, or when the user says "what are people saying about X", "find the objections", "discourse research".
---

# Discourse pull

The SERP tells you what Google rewards. It does not tell you what the reader believes,
what they are afraid of, or the words they use for the thing.

**That gap is where most weak articles come from.** The page answers the question the
keyword implies, and the reader arrives carrying a different question entirely.

## What this actually changes in the article

One real thread, about companies cold-calling a business owner offering to remove bad
reviews:

> "100% pure scam. The only one that can remove Google reviews is Google."
> "It is possible they are the ones who added the bad reviews and are asking for money."
> "Most services only get paid when they are able to remove the review."

Those three comments move six things:

| Part of the article | What changes |
|---|---|
| Opening paragraph | The reader's first question is not "how do I do this", it is "are you a scam". Answer that or lose them in three lines |
| "What usually fails" | Stops being your guess and becomes evidence |
| A section nobody else writes | Pricing model. People are asking *when* they pay, not what it costs |
| FAQ | Raw questions in the reader's words, not Google's cleaned-up PAA phrasing |
| Title and H2s | Which noun people actually use: reviews, articles, results, content |
| Before the CTA | If the scam objection is unanswered, the reader stops at the CTA, because you sound like the cold call |

## The split, and why it is this way

**Tavily finds. Reddit hydrates.**

Tested head to head on the same query. Tavily returned 10 of 10 on-topic threads;
Reddit's own search returned about 5 of 11, because Google understands the question and
Reddit matches keywords.

But **only Reddit gives the comments**, and the comments are the entire point. A search
snippet never contains an objection.

So:

1. **You** call `tavily_search` with `include_domains: ["reddit.com"]`
2. Pass the permalinks to the script
3. The script pulls comment trees, caches them, and writes the brief

```bash
python3 scripts/discourse_pull.py --slug <article-slug> \
  --urls <reddit-url> <reddit-url> ...
```

Add `--dry-run` first if you want to see what it would cost. It spends nothing.

### If Tavily is unavailable

```bash
python3 scripts/discourse_pull.py --slug x --search "..." --t year
```

`--search` hits Reddit's own search and is noticeably noisier. **Never drop the time
window.** Reddit defaults `t` to `all`, so a relevance query pulls years-old viral posts;
that default produced an r/AskHistorians survey and a car-accident thread on a query
about Google search results. The script defaults `--t year` for exactly this reason.

## The cache is the point

`index.json` is checked before any paid call. A thread already stored is not fetched
again, and the run prints what it reused and what that saved.

The second article on a related topic frequently costs **nothing at all**, because the
threads are already there. The index records every article that used each thread, so
over time you can see which objections recur across the whole account.

Freshness is three-valued, not two:

| State | Age | Means |
|---|---|---|
| `fresh` | ≤ 30 days | good for "what are people saying now" |
| `ageing` | ≤ 120 days | usable, prefer a re-pull |
| `stale` | older | still fine as evidence of **what was said in that thread**, not as evidence of what people say **now** |

That distinction is deliberate. Treating a cached pull as automatically current is the
same mistake as trusting a stored keyword board, where four of four keywords re-pulled
after three weeks carried a wrong figure and every error flattered the keyword.

## What it writes

```
<site>/research/
  discourse/
    index.json                 the spine. Read before spending
    threads/<id>.json          trimmed payload, ~20KB not ~200KB
  DISCOURSE-<slug>.md          the brief the writer reads
```

The brief is markdown with `[[wikilinks]]`, so pointing Obsidian at the folder gives you
a graph of which objections recur across which articles, with no integration work. The
raw cache stays JSON, for the agent.

Keep this **committed**. The whole point is that the team does not pay twice, and a
gitignored cache is a cache each machine refills at its own expense.

## Budget

About **one cent per article**. Five threads is the default cap because objections
repeat: past roughly five you stop learning and only spend.

The key lives in the site's gitignored `.env` as `REDDITAPIS_KEY_1`. If it is missing the
script refuses and says plainly that the article will otherwise be written without
knowing what people say about the topic. It does not carry on quietly.

## Guardrails

- Never skip the time window on `--search`.
- Never treat a `stale` cache hit as current discourse. Re-pull, or say in the brief
  that the evidence is old.
- **Read the thread counts.** The brief reports how many comments were deleted or
  removed. On the reference thread the two highest-voted comments were both `[removed]`;
  a quiet thread is unproven, not settled.
- Public posts only. This reads what people chose to publish.
- One article per run.
