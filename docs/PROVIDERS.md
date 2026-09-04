# Research providers

What is connected, what answers, and what is broken in a way that waiting will not fix.

**Verified 2026-09-01**, by calling each one.

## Working

| Provider | Access | Verified how |
|---|---|---|
| **DataForSEO** | MCP, `mcp__claude_ai_dataforseo__*` | live `serp_organic_live_advanced` pull for `coinbase perpetual futures`, en / United States. Returned the full SERP plus the AI Overview and its citations |
| **Tavily** | MCP, `mcp__claude_ai_Tavily__*` | `tavily_search`, `tavily_extract`, `tavily_crawl`, `tavily_map`, `tavily_research`. **The only route for geo-specific search**, since built-in WebSearch is US-only |
| **Novamira WordPress** | MCP, one server **per site** | `mcp-adapter-discover-abilities` answered on the site tested: WordPress 7.1, PHP 8.2.29, Rank Math active, `create-post` / `update-post` available |

DataForSEO did most of the work on the reference account.

### Reddit, for discourse research

`api.redditapis.com`, bearer token, **$0.002 per read**. Verified by direct call.

Three endpoints matter, and two of them have a trap in the parameter name:

| Endpoint | Note |
|---|---|
| `/api/reddit/posts` | flat JSON, straightforward |
| `/api/reddit/search` | the parameter is **`q`**, not `query`. **Always pass `t`** |
| `/api/reddit/comments` | the parameter is **`permalink`**, not `id`. Returns Reddit's raw `{kind, data}` envelope, a different shape from the posts endpoint |

**On `t`:** Reddit defaults the time window to `all`, so a relevance query returns
years-old viral posts. A test that omitted it returned an r/AskHistorians survey and a
car-accident thread for a query about Google search results. That was a calling error,
not an API fault, and `discourse_pull.py` defaults to `t=year` so it cannot happen twice.

The response carries `listing_status: complete | truncated | unknown`, and the docs say
plainly not to treat `unknown` as the end of the data. That is the same honesty this
engine applies to its own gates, and it is worth trusting.

### X / GetXAPI, optional and off by default

`api.getxapi.com/twitter/...`, bearer token, **$0.001 per read**, parameter **`q`**.
There is also an MCP server: `claude mcp add getxapi npx -y @getxapi/mcp@latest`.

**Leave it unconfigured unless a client needs it.** Tested on a topic query it returned
13 posts, mostly automated "BREAKING NEWS" accounts, about one real opinion in five. A
tweet is a reaction; the article needs the reasoning underneath it, and that is on Reddit.

Where it does earn its cost is `get_mentions` against a **named account**. Entity
monitoring, not topic research. For a reputation-management client that is a service they
sell, not a content input, so it belongs in that client's config and nowhere else.

## Broken, and connected, which is the dangerous combination

A connected-but-broken provider gets called by a naive run and returns nothing. Neither of
these is a transient failure.

### Ahrefs MCP: unauthorised

Needs an OAuth flow in an interactive session. A non-interactive run **cannot** fix it and
should say so rather than retrying. Until it is authorised, there is no second difficulty
source.

### Apify route to Ahrefs: HTTP 403, and it is not a quota

```
HTTP 403  Monthly usage hard limit exceeded
```

The connected account is on the **free plan**. This returned 403 on 2026-08-31 and again on
2026-09-01, **day one of a new month**. There is no month boundary to wait for. The fix is
funding the account, authorising the Ahrefs connector, or buying the Ahrefs seat that has
been pending since August.

### Novamira, the servers that do not answer

Of three Novamira servers configured on the machine this was built on, **two failed to
connect**, one with `ENOTFOUND`. Each site has its own server, so this is normal and
permanent rather than an incident: some sites are local, some are retired, some were never
finished.

Check with `mcp-adapter-discover-abilities` before publishing, and **report a dead server
rather than skipping the publish step.**

## What this costs, stated plainly

The two-source difficulty cross-check is unenforceable right now. It earns its keep: one
keyword read **KD 9 on DataForSEO and KD 46 on Ahrefs**. Every difficulty figure produced
since late August is **DataForSEO-only**, and the briefs say so in the difficulty row rather
than implying corroboration that did not happen.

**Never guess a number when a provider fails. Write down that it failed.**

## Multi-account credentials

`templates/env.example` holds several numbered credentials per provider, and
`quality-gates/scripts/providers.py` rotates through them and logs which one served the
call. Quota exhaustion on a single key is exactly how the Ahrefs route was lost.

```bash
python3 plugins/seo-blog-engine/skills/quality-gates/scripts/providers.py
```

A provider with no credentials is reported as **unconfigured**, never as a provider that
returned no data. Those are different facts and a brief must be able to tell them apart.

## Two standing traps

- **Never screen traffic on an estimated-traffic-value field.** On the reference account it
  overstated one domain by **192x** against a real measurement: ETV 767 against real traffic
  of 4. A provider's domain rank is an acceptable stand-in for DR. Its ETV is not an
  acceptable stand-in for traffic.
- **Never write one provider's numbers into a field labelled with another provider's name.**
