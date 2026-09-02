# claims fixture

Five claims, four of them broken in a different way. The sources are cached, so
this runs offline and gives the same answer every time.

```bash
python3 ../../scripts/claims_check.py draft.mdx --source-cache cache --recency-months 36
```

Expected: **exit 2**, with exactly these four, and the first claim passing.

| Line | Rule | Why it is here |
|---|---|---|
| 5 | *(passes)* | Figure is on the page, hedge is not overstated. Must NOT block |
| 7 | `claim-uncited` | A figure with no source of its own |
| 9 | `value-not-in-source` | Real citation, page never gives that number |
| 11 | `qualifier-stronger-than-source` | Draft says "most", source says "some" |
| 13 | `source-too-old` | Figure IS on the page, but the page is 2021 |

Lines 11 and 13 are the two that matter most, because both look verified. The
source resolves, the source is real, and a two-check version passes them.

Line 5 earns its place too: it is the regression test for two false positives
that this fixture caught during development.

- "which is the figure **every**one quotes" fired the strongest hedge on the
  ladder, because the boundary guard only covered the start of the word.
- The uncited claim on line 7 borrowed line 9's citation, because the scan for a
  nearby source ran past the paragraph break.

Both would have made the gate untrustworthy in opposite directions: one blocking
clean copy, one waving through a bare assertion.
