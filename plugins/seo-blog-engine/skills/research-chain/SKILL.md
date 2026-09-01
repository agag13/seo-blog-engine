---
name: research-chain
description: Pull keyword and SERP data through a provider fallback chain and record which provider answered. Never guesses a number when a provider fails, and never reports a single-source figure as if it were corroborated. Use after intake and before any writing, and whenever a difficulty, volume, or trend figure is needed.
---

# Research chain

Two rules, and everything else is detail.

**1. Try providers in order, and record which one answered.** Not "as of today"; the actual
provider, per figure, written into the brief.

**2. When a provider fails, write down that it failed.** Never substitute a number from
somewhere else and let it stand where a corroborated figure was supposed to be. Five
articles have already shipped carrying a difficulty figure from one source only, and the
run doc says so in those words rather than inventing a second source. That is the standard.

## The chain

### SERP, which is the one that decides whether to build

| Order | Provider | Call |
|---|---|---|
| 1 | **DataForSEO** | `serp_organic_live_advanced`, with `location_name` and `language_code` set explicitly |
| 2 | **Tavily** | `tavily_search`. Only the ranking domains are trustworthy here; positions are not Google's |
| 3 | *stop* | There is no third. A keyword whose SERP could not be pulled does not get built |

Save the raw response to `<slug>.serp.json` and run `serp_gate.py` on it. The gate, not the
reading of it, decides.

### Volume, difficulty, trend

| Order | Provider | Call |
|---|---|---|
| 1 | **DataForSEO** | `dataforseo_labs_google_keyword_overview`, `dataforseo_labs_bulk_keyword_difficulty` |
| 2 | **DataForSEO Trends** | `kw_data_dfs_trends_explore` for the twelve-month series |
| 3 | **Ahrefs** | currently unavailable, see below. When it returns, it is the second source that makes the cross-check real |

### Geo-specific anything

**Built-in WebSearch is US-only.** For any question about a regulator, a market, or a rule
outside the US, use `tavily_search` with `country: "<Full Country Name>"`. Full name, not an
ISO code.

## Providers that are connected and broken, right now

These are connected, so a naive run will call them and get nothing. Do not silently rely on
them, and do not report their absence as "no data".

- **Ahrefs MCP: unauthorised.** Needs an OAuth flow in an interactive session. A
  non-interactive run cannot fix this, and should say so rather than retrying.
- **Apify route to Ahrefs: HTTP 403, `Monthly usage hard limit exceeded`.** The account is
  on the **free plan**. This returned 403 on the last day of one month and again on day one
  of the next. **It is not a quota that resets.** Waiting is not a plan; funding the account
  or buying the Ahrefs seat is.

When difficulty comes from DataForSEO alone, the brief says so in the difficulty row itself:

```
KD 9 (DataForSEO only. Ahrefs unavailable: OAuth unauthorised + Apify free-plan 403.)
```

That matters because the two sources genuinely disagree. One keyword read **KD 9 on
DataForSEO and KD 46 on Ahrefs**. A single-source figure is not wrong, it is unconfirmed,
and the brief must let a reader tell those apart.

## Stored keyword lists are candidates, never data

Re-pull at brief time. Every time.

Four of four keywords re-pulled after three weeks carried at least one wrong figure, and
**every error flattered the keyword**:

| Keyword shape | Board said | Live, three weeks later |
|---|---|---|
| a long-tail head term | difficulty 3, "lowest on the board" | difficulty 10, down 71% year on year |
| a category term | volume 1,300, down 28% | 1,000 average, 480 run rate, down 45% quarter on quarter |

**Mechanism: a trailing twelve-month average taken across a spike.** One term peaked in
February; the average captured in August still carried the peak. The stored number is not
stale in the sense of slightly old. It is describing a different world.

## Recording the answer

Every figure in a brief carries its provider. The research block looks like this:

```yaml
pulled_at: 2026-09-01
serp:        {provider: dataforseo, location: "United States", verdict: BUILD}
volume:      {value: 320, provider: dataforseo}
difficulty:  {value: 10, provider: dataforseo, corroborated: false,
              why: "Ahrefs unauthorised; Apify free-plan hard limit"}
trend_12mo:  {value: "-19%", provider: dataforseo-trends}
```

`corroborated: false` is not a defect to hide. It is the honest state of the account's
tooling, and it is what makes the decision to fund a second source visible.

## Guardrails

- Never write a number you did not pull in this run.
- Never fill a failed provider's figure from your own knowledge, or from the last brief.
- Never screen traffic quality on an estimated-traffic-value field. On one account it
  overstated a domain by 192x against a real measurement.
- A provider that returns an empty result is a failure, not a zero.
