# Product facts

Every product fact this site may state, with a status and a source.

Fictional, and abridged. A real one runs to sixty entries or more. These five show the
shape, including all three non-publishable states, because those are the entries that earn
the file.

## Statuses

| Status | Means | Publishable |
|---|---|---|
| `EVIDENCED` | a named source states it, and the source is linked | yes |
| `BETA` | true, but only with the qualifier attached | yes, qualified |
| `CONFLICTED` | the client's own surfaces disagree with each other | **no** |
| `NOT PUBLISHED` | nobody has stated it publicly | **no** |

`NOT PUBLISHED` is the one people argue with. An article stating it would be the **first
public statement** on the matter, which is a legal decision, not an editorial one.

---

## Maximum concurrent users per workspace

- status: CONFLICTED
- source: three figures across three of the client's own surfaces. 500 on the pricing page, 250 in the docs, "unlimited" in a marketing post. Escalated YYYY-MM-DD, unresolved.
- guard: (?i)\b(?:up to\s+)?[\d,]{2,7}\s+(?:concurrent\s+)?(?:users|seats)\b

**This is the entry that justifies the whole file.** The number was plausible, every source
carrying it was the client's own, and they disagreed. No amount of writer care catches that.
A regex does.

On the account this engine was built from, the equivalent entry was a leverage figure that
appeared four times across four client surfaces with an **8x spread**, including a product
page that contradicted its own meta description. It nearly published.

## Uptime guarantee

- status: NOT PUBLISHED
- source: no SLA is published anywhere. Sales quotes a number verbally; nothing is in writing.
- guard: (?i)\b(?:99\.\d+%|uptime\s+(?:guarantee|sla))\b

## Mobile app

- status: NOT PUBLISHED
- source: the roadmap page says "coming soon" and has said so for two quarters.
- guard: (?i)\b(?:our|the)\s+(?:ios|android|mobile)\s+app\b|\bapp store\b|\bgoogle play\b

## Audit log retention

- status: BETA
- source: changelog YYYY-MM-DD, verbatim "audit log export is in beta"
- guard: (?i)\baudit log\b(?:(?!\bbeta\b)[^.]){0,120}\.

Publishable only with the qualifier attached. The guard deliberately matches an audit-log
sentence that does **not** contain "beta", because that is the failure mode.

## SOC 2 Type II

- status: EVIDENCED
- source: trust page, report dated YYYY-MM-DD, read YYYY-MM-DD
- guard: (?i)\bSOC\s?2\b

---

## Writing a guard

Match the **claim**, not the sentence. A guard that only matches one phrasing gets walked
around by the next draft.

A guard will sometimes fire on a sentence about somebody else's product. That is the correct
trade: a false positive costs a reviewer ten seconds, and the miss it prevents was a live
defect on a money page.

A fact with no `guard` is documentation, not a gate, and `facts_check.py` says so rather
than passing it silently.

**Last reconciled against client surfaces:** YYYY-MM-DD

Product facts drift. Re-read the client's live surfaces at brief time for any fact the
article leans on, exactly as keyword data is re-pulled at brief time.
