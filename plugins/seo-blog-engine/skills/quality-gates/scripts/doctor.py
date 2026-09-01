#!/usr/bin/env python3
"""Setup doctor: tell a teammate exactly what is still missing before a first run.

Onboarding a site is a list of things somebody has to supply, and the expensive
failure is a gate that looks installed but has nothing to check. A missing
PARTNERS.md does not error; it just means the partner rule silently never fires.
A fingerprint left on template defaults does not error either; it means the voice
gate is comparing against numbers nobody measured.

So this reports READY / INCOMPLETE / MISSING per item, and says what to do about
each one. Run it from inside a website's project folder.

Usage
-----
    python3 doctor.py                 # checks the current folder
    python3 doctor.py --project-root ../mysite
    python3 doctor.py --json

Exit codes
----------
    0   ready to run the pipeline
    1   runnable, but at least one gate cannot actually check anything
    2   not ready. Something required is missing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import site_config  # noqa: E402
import providers as prov  # noqa: E402

# A file still carrying these is a template somebody copied and did not fill.
PLACEHOLDER = re.compile(
    r"<[a-z][^>\n]{2,60}>|YYYY-MM-DD|Example Brand|example\.com|Example Partner|"
    r"Another Partner|Example fact|TODO", re.I)


def item(name, state, note, fix=""):
    return {"item": name, "state": state, "note": note, "fix": fix}


def check_runtime() -> list:
    out = []
    v = sys.version_info
    if v >= (3, 9):
        out.append(item("Python", "READY", f"{v.major}.{v.minor}.{v.micro}"))
    else:
        out.append(item("Python", "MISSING", f"{v.major}.{v.minor} is too old",
                        "Install Python 3.9 or newer. 3.11 recommended."))
    try:
        import yaml  # noqa: F401,PLC0415
        out.append(item("PyYAML", "READY", "installed"))
    except ImportError:
        out.append(item(
            "PyYAML", "INCOMPLETE",
            "not installed, so the voice gate cannot read the fingerprint and falls "
            "back to built-in bands",
            "pip3 install pyyaml"))
    return out


def check_context(root: str) -> list:
    out = []
    project = site_config.load_project(root)

    if not project.get("_source"):
        out.append(item("project.yaml", "MISSING", f"none found under {root}",
                        "Run `project-init` in this folder."))
        return out
    out.append(item("project.yaml", "READY", project["_source"]))

    url = site_config.site_url(project)
    if url and "example.com" not in url:
        out.append(item("site.url", "READY", url))
    else:
        out.append(item("site.url", "MISSING", f"site.url is {url or 'unset'}",
                        "Set the real site root. Without it the links gate cannot "
                        "resolve a single internal link."))

    cms = (project.get("cms") or {})
    ctype = cms.get("type") if isinstance(cms, dict) else None
    status = cms.get("default_status") if isinstance(cms, dict) else None
    if ctype in ("wordpress", "markdown"):
        note = f"{ctype}, default_status={status or 'unset'}"
        if status != "draft":
            out.append(item("cms", "INCOMPLETE", note,
                            "Set cms.default_status to draft. The engine never publishes live."))
        else:
            out.append(item("cms", "READY", note))
    elif ctype:
        out.append(item("cms", "MISSING", f"cms.type '{ctype}' has no adapter",
                        "Supported today: wordpress, markdown."))
    else:
        out.append(item("cms", "MISSING", "cms.type unset", "Set wordpress or markdown."))

    for fname, why, fix in (
        ("BRAND.md", "audience, positioning and honesty rules", "Run `project-init`."),
        ("VOICE.md", "readable tone guidance for the writer", "Run `project-init`."),
        ("PARTNERS.md", "who this client never writes competitively about",
         "Ask the client for the list, with domains. Until it exists the partner "
         "rule never fires."),
        ("FACTS.md", "every product fact with a status and a source",
         "Audit the client's own surfaces. Expect contradictions; those are CONFLICTED."),
    ):
        path = site_config.context_file(root, fname)
        if not path:
            out.append(item(fname, "MISSING", "not found", fix))
            continue
        body = open(path, encoding="utf-8", errors="replace").read()
        hits = PLACEHOLDER.findall(body)
        if hits:
            out.append(item(fname, "INCOMPLETE",
                            f"still carries {len(hits)} template placeholder(s), "
                            f"e.g. {hits[0][:40]!r}",
                            f"Fill it in. It holds {why}."))
        else:
            out.append(item(fname, "READY", path))

    out += check_fingerprint(project, root)
    return out


def check_fingerprint(project: dict, root: str) -> list:
    path = site_config.fingerprint_path(project, root)
    if not os.path.exists(path):
        return [item("voice-fingerprint.yaml", "MISSING", f"none at {path}",
                     "Copy templates/voice-fingerprint.yaml.template and MEASURE the bands "
                     "from the client's own published writing. Do not assert them.")]
    try:
        import yaml  # noqa: PLC0415
        doc = yaml.safe_load(open(path)) or {}
    except ImportError:
        return [item("voice-fingerprint.yaml", "INCOMPLETE", "present, unreadable without PyYAML",
                     "pip3 install pyyaml")]
    except Exception as exc:  # noqa: BLE001
        return [item("voice-fingerprint.yaml", "MISSING", f"will not parse: {exc}",
                     "Fix the YAML. A fingerprint that does not parse is no fingerprint.")]

    out = []
    profiles = doc.get("profiles") or {}
    active = doc.get("active")
    if active in profiles:
        out.append(item("voice-fingerprint.yaml", "READY",
                        f"{len(profiles)} profile(s), active={active}"))
    else:
        out.append(item("voice-fingerprint.yaml", "MISSING",
                        f"active profile '{active}' is not in profiles",
                        "Point `active` at a profile that exists."))

    p = profiles.get(active) or {}
    if not p.get("sample_count"):
        out.append(item("fingerprint corpus", "INCOMPLETE",
                        "sample_count is 0, so these bands were never measured",
                        "Measure them from at least 10 published pieces. Guessed bands "
                        "block good copy and pass bad copy, and then somebody switches "
                        "the gate off."))
    else:
        out.append(item("fingerprint corpus", "READY",
                        f"{p.get('sample_count')} sample(s), "
                        f"{p.get('sample_word_count') or '?'} words"))

    due = str(doc.get("refresh_due") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", due):
        import datetime as _dt
        if _dt.date.fromisoformat(due) < _dt.date.today():
            out.append(item("fingerprint freshness", "INCOMPLETE",
                            f"refresh_due was {due}, which has passed",
                            "Re-measure. A stale fingerprint is a stale gate."))
        else:
            out.append(item("fingerprint freshness", "READY", f"good until {due}"))
    else:
        out.append(item("fingerprint freshness", "INCOMPLETE",
                        "refresh_due is unset or not a date", "Set it 90 days out."))

    if not (doc.get("banned_structures") or []):
        out.append(item("banned_structures", "INCOMPLETE",
                        "empty, so no brand-specific rule is enforced",
                        "Add the client's hard rules as id/pattern/why entries. The generic "
                        "AI tells ship with the engine; brand rules cannot."))
    else:
        out.append(item("banned_structures", "READY",
                        f"{len(doc['banned_structures'])} rule(s)"))
    return out


def check_providers() -> list:
    st = prov.status()
    out = []
    for name in ("dataforseo", "tavily"):
        n = st[name]["configured"]
        if n:
            out.append(item(f"provider {name}", "READY", f"{n} credential(s) in .env"))
        else:
            out.append(item(f"provider {name}", "INCOMPLETE",
                            "no credentials in .env",
                            "Fine if you reach it through its MCP connector instead. "
                            "Needed only for direct API calls."))
    for name in ("serpapi", "apify", "ahrefs", "moz"):
        n = st[name]["configured"]
        out.append(item(f"provider {name}", "READY" if n else "INCOMPLETE",
                        f"{n} credential(s)" if n else "none",
                        "" if n else "Optional. A second credential here is what keeps a "
                                     "provider alive when one key hits its quota."))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    site_config.add_root_arg(ap)
    a = ap.parse_args()
    root = site_config.find_project_root(os.getcwd(), a.project_root)

    groups = [("Runtime", check_runtime()),
              ("Site context", check_context(root)),
              ("Providers", check_providers())]

    required_missing = any(i["state"] == "MISSING"
                           for g, items in groups for i in items
                           if g in ("Runtime", "Site context"))
    any_incomplete = any(i["state"] != "READY" for _, items in groups for i in items)
    code = 2 if required_missing else (1 if any_incomplete else 0)

    if a.json:
        print(json.dumps({"root": root, "verdict": code,
                          "groups": {g: items for g, items in groups}}, indent=2))
        return code

    print(f"doctor · site {root}\n")
    for gname, items in groups:
        print(f"{gname}")
        for i in items:
            mark = {"READY": " ok ", "INCOMPLETE": "warn", "MISSING": "STOP"}[i["state"]]
            print(f"  [{mark}] {i['item']:<26} {i['note']}")
            if i["fix"] and i["state"] != "READY":
                print(f"           -> {i['fix']}")
        print()
    print({0: "READY. Run `intake` to start an article.",
           1: "RUNNABLE, but at least one gate cannot check anything. Read the warns above.",
           2: "NOT READY. Fix the STOP items first."}[code])
    return code


if __name__ == "__main__":
    sys.exit(main())
