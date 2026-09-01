# Voice Context

Fictional. **This file does not enforce anything**, and that is the most useful thing to
understand before writing one.

Prose guidance is read once and then read past. So everything here that can be measured
lives in `config/voice-fingerprint.yaml` instead, where `voice_check.py` can fail a build on
it. What stays in this file is the part a number cannot capture.

If you find yourself writing "keep paragraphs short" here, that is a number. Put it in the
fingerprint.

## Pronoun stance
"You" for the reader. "We" for the brand, sparingly. Never "I" outside a signed byline.

## What the measured gap usually is

Not rule compliance. **Cadence.**

Copy can pass every hard rule and still read corporate. On the account this engine was built
from, the founder's own essays ran **42.1% one-sentence paragraphs**, with **exactly one
paragraph over 70 words across 297**. The team's shipped articles ran 11.7%, with 62 walls
out of 290. Same rules, same facts, completely different rhythm.

The rhythm is what a reader feels as "written by a company".

Both of those are bands in the fingerprint, which is why they are enforceable and this
sentence is not.

## Headline patterns
- **Favour**: the question the reader actually typed. A real number when the number is
  load-bearing.
- **Avoid**: "Ultimate Guide", manufactured urgency, and numbers in a headline the body does
  not immediately support.

## Register
Casual-professional. Contractions are normal. Formal transitions like "However" and
"Furthermore" do not appear in this client's corpus at all, so the fingerprint blocks them.

## Readability target
Professional audience, but assume no vocabulary they have not already met inside the product.
Explain a term the first time and never again.
