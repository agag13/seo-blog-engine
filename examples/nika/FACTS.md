# Product facts

Worked example. Generated from that client's `docs/nika-product-truth.md`, read 2026-09-01.
Abridged: the full ledger runs to about sixty facts. These are the ones that show the shape,
including every non-publishable one, because those are the entries that earn the file.

## Maximum leverage

- status: CONFLICTED
- source: four figures across four of the client's own surfaces, an 8x spread. 200x on the client blog, 50x on the product page, 40x in the GitBook, 25x in that same product page's own meta description. Escalated 2026-08-31, unresolved.
- guard: (?i)\b(?:up to\s+)?\d{2,3}\s*x\s+(?:max(?:imum)?\s+)?leverage\b

**This is the fact that justifies the whole file.** The number was in a brief, it was
plausible, every surface that carried it was the client's own, and they disagreed with each
other by a factor of eight. No amount of writer care catches that. A regex does.

## Prediction markets fee

- status: NOT PUBLISHED
- source: the client's `fees.md` covers perps, spot and the non-crypto venue only. It publishes no prediction-markets fee at all.
- guard: (?i)\bprediction (?:market|markets)\b[^.]{0,80}\b(?:fee|fees|costs?|free)\b

Stating this either way, including "free", would be the first public statement on it. One
article's FAQ already shipped an answer here and had to be corrected.

## Mobile app

- status: NOT PUBLISHED
- source: the client's `mobile-app.md` is empty and its `llms.txt` says "Coming soon".
- guard: (?i)\b(?:our|the|its)\s+(?:ios|android|mobile)\s+app\b|\bapp store\b|\bgoogle play\b

## Smart-contract and vault architecture

- status: CONFLICTED
- source: "no smart-contract lock-in or hidden vaults" on one surface, against the EVM execution model described elsewhere in the same docs set.
- guard: (?i)\bno\s+(?:smart[- ]contract\s+lock[- ]in|hidden vaults)\b

## Prediction markets are in beta

- status: BETA
- source: client `predictions.md`, verbatim "Predictions is currently in beta"
- guard: (?i)\bprediction[s]?\b(?:(?!\bbeta\b)[^.]){0,120}\.

Publishable only with the beta qualifier attached. The guard deliberately matches a
prediction-markets sentence that does *not* contain "beta", which is the failure mode.

## Seven supported networks

- status: EVIDENCED
- source: client `supported-tokens-and-networks.md` and `deposit-crypto.md`, which state the list twice: Ethereum Mainnet, Arbitrum, Base, BNB Chain, Solana, Optimism, Polygon
- guard: (?i)\bsupport(?:s|ed)?\s+\w{0,12}\s*networks?\b

## Keys are split with MPC, and are exportable

- status: EVIDENCED
- source: client `smart-accounts.md`, verbatim "MPC does not mean custodial. Users can always export their full private key if desired." Exports into MetaMask on EVM, Phantom or Solflare on Solana.
- guard: (?i)\bMPC\b|\bexport (?:your|the) (?:full )?private key\b

## Gas is sponsored

- status: EVIDENCED
- source: client `smart-accounts.md`. Users need no ETH on EVM and no SOL on Solana.
- guard: (?i)\bgas is sponsored\b|\bno (?:ETH|SOL) (?:is )?(?:required|needed)\b

## Perps funding settles hourly

- status: EVIDENCED
- source: client `funding-rate.md`
- guard: (?i)\bfunding\b[^.]{0,40}\b(?:hourly|every hour)\b

---

**Last reconciled against client surfaces:** 2026-08-17, with the leverage escalation added
2026-08-31.

Two of the nine entries above changed status between those two dates. Re-read the client's
live surfaces at brief time for any fact the article leans on.
