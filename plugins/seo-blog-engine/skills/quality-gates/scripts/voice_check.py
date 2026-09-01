#!/usr/bin/env python3
"""Voice gate: mechanical cadence and brand rules, blocking.

Prose guidance in a VOICE.md does not work, because a model reads past it. A
number fails. This gate checks a draft against the measured cadence bands in the
site's config/voice-fingerprint.yaml and against that site's own banned
structures, and returns a non-zero exit code the pipeline cannot ignore.

Everything here is mechanical. The read-aloud test and the tone test stay human.

The site is resolved from the file being checked (see site_config.py), so the
same engine copy checks any site without editing the script.

Usage
-----
    python3 voice_check.py drafts/what-is-a-crypto-bridge.mdx
    python3 voice_check.py --profile founder-essay drafts/guest-post.md
    python3 voice_check.py --json drafts/*.mdx

Exit codes
----------
    0   clean
    1   warnings only, drift worth a look
    2   at least one BLOCK, the draft does not ship

Blocks are voice-rules.md violations and hard AI tells. Warnings are cadence
drift against the fingerprint bands. The article-register bands are
deliberately *corrective*: they sit between the shipped corpus and Daniel's
own essays, so an existing article warning on cadence is the tool working, not
a false positive. See the header of config/voice-fingerprint.yaml.

Stdlib only, so the gate never fails on a missing dependency.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import site_config  # noqa: E402

# Resolved per run from the target file, never from __file__. See site_config.
REPO = os.getcwd()

# Words voice-extractor's global list bans, minus the ones this domain needs.
# `leverage` is handled separately: legitimate as a financial noun, banned as a verb.
GLOBAL_BANNED = [
    "delve", "robust", "synergy", "paradigm", "unleash", "empower",
    "revolutionize", "revolutionise", "revolutionary", "seamless", "seamlessly",
    "game-changing", "game changer", "world-class", "best-in-class",
    "cutting-edge", "next-gen", "disrupt", "move the needle", "circle back",
    "we are committed to", "we pride ourselves on", "tapestry", "plethora",
    "meticulous", "ever-evolving", "embark", "harness the",
]

# `leverage`/`leveraging` used as a verb. The noun ("no margin and no leverage")
# is correct financial English and appears throughout the shipped corpus.
LEVERAGE_VERB = re.compile(
    r"\bleverag(?:e|es|ed|ing)\s+(?:our|your|their|its|the|this|these|a|an)\b", re.I
)

STRUCTURE_BLOCKS = [
    ("not-just-x-its-y", r"(?i)\bit'?s not just .*?,? it'?s\b",
     "The 'it's not just X, it's Y' construction is an AI tell."),
    ("imagine-if-opener", r"(?im)^(Imagine if|Picture this|What if I told you)\b",
     "Banned opener."),
    ("in-todays-adjective-world", r"(?i)\bin today'?s [a-z-]+ (world|landscape|market)\b",
     "Banned opener construction."),
    ("now-more-than-ever", r"(?i)\bnow more than ever\b", "Empty intensifier."),
    ("ever-evolving-landscape", r"(?i)\bever[- ](evolving|changing) (landscape|world|industry)\b",
     "AI tell."),
    ("stray-placeholder", r"\{[a-z _]+\}|\[[A-Z_ ]{3,}\]|<<[A-Z_ ]+>>",
     "Unfilled placeholder left in the draft."),
]
# Everything above is a generic AI tell and ships with the engine. Anything
# brand-specific ("never call us the best", "the bio says founder, not CEO")
# belongs in the site's voice-fingerprint.yaml under `banned_structures`, and is
# appended to this list at load time.

def partner_pattern(partners: list[str], brand: str | None):
    """Competitive framing aimed at a partner. Blocking.

    A prose honesty rule does not stop an agent writing "alternatives to X"
    about a partner, because the agent is optimising for the SERP and the rule
    is a sentence in a file it read once. This is the same rule as a regex.
    """
    if not partners:
        return None
    p = "|".join(re.escape(x) for x in partners)
    alt = (rf"\b(?:{p})\s+(?:alternatives?|competitors?|rivals?)\b"
           rf"|\balternatives?\s+to\s+(?:{p})\b"
           rf"|\b(?:best|top)\s+(?:{p})\s+\w+\b")
    if brand:
        b = re.escape(brand)
        alt += rf"|\b{b}\s+vs\.?\s+(?:{p})\b|\b(?:{p})\s+vs\.?\s+{b}\b"
    return re.compile(alt, re.I)


def load_partners(root: str) -> tuple[list[str], str | None]:
    """Read partner names out of the site's PARTNERS.md.

    Format is one partner per `## Name` heading, which keeps the file readable
    for the client and parseable for the gate.
    """
    path = site_config.context_file(root, "PARTNERS.md")
    if not path:
        return [], path
    names = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not m.group(1).lower().startswith(("how ", "why ", "what ")):
            names.append(m.group(1).strip())
    return names, path

# Sites with a list-shaped domain (chains, integrations, supported banks) drift
# into enumerating it. Declared per site as `enumeration_watch` in the
# fingerprint; empty means the check does not run.

CONTRACTIONS = re.compile(r"\b\w+['’](?:s|t|re|ve|ll|d|m)\b", re.I)
CONTRACTIBLE = re.compile(
    r"\b(?:it is|that is|there is|do not|does not|did not|is not|are not|was not|were not|"
    r"cannot|will not|would not|should not|could not|has not|have not|had not|you are|"
    r"we are|they are|i am|you will|we will|they will|it will|you have|we have|they have|"
    r"i have|let us)\b", re.I,
)

TRANSITION_BLOCK = re.compile(r"(?m)(?:^|(?<=[.!?]\s))(However|Furthermore|Moreover|Additionally)[,\s]")


# --------------------------------------------------------------------------- fingerprint

def load_fingerprint(profile: str | None, path: str):
    """Read the fingerprint. Falls back to hardcoded defaults if PyYAML is absent,
    because a missing dependency must never silently disable the gate."""
    defaults = {
        "cadence_mean": 13.0, "cadence_p90": 24, "cv_floor": 0.50,
        "para_max_words": 70, "one_sent_para": 0.25, "contraction_rate": 0.35,
        "mattr_floor": 0.78, "banned_user": [], "signature": [], "em_dash": "never",
        "structures": [], "enumeration_watch": [],
        "_source": f"built-in defaults (no fingerprint read at {path})",
    }
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return defaults
    if not os.path.exists(path):
        return defaults
    try:
        doc = yaml.safe_load(open(path))
    except Exception as exc:  # noqa: BLE001
        defaults["_source"] = f"parse failed ({exc}); using built-in defaults"
        return defaults

    profiles = doc.get("profiles", {}) or {}
    pid = profile or doc.get("active") or (next(iter(profiles), None))
    p = profiles.get(pid)
    if not p:
        defaults["_source"] = f"profile '{pid}' not found; using built-in defaults"
        return defaults

    sl = p["cadence"]["sentence_length"]
    pl = p["cadence"]["paragraph_length"]
    return {
        "profile": pid,
        "cadence_mean": sl["mean"],
        "cadence_p90": sl["p90"],
        "cv_floor": sl.get("length_cv_floor", 0.50),
        "para_max_words": pl.get("max_words", 70),
        "one_sent_para": pl["one_sentence_paragraph_frequency"],
        "contraction_rate": p["mechanics"]["contraction_rate"],
        "mattr_floor": p["lexical"].get("mattr_floor", 0.78),
        "em_dash": p["mechanics"]["em_dash_usage"],
        "banned_user": doc.get("banned_words_user_specific", []),
        "signature": p.get("idioms", {}).get("signature_phrases", []),
        # Brand rules the engine cannot know. Each entry: id, pattern, why.
        "structures": doc.get("banned_structures", []) or [],
        "enumeration_watch": doc.get("enumeration_watch", []) or [],
        "_source": path,
    }


# --------------------------------------------------------------------------- parsing

def split_doc(path: str):
    """Return (headings, body_paragraphs, full_text_for_regex, lede)."""
    raw = open(path, encoding="utf-8", errors="replace").read()

    if path.endswith((".html", ".htm")):
        import html as _html
        raw = re.sub(r"(?is)<(script|style|head|nav|footer)[^>]*>.*?</\1>", " ", raw)
        heads = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
                 for h in re.findall(r"(?is)<h[1-3][^>]*>(.*?)</h[1-3]>", raw)]
        body = re.sub(r"(?is)<h[1-6][^>]*>.*?</h[1-6]>", " ", raw)
        paras = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", p))).strip()
                 for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
        paras = [p for p in paras if len(p.split()) > 6]
        return heads, paras, "\n\n".join(heads + paras), (paras[0] if paras else "")

    # markdown / mdx
    body = re.sub(r"(?s)^---.*?\n---\n", "", raw)          # frontmatter
    fm = re.search(r"(?s)^---(.*?)\n---\n", raw)
    body = re.sub(r"(?s)\{/\*.*?\*/\}", "", body)          # mdx handover comments
    body = re.sub(r"(?s)```.*?```", "", body)
    # Inline SVG diagrams are markup, not prose. Since docs/diagram-spec-2026-09-01.md
    # mandates inline SVG in the MDX (rather than a file), leaving it in the cadence
    # corpus produces false wall-paragraph hits and tanks MATTR on repeated attribute
    # names (textAnchor, fontFamily, fill). The <figcaption> is real prose and stays.
    body = re.sub(r"(?is)<svg\b.*?</svg>", "", body)
    heads = re.findall(r"(?m)^#{1,3} (.+)$", body)
    # Frontmatter title and description are published copy and must be scanned.
    # They are prepended to the regex surface, never to the cadence corpus.
    surface = ""
    if fm:
        for field in ("title", "description"):
            v = re.search(rf'(?m)^{field}:\s*"?(.*?)"?\s*$', fm.group(1))
            if v and v.group(1):
                surface += v.group(1) + "\n"
                if field == "title":
                    heads.insert(0, v.group(1))
    nohead = re.sub(r"(?m)^#{1,6} .*$", "", body)
    nohead = re.sub(r"(?m)^\s*\|.*$", "", nohead)          # tables
    nohead = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", nohead)
    nohead = re.sub(r"[*_`]", "", nohead)
    paras = []
    for p in nohead.split("\n\n"):
        t = re.sub(r"\s+", " ", p).strip()
        t = re.sub(r"^>\s*", "", t)
        if len(t.split()) > 6:
            paras.append(t)
    return heads, paras, surface + body, (paras[0] if paras else "")


def sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“])", re.sub(r"\s+", " ", text))
    return [p.strip() for p in parts if len(p.strip()) > 1]


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


# --------------------------------------------------------------------------- checks

def check(path: str, fp: dict, partner_re=None) -> list[dict]:
    heads, paras, full, lede = split_doc(path)
    body = "\n\n".join(paras)
    out: list[dict] = []

    def add(sev, rule, msg, line=None, match=None):
        out.append({"severity": sev, "rule": rule, "message": msg,
                    "line": line, "match": (match or "")[:90]})

    # ---- BLOCKS -----------------------------------------------------------
    if fp["em_dash"] == "never":
        for m in re.finditer(r"[—–]|(?<![-<!])--(?![->])", full):
            add("BLOCK", "em-dash",
                "No em dashes anywhere. Substitute a comma, semicolon, period, or middot.",
                line_of(full, m.start()), full[max(0, m.start() - 40):m.start() + 40])

    # Engine rules always block. A site rule blocks unless it declares
    # `severity: warn`, because some brand rules are judgment calls and a gate
    # that blocks on a judgment call gets switched off.
    site_structures = [(d.get("id", "banned-structure"), d.get("pattern"), d.get("why", ""),
                        (d.get("severity") or "block").upper())
                       for d in fp.get("structures", []) if isinstance(d, dict)]
    for rule, pat, why, sev in [(r, p_, w, "BLOCK") for r, p_, w in STRUCTURE_BLOCKS] + site_structures:
        if not pat:
            # A declared rule with no pattern is measured elsewhere (e.g. wall
            # paragraphs). Not an error, and not silently dropped either.
            continue
        try:
            hits = list(re.finditer(pat, full))
        except re.error as exc:
            add("BLOCK", "bad-structure-pattern",
                f"banned_structures entry '{rule}' is not a valid regex: {exc}")
            continue
        for m in hits:
            add("BLOCK" if sev == "BLOCK" else "WARN", rule, why,
                line_of(full, m.start()), m.group(0))

    if partner_re is not None:
        for m in partner_re.finditer(full):
            add("BLOCK", "partner-as-target",
                "Partners are never comparison targets. See this site's PARTNERS.md.",
                line_of(full, m.start()), m.group(0))

    for w in GLOBAL_BANNED:
        for m in re.finditer(r"\b" + re.escape(w).replace(r"\ ", r"\s+") + r"\b", full, re.I):
            add("BLOCK", "banned-word-global",
                f"'{w}' is on the AI-slop banned list.",
                line_of(full, m.start()), m.group(0))

    for m in LEVERAGE_VERB.finditer(full):
        add("BLOCK", "leverage-as-verb",
            "'leverage' is fine as a financial noun, banned as a verb.",
            line_of(full, m.start()), m.group(0))

    # The named STRUCTURE_BLOCKS above already cover several of these with a
    # better message. Only report a banned word if nothing more specific fired
    # on the same span.
    claimed = {(x["line"], x["match"].lower()) for x in out}
    for w in fp["banned_user"]:
        for m in re.finditer(re.escape(w), full, re.I):
            if (line_of(full, m.start()), m.group(0).lower()) in claimed:
                continue
            add("BLOCK", "banned-word-site", f"'{w}' is banned for this site's copy.",
                line_of(full, m.start()), m.group(0))

    for m in TRANSITION_BLOCK.finditer(body):
        add("BLOCK", "formal-transition",
            f"'{m.group(1)}' does not appear in this site's voice corpus.",
            line_of(body, m.start()), m.group(0))

    # ---- WARNINGS ---------------------------------------------------------
    watch = fp.get("enumeration_watch", [])
    hit = sorted({c for c in watch if re.search(r"\b" + re.escape(c) + r"\b", body, re.I)})
    if len(hit) >= 2:
        add("WARN", "list-enumeration",
            f"Enumerates {len(hit)} of the watched set ({', '.join(hit)}). Name the category "
            f"unless the full list is load-bearing to the argument.")

    h1 = heads[0] if heads else ""
    for m in re.finditer(r"\b\d[\d,.]*\b", h1):
        if not re.fullmatch(r"20\d\d", m.group(0)):
            add("WARN", "number-in-headline",
                f"Hard number '{m.group(0)}' in the H1. Only the year is allowed.")
    for m in re.finditer(r"\$[\d,.]+|\b\d[\d,.]{2,}\b", lede):
        add("WARN", "number-in-lede",
            f"Hard number '{m.group(0)}' in the lede. Qualitative framing in surface copy.")

    if not paras:
        add("WARN", "no-body", "No body paragraphs found. Check the parser matched this format.")
        return out

    # cadence
    sl, para_sents, walls = [], [], []
    for p in paras:
        ss = sentences(p)
        para_sents.append(len(ss))
        if len(p.split()) > fp["para_max_words"]:
            walls.append(p)
        sl += [len(s.split()) for s in ss if s.split()]
    if not sl:
        return out

    mean = statistics.mean(sl)
    cv = statistics.pstdev(sl) / mean if mean else 0
    p90 = sorted(sl)[int(0.9 * (len(sl) - 1))]
    one_rate = sum(1 for n in para_sents if n == 1) / len(para_sents)

    if walls:
        add("WARN", "wall-paragraph",
            f"{len(walls)} paragraph(s) over {fp['para_max_words']} words "
            f"({100 * len(walls) / len(paras):.0f}% of the draft). Daniel's essays have one "
            f"in 297. Split them.", None, walls[0][:90])

    if abs(mean - fp["cadence_mean"]) / fp["cadence_mean"] > 0.40:
        add("WARN", "cadence_mean_drift",
            f"Mean sentence {mean:.1f}w vs fingerprint {fp['cadence_mean']}w (>40% drift).")
    if p90 > fp["cadence_p90"] * 1.5:
        add("WARN", "cadence_p90_drift",
            f"p90 sentence {p90}w vs fingerprint {fp['cadence_p90']}w (>50% drift).")
    if cv < fp["cv_floor"]:
        add("WARN", "low_burstiness",
            f"length_cv {cv:.3f} below floor {fp['cv_floor']}. Sentences are too uniform; "
            f"mix short ones in.")
    if one_rate < fp["one_sent_para"] * 0.5:
        add("WARN", "paragraph_rate_drift",
            f"One-sentence paragraphs {100 * one_rate:.1f}% vs target "
            f"{100 * fp['one_sent_para']:.0f}%. Below half the band. This is the single "
            f"biggest single thing that makes copy read as corporate.")

    n_c = len(CONTRACTIONS.findall(body))
    n_t = len(CONTRACTIBLE.findall(body)) + n_c
    if n_t >= 20:
        rate = n_c / n_t
        if rate < fp["contraction_rate"] * 0.5:
            add("WARN", "contraction_rate_drop",
                f"Contractions {100 * rate:.0f}% of contractible pairs vs target "
                f"{100 * fp['contraction_rate']:.0f}%. Reads more formal than Daniel.")

    toks = re.findall(r"[a-z']+", body.lower())
    if len(toks) >= 200:
        w = 50
        m_score = statistics.mean(
            len(set(toks[i:i + w])) / w for i in range(len(toks) - w + 1))
        if m_score < fp["mattr_floor"]:
            add("WARN", "lexical_diversity_drop",
                f"MATTR {m_score:.3f} below floor {fp['mattr_floor']}. Repetitive vocabulary.")

    if fp["signature"] and len(toks) > 150:
        hits = sum(1 for s in fp["signature"] if s.lower() in body.lower())
        if hits < 2:
            add("WARN", "signature_absence",
                f"Only {hits} signature phrase(s) present. Expected at least 2. "
                f"Does not sound like us.")

    return out


# --------------------------------------------------------------------------- cli

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--profile", help="profile id in the fingerprint. Default: its `active` key.")
    ap.add_argument("--fingerprint", default=None, help="explicit path to voice-fingerprint.yaml")
    site_config.add_root_arg(ap)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--blocks-only", action="store_true",
                    help="suppress warnings; exit non-zero only on blocks")
    a = ap.parse_args()

    global REPO
    REPO = site_config.find_project_root(a.paths[0], a.project_root)
    project = site_config.load_project(REPO)
    fp = load_fingerprint(a.profile, site_config.fingerprint_path(project, REPO, a.fingerprint))
    partners, partners_file = load_partners(REPO)
    brand = (project.get("site") or {}).get("name") if isinstance(project.get("site"), dict) else None
    partner_re = partner_pattern(partners, brand)
    results, worst = {}, 0

    for path in a.paths:
        if not os.path.exists(path):
            print(f"missing: {path}", file=sys.stderr)
            worst = max(worst, 2)
            continue
        f = check(path, fp, partner_re)
        if a.blocks_only:
            f = [x for x in f if x["severity"] == "BLOCK"]
        results[path] = f
        if any(x["severity"] == "BLOCK" for x in f):
            worst = 2
        elif f and worst < 1:
            worst = 1

    if a.json:
        print(json.dumps({"site": REPO, "fingerprint": fp.get("profile", "defaults"),
                          "source": fp["_source"], "partners": partners,
                          "results": results}, indent=2))
        return worst

    print(f"voice_check · site {REPO}")
    print(f"  profile: {fp.get('profile', 'defaults')} · bands from {fp['_source']}")
    if partner_re is None:
        print("  partners: NONE LOADED. No PARTNERS.md found, so the partner-as-target "
              "check did not run.")
    else:
        print(f"  partners: {len(partners)} from {partners_file}")
    print()
    for path, f in results.items():
        blocks = [x for x in f if x["severity"] == "BLOCK"]
        warns = [x for x in f if x["severity"] == "WARN"]
        status = "BLOCKED" if blocks else ("warn" if warns else "clean")
        print(f"{os.path.relpath(path, REPO) if path.startswith(REPO) else path}"
              f"   [{status}]  {len(blocks)} block(s), {len(warns)} warning(s)")
        for x in blocks + warns:
            loc = f":{x['line']}" if x["line"] else ""
            print(f"   {x['severity']:<5} {x['rule']}{loc}")
            print(f"         {x['message']}")
            if x["match"]:
                print(f"         > ...{x['match'].strip()}...")
        print()

    print({0: "PASS", 1: "PASS with cadence drift", 2: "FAIL, blocks present"}[worst])
    return worst


if __name__ == "__main__":
    sys.exit(main())
