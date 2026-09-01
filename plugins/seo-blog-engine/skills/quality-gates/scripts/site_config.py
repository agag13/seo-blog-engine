#!/usr/bin/env python3
"""Per-site config resolution for the gate scripts.

The engine is shared; the context is per site. Every gate therefore has to find
the site it is checking rather than assume a repo layout. Resolution order, and
the first one that answers wins:

    1.  an explicit --project-root on the command line
    2.  $SEO_BLOG_PROJECT
    3.  walk up from the file being checked, looking for project.yaml
    4.  walk up from the file being checked, looking for .git
    5.  the current working directory

The scripts this engine inherited computed the repo root from __file__ with four
os.pardir
hops. That is the bug that made the batch-3 regression test invalid: run the
script from anywhere else and the fingerprint path silently broke, so the gate
compared against built-in defaults while appearing to pass. Resolution now
starts from the *target file*, and every gate prints which site config answered.

Stdlib only, and PyYAML is optional. A missing dependency must never silently
disable a gate, so the loader falls back to a small regex reader that handles
the flat scalar keys the gates actually need.
"""
from __future__ import annotations

import os
import re

MARKERS = ("project.yaml", "project.yml")


def find_project_root(start: str | None = None, explicit: str | None = None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    env = os.environ.get("SEO_BLOG_PROJECT")
    if env:
        return os.path.abspath(env)

    here = os.path.abspath(start or os.getcwd())
    if os.path.isfile(here):
        here = os.path.dirname(here)

    for marker in (MARKERS, (".git",)):
        probe = here
        while True:
            for m in marker:
                if os.path.exists(os.path.join(probe, m)):
                    return probe
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
    return os.getcwd()


def _regex_scalars(text: str) -> dict:
    """Last-resort reader: top-level-section scalars, one nesting level deep.

    Produces keys like "site.url". Enough for the gates; not a YAML parser, and
    it says so rather than pretending otherwise.
    """
    out, section = {}, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            section = m.group(1)
            val = m.group(2).strip()
            if val:
                out[section] = val.strip('"\'')
            continue
        m = re.match(r"^\s{1,4}([A-Za-z_][\w-]*):\s*(.+)$", line)
        if m and section:
            out[f"{section}.{m.group(1)}"] = m.group(2).strip().strip('"\'')
    return out


def load_project(root: str) -> dict:
    """Return the site's project.yaml as a dict, plus `_source` and `_parser`."""
    path = None
    for m in MARKERS:
        cand = os.path.join(root, m)
        if os.path.exists(cand):
            path = cand
            break
    if not path:
        return {"_source": None, "_parser": "none", "_root": root}

    text = open(path, encoding="utf-8", errors="replace").read()
    try:
        import yaml  # noqa: PLC0415

        doc = yaml.safe_load(text) or {}
        doc["_parser"] = "pyyaml"
    except ImportError:
        doc = _nest(_regex_scalars(text))
        doc["_parser"] = "regex-fallback (PyYAML not installed)"
    except Exception as exc:  # noqa: BLE001
        doc = _nest(_regex_scalars(text))
        doc["_parser"] = f"regex-fallback (YAML parse failed: {exc})"
    doc["_source"] = path
    doc["_root"] = root
    return doc


def _nest(flat: dict) -> dict:
    out: dict = {}
    for k, v in flat.items():
        if "." in k:
            a, b = k.split(".", 1)
            out.setdefault(a, {})
            if isinstance(out[a], dict):
                out[a][b] = v
        else:
            out.setdefault(k, v)
    return out


def site_url(project: dict, default: str = "") -> str:
    site = project.get("site") or {}
    url = site.get("url") if isinstance(site, dict) else None
    return (url or default).rstrip("/")


def site_host(project: dict, default: str = "") -> str:
    """Host with any leading www. removed, for internal/external classification."""
    url = site_url(project, default)
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return re.sub(r"^www\.", "", host)


def fingerprint_path(project: dict, root: str, explicit: str | None = None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    env = os.environ.get("SEO_BLOG_FINGERPRINT")
    if env:
        return os.path.abspath(env)
    voice = project.get("voice") or {}
    rel = voice.get("fingerprint") if isinstance(voice, dict) else None
    return os.path.join(root, rel or os.path.join("config", "voice-fingerprint.yaml"))


def context_file(root: str, name: str) -> str | None:
    """Locate a per-site context file (PARTNERS.md, FACTS.md) if the site has one."""
    for rel in (name, os.path.join("config", name), os.path.join("context", name)):
        cand = os.path.join(root, rel)
        if os.path.exists(cand):
            return cand
    return None


def add_root_arg(ap) -> None:
    ap.add_argument("--project-root", default=None,
                    help="site folder holding project.yaml. Default: walk up from the target file.")


# --------------------------------------------------------------------------- drafts

def frontmatter(raw: str) -> tuple:
    """Split a draft into (frontmatter dict, body). Lives here so the builder and
    the publisher read a draft the same way; two parsers would eventually differ,
    and a difference between them is a difference between surfaces.

    Scalars only, which is all the house frontmatter uses. A list value is kept
    as its raw string rather than half-parsed into something misleading.
    """
    m = re.match(r"(?s)\A---\n(.*?)\n---\n?(.*)\Z", raw)
    if not m:
        return {}, raw
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"\'')
    return fm, m.group(2)
