#!/usr/bin/env python3
"""Pull what people actually say about a topic, and cache it so you pay once.

The SERP tells you what Google rewards. It does not tell you what the reader
believes, what they are afraid of, or the words they use. That comes from the
comment threads, and it changes the article's opening, its headings, its FAQ and
its call to action.

**Search finds the thread. Only the comments contain the objections.** From one
real thread about companies cold-calling to offer review removal:

    "100% pure scam. The only one that can remove Google reviews is Google."
    "It is possible they are the ones who added the bad reviews."
    "Most services only get paid when they are able to remove the review."

Three objections, in the reader's own words, that the article has to answer. No
search snippet carries them.

Division of labour
------------------
Finding the right threads is a semantic problem and Google is better at it than
Reddit's own search. So:

    the skill    calls Tavily, restricted to reddit.com, and passes the
                 permalinks here
    this script  hydrates them: comment trees, dedupe, cache, and the markdown
                 the writer reads

`--search` exists as a fallback when Tavily is unavailable. It hits Reddit's own
search, which is noisier. **Always pass a time window with it**: Reddit defaults
`t` to `all`, so a relevance query surfaces years-old viral posts. That default
is the single easiest way to get a useless result out of this API.

Paying once
-----------
`index.json` is checked before every paid call. A thread already cached is not
fetched again, and the run reports what it skipped and what that saved. This is
the point of the cache; the disk space is incidental.

Freshness is three-valued, not two. A thread pulled six months ago is perfectly
good evidence of *what was said in that thread*, and useless as *what people say
now*. The index records both the age and which of those two questions it can
still answer.

Usage
-----
    # normal path: the skill found these with Tavily
    python3 discourse_pull.py --slug remove-negative-reviews \\
        --urls https://reddit.com/r/SEO/comments/1n89m13/...

    # fallback, no Tavily
    python3 discourse_pull.py --slug x --search "remove negative reviews" --t year

    python3 discourse_pull.py --slug x --urls ... --dry-run   # costs nothing

Exit codes
----------
    0   pulled, or served entirely from cache
    1   partial: something could not be fetched, and it is named
    2   refused: no API key, or the call cap would be exceeded

Stdlib only. The key comes from the site's gitignored .env, never from a file in
the engine.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GATES = os.path.abspath(os.path.join(HERE, "..", "..", "quality-gates", "scripts"))
for _p in (HERE, GATES):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import site_config  # noqa: E402
import providers as prov  # noqa: E402

BASE = "https://api.redditapis.com/api/reddit"
COST_PER_CALL = 0.002
FRESH_DAYS, AGEING_DAYS = 30, 120

# Objection-shaped language. A comment matching one of these is doing the work
# the article has to answer, and gets lifted into the brief.
OBJECTION = [
    ("scam-or-distrust", r"\b(scam|scammer|shady|rip[- ]?off|fraud|don'?t trust|avoid|red flag)\b"),
    ("does-not-work", r"\b(doesn'?t work|didn'?t work|waste of (money|time)|useless|never worked)\b"),
    ("pricing", r"\b(cost|price|pricing|charge[ds]?|fee|expensive|how much|per month|upfront|retainer)\b"),
    ("only-way", r"\b(the only (way|one)|you can'?t|impossible to|no way to|cannot be)\b"),
    ("diy", r"\b(did it myself|do it yourself|on my own|without (paying|hiring))\b"),
    ("timeline", r"\b(how long|took (me )?\w+ (weeks?|months?)|still waiting|never heard back)\b"),
]


def classify(text: str) -> list:
    t = (text or "").lower()
    return [n for n, p in OBJECTION if re.search(p, t)]


# --------------------------------------------------------------------------- api

def key_or_die(providers: prov.Providers):
    creds = providers.credentials("redditapis")
    if not creds:
        print("discourse_pull: no REDDITAPIS_KEY_1 in the environment.\n"
              "  The discourse step cannot run, which means the article will be written\n"
              "  without knowing what people actually say about the topic.\n"
              "  Put the key in this site's gitignored .env. See templates/env.example.",
              file=sys.stderr)
        return None
    return creds


def call(path: str, params: dict, cred, timeout: int = 30):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + cred.value})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


def permalink_of(url: str) -> str:
    p = urllib.parse.urlparse(url).path
    return p if p.startswith("/r/") else url


def thread_id(permalink: str) -> str:
    m = re.search(r"/r/([^/]+)/comments/([a-z0-9]+)", permalink, re.I)
    return f"{m.group(1).lower()}-{m.group(2)}" if m else re.sub(r"\W+", "-", permalink)[:60]


# --------------------------------------------------------------------------- store

class Store:
    def __init__(self, root: str):
        self.dir = os.path.join(root, "research", "discourse")
        self.threads = os.path.join(self.dir, "threads")
        os.makedirs(self.threads, exist_ok=True)
        self.index_path = os.path.join(self.dir, "index.json")
        self.index = (json.load(open(self.index_path, encoding="utf-8"))
                      if os.path.exists(self.index_path) else {})

    def age_days(self, tid: str):
        e = self.index.get(tid)
        if not e or not e.get("fetched_at"):
            return None
        try:
            return (dt.date.today() - dt.date.fromisoformat(e["fetched_at"])).days
        except ValueError:
            return None

    def freshness(self, tid: str) -> str:
        a = self.age_days(tid)
        if a is None:
            return "missing"
        return "fresh" if a <= FRESH_DAYS else ("ageing" if a <= AGEING_DAYS else "stale")

    def load(self, tid: str):
        p = os.path.join(self.threads, tid + ".json")
        return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

    def save(self, tid: str, doc: dict, slug: str):
        json.dump(doc, open(os.path.join(self.threads, tid + ".json"), "w",
                            encoding="utf-8"), indent=1, ensure_ascii=False)
        e = self.index.setdefault(tid, {})
        e.update({"id": tid, "subreddit": doc.get("subreddit"), "title": doc.get("title"),
                  "comments": len(doc.get("comments") or []),
                  "objections": sorted({o for c in doc.get("comments") or []
                                        for o in c.get("objections") or []}),
                  "fetched_at": dt.date.today().isoformat(),
                  "permalink": doc.get("permalink")})
        used = set(e.get("used_by") or [])
        used.add(slug)
        e["used_by"] = sorted(used)

    def mark_used(self, tid: str, slug: str) -> None:
        """Record the article even when the thread came from cache.

        Without this the index only ever credits the article that first paid for
        a thread, and the cross-article picture, which is the whole reason the
        cache is worth keeping, never builds up.
        """
        e = self.index.get(tid)
        if not e:
            return
        used = set(e.get("used_by") or [])
        used.add(slug)
        e["used_by"] = sorted(used)

    def flush(self):
        json.dump(self.index, open(self.index_path, "w", encoding="utf-8"),
                  indent=1, ensure_ascii=False, sort_keys=True)


def trim_thread(payload: dict, permalink: str) -> dict:
    """Reddit returns ~200KB per thread and about a tenth of it is readable.

    Keeping the raw envelope would make the cache expensive to store, slow to
    grep and unpleasant to read, for fields nothing uses.
    """
    post = payload.get("post") or {}
    out = []
    for node in payload.get("comments") or []:
        d = node.get("data") if isinstance(node, dict) and "data" in node else node
        if not isinstance(d, dict):
            continue
        body = (d.get("body") or "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue
        out.append({"body": body, "score": d.get("score") or d.get("ups") or 0,
                    "author": d.get("author"), "objections": classify(body)})
    out.sort(key=lambda c: -(c["score"] or 0))
    return {"permalink": permalink,
            "title": post.get("title") or payload.get("title"),
            "subreddit": post.get("subreddit") or payload.get("subreddit"),
            "url": "https://reddit.com" + permalink if permalink.startswith("/") else permalink,
            "upvotes": post.get("upvotes"), "created": post.get("created"),
            "comments": out,
            "withheld": sum(1 for n in payload.get("comments") or []
                            if isinstance(n, dict)
                            and ((n.get("data") or {}).get("body") in ("[deleted]", "[removed]"))),
            "listing_status": payload.get("listing_status")}


# --------------------------------------------------------------------------- output

def write_brief(root: str, slug: str, threads: list) -> str:
    """Markdown, because this is the file a human and Obsidian both read.

    Wikilinks are deliberate: opened as a vault, the graph shows which objections
    recur across articles, which is the thing worth knowing.
    """
    by_obj: dict = {}
    for t in threads:
        for c in t["comments"]:
            for o in c["objections"]:
                by_obj.setdefault(o, []).append((c, t))

    lines = [f"# Discourse: {slug}", "",
             f"Pulled {dt.date.today().isoformat()} from {len(threads)} thread(s). "
             f"Objections are ordered by how often they recur, not by upvotes.", ""]

    if not by_obj:
        lines += ["No objection-shaped comments found. Either the threads are thin, "
                  "or the topic genuinely has no contested points. Read them yourself "
                  "before assuming the second.", ""]

    for obj, hits in sorted(by_obj.items(), key=lambda kv: -len(kv[1])):
        lines += [f"## {obj}", "",
                  f"Seen in {len(hits)} comment(s) across "
                  f"{len({t['permalink'] for _, t in hits})} thread(s).", ""]
        for c, t in sorted(hits, key=lambda x: -(x[0]["score"] or 0))[:3]:
            quote = " ".join(c["body"].split())[:280]
            lines += [f"> {quote}", "",
                      f"— r/{t['subreddit']}, {c['score']} up · "
                      f"[[{thread_id(t['permalink'])}]]", ""]

    lines += ["## Threads", ""]
    for t in threads:
        w = f" · {t['withheld']} comment(s) deleted or removed" if t.get("withheld") else ""
        lines += [f"- [[{thread_id(t['permalink'])}]] — r/{t['subreddit']}, "
                  f"{len(t['comments'])} readable comment(s){w}",
                  f"  <{t['url']}>"]
    lines += ["", "---", "",
              "The thread is not the whole conversation. Comments get deleted and "
              "removed, and the counts above say how many. Treat a quiet thread as "
              "unproven rather than settled."]

    out = os.path.join(root, "research", f"DISCOURSE-{slug}.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="the article this is for")
    ap.add_argument("--urls", nargs="*", default=[],
                    help="reddit thread URLs, normally found with Tavily by the skill")
    ap.add_argument("--search", default=None,
                    help="fallback: search Reddit directly. Noisier than Tavily")
    ap.add_argument("--t", default="year",
                    help="time window for --search: hour|day|week|month|year|all. "
                         "Reddit defaults to `all`, which surfaces years-old viral "
                         "posts, so this defaults to `year` instead (default: year)")
    ap.add_argument("--max-threads", type=int, default=5,
                    help="objections repeat; past about five threads you stop learning "
                         "anything new and only spend money (default 5)")
    ap.add_argument("--max-calls", type=int, default=12)
    ap.add_argument("--refresh", action="store_true",
                    help="re-fetch even if cached. Off by default, which is the point")
    ap.add_argument("--dry-run", action="store_true", help="plan only, spend nothing")
    ap.add_argument("--json", action="store_true")
    site_config.add_root_arg(ap)
    a = ap.parse_args()

    root = site_config.find_project_root(os.getcwd(), a.project_root)
    store = Store(root)
    providers = prov.Providers()
    calls = 0
    notes: list = []

    creds = None
    if not a.dry_run:
        creds = key_or_die(providers)
        if creds is None:
            return 2
    cred = creds[0] if creds else None

    # ---- decide the target list -------------------------------------------
    targets = [permalink_of(u) for u in a.urls]
    if a.search and not targets:
        if a.dry_run:
            notes.append(f"would search Reddit for {a.search!r} with t={a.t}")
        else:
            d, err = call("/search", {"q": a.search, "sort": "relevance", "t": a.t,
                                      "limit": 25, "min_comments": 3}, cred)
            calls += 1
            if err:
                notes.append(f"search failed: {err}")
            else:
                targets = [p.get("permalink") for p in (d.get("posts") or [])
                           if p.get("permalink")]
    if not targets and not a.dry_run:
        print("discourse_pull: nothing to pull. Pass --urls from a Tavily search, "
              "or --search as a fallback.", file=sys.stderr)
        return 1

    # ---- cache first, always ----------------------------------------------
    plan, cached, saved = [], [], 0.0
    for permalink in targets:
        if len(plan) + len(cached) >= a.max_threads:
            break
        tid = thread_id(permalink)
        state = store.freshness(tid)
        if state != "missing" and not a.refresh:
            doc = store.load(tid)
            if doc:
                cached.append((tid, doc, state))
                store.mark_used(tid, a.slug)
                saved += COST_PER_CALL
                continue
        plan.append((tid, permalink))

    if a.dry_run:
        print(f"discourse_pull · {a.slug} · DRY RUN, nothing spent\n")
        for tid, _, state in cached:
            print(f"  cached  {tid}  ({state})")
        for tid, _ in plan:
            print(f"  fetch   {tid}")
        for n in notes:
            print(f"  note    {n}")
        print(f"\n  would fetch {len(plan)}, reuse {len(cached)}, "
              f"cost ${len(plan) * COST_PER_CALL:.3f}, saved ${saved:.3f}")
        return 0

    # ---- fetch what is genuinely missing -----------------------------------
    threads = [doc for _, doc, _ in cached]
    for tid, permalink in plan:
        if calls >= a.max_calls:
            notes.append(f"stopped at the {a.max_calls}-call cap")
            break
        d, err = call("/comments", {"permalink": permalink, "limit": 60}, cred)
        calls += 1
        if err:
            providers.record(cred.provider if cred else "redditapis", cred, False, err)
            notes.append(f"{tid}: {err}")
            continue
        doc = trim_thread(d, permalink)
        store.save(tid, doc, a.slug)
        threads.append(doc)
    if cred and calls:
        providers.record("redditapis", cred, True)
    store.flush()

    brief = write_brief(root, a.slug, threads) if threads else None
    stale = [tid for tid, _, s in cached if s == "stale"]
    verdict = 1 if (notes or stale) else 0

    if a.json:
        print(json.dumps({"slug": a.slug, "threads": len(threads), "fetched": len(plan),
                          "from_cache": len(cached), "calls": calls,
                          "cost": round(calls * COST_PER_CALL, 4),
                          "saved": round(saved, 4), "brief": brief,
                          "stale": stale, "notes": notes}, indent=2))
        return verdict

    print(f"discourse_pull · {a.slug}")
    print(f"  {len(threads)} thread(s): {len(plan)} fetched, {len(cached)} from cache")
    print(f"  {calls} call(s), ${calls * COST_PER_CALL:.3f} spent, ${saved:.3f} saved by the cache")
    if brief:
        print(f"  brief: {brief}")
    for tid in stale:
        print(f"  STALE  {tid} is over {AGEING_DAYS} days old. Fine as evidence of what "
              f"was said; not evidence of what people say now. --refresh to re-pull.")
    for n in notes:
        print(f"  NOTE   {n}")
    print("\n" + ("OK" if verdict == 0 else "OK with gaps, read the notes"))
    return verdict


if __name__ == "__main__":
    sys.exit(main())
