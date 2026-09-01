# Worked example

A complete per-site context, filled in, so you can see the level of detail that actually
changes a draft. Copy the **shape**, not the content.

Everything here is invented. The brand is fictional, the domain is the reserved
documentation domain, and the numbers in the fingerprint are illustrative.

**`doctor.py` deliberately reports this folder as not-ready.** `site.url` is `example.com`,
which is exactly what the check is for. A real site replaces it. That the example fails its
own check is the check working.

## Files, and who fills each one

| File | Who supplies it | What it does |
|---|---|---|
| `project.yaml` | you | site, CMS, which gates are required |
| `BRAND.md` | client, plus your reading of their site | audience, positioning, honesty rules |
| `VOICE.md` | you, from their published writing | tone. **Enforces nothing** |
| `config/voice-fingerprint.yaml` | **measured** from 10+ published pieces | the bands. **This is the gate** |
| `PARTNERS.md` | **client must confirm** | who they are never written against |
| `FACTS.md` | you, auditing the client's own surfaces | every claim, with a status |

## The distinction people get wrong

`VOICE.md` and `voice-fingerprint.yaml` are not two versions of the same thing.

`VOICE.md` is prose for a human. It enforces nothing, because a model reads past prose
guidance. Anything that can be measured belongs in the fingerprint instead, where
`voice_check.py` can fail a build on it.

If you find yourself writing "keep paragraphs short" in `VOICE.md`, that is a number, and
it belongs in the other file.

## Try the gates before you write anything

`drafts/failing-sample.mdx` is deliberately broken. Run the gates on it:

```bash
python3 <plugin>/skills/quality-gates/scripts/run_gates.py \
  --project-root examples/worked-example \
  --mdx examples/worked-example/drafts/failing-sample.mdx
```

Expect **BLOCKED**, with roughly a dozen voice blocks and two facts blocks: an em dash, the
brand calling itself the best, a guaranteed outcome, "alternatives to" a partner, a
CONFLICTED user count, and a NOT PUBLISHED mobile app. Plus cadence warnings for a wall
paragraph.

It is worth seeing once. A block reads very differently from a score, and the difference is
the entire point of this layer.
