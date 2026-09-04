#!/usr/bin/env python3
"""Multi-credential provider resolution, rotation, and an answer log.

One key per provider is how a research layer dies quietly. The Apify route to
Ahrefs on the reference account returns HTTP 403 `Monthly usage hard limit
exceeded` because that account is on the free plan, and it returned the same 403
on day one of the following month. A hard limit on a free plan is not a quota
that resets, and there was no second credential to fall through to.

So: several credentials per provider, rotate on failure, and record which key
served the call. The record matters as much as the rotation, because a figure
whose provenance is unknown cannot be corroborated later.

Credentials come from the environment, numbered `_1`, `_2`, `_3`. Never from a
committed file. See templates/env.example.

Usage
-----
    python3 providers.py                  # report what is configured and what is not
    python3 providers.py --json

    from providers import Providers
    p = Providers()
    for cred in p.credentials("serpapi"):
        try:
            r = call(cred.value); p.record("serpapi", cred, ok=True); break
        except HTTPError as e:
            p.record("serpapi", cred, ok=False, note=str(e))
    else:
        p.record_exhausted("serpapi")   # every key failed. NOT the same as no data.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

# name -> (env prefix, extra paired env prefixes)
SPEC = {
    "serpapi":    ("SERPAPI_KEY", []),
    "apify":      ("APIFY_TOKEN", ["APIFY_PLAN"]),
    "dataforseo": ("DATAFORSEO_LOGIN", ["DATAFORSEO_PASSWORD"]),
    "ahrefs":     ("AHREFS_API_TOKEN", []),
    "tavily":     ("TAVILY_API_KEY", []),
    "moz":        ("MOZ_ACCESS_ID", ["MOZ_SECRET_KEY"]),
    "redditapis": ("REDDITAPIS_KEY", []),
    "getxapi":    ("GETXAPI_KEY", []),
}
MAX_SLOTS = 9


@dataclass
class Cred:
    provider: str
    slot: int
    value: str
    extras: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Safe to print and to write into a brief. Never the secret itself."""
        tail = self.value[-4:] if len(self.value) >= 4 else "????"
        return f"{self.provider}#{self.slot}(...{tail})"


class Providers:
    def __init__(self, env: dict | None = None):
        self.env = env if env is not None else os.environ
        self.log: list[dict] = []

    def credentials(self, provider: str) -> list[Cred]:
        if provider not in SPEC:
            raise KeyError(f"unknown provider '{provider}'. Known: {', '.join(SPEC)}")
        prefix, extras = SPEC[provider]
        out = []
        for i in range(1, MAX_SLOTS + 1):
            val = (self.env.get(f"{prefix}_{i}") or "").strip()
            if not val:
                continue
            ex = {}
            for e in extras:
                v = (self.env.get(f"{e}_{i}") or "").strip()
                if v:
                    ex[e.lower()] = v
            out.append(Cred(provider, i, val, ex))
        return out

    # -- the answer log -----------------------------------------------------
    def record(self, provider: str, cred: Cred, ok: bool, note: str = "") -> None:
        self.log.append({"provider": provider, "credential": cred.label,
                         "ok": ok, "note": note})

    def record_exhausted(self, provider: str, note: str = "") -> None:
        """Every credential failed. This is a failure to record, never a zero."""
        self.log.append({"provider": provider, "credential": None, "ok": False,
                         "exhausted": True,
                         "note": note or "all configured credentials failed"})

    def record_unconfigured(self, provider: str, why: str) -> None:
        self.log.append({"provider": provider, "credential": None, "ok": False,
                         "unconfigured": True, "note": why})

    def answered_by(self, provider: str) -> str | None:
        for e in reversed(self.log):
            if e["provider"] == provider and e["ok"]:
                return e["credential"]
        return None

    def brief_line(self, provider: str) -> str:
        """One line for the brief's provenance block. Honest when it failed."""
        who = self.answered_by(provider)
        if who:
            return f"{provider}: answered by {who}"
        fails = [e for e in self.log if e["provider"] == provider]
        if not fails:
            return f"{provider}: NOT CALLED"
        if any(e.get("unconfigured") for e in fails):
            return f"{provider}: NOT CONFIGURED. {fails[-1]['note']}"
        n = len(self.credentials(provider)) or len([e for e in fails if e["credential"]])
        return (f"{provider}: FAILED on all {n} configured credential(s). "
                f"{fails[-1]['note']}")


def status(env: dict | None = None) -> dict:
    p = Providers(env)
    out = {}
    for name in SPEC:
        creds = p.credentials(name)
        out[name] = {"configured": len(creds), "slots": [c.label for c in creds],
                     "extras": [c.extras for c in creds if c.extras]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    st = status()
    if a.json:
        print(json.dumps(st, indent=2))
        return 0
    print("providers · credentials found in the environment\n")
    for name, info in st.items():
        n = info["configured"]
        mark = "  ok " if n else "  -- "
        print(f"{mark}{name:<12} {n} credential(s)"
              + (f"  {', '.join(info['slots'])}" if n else "  NOT CONFIGURED"))
        for ex in info["extras"]:
            if ex.get("apify_plan") == "free":
                print("               note: this Apify account is on the FREE plan. Its hard "
                      "limit does not reset monthly.")
    print("\nA provider with no credentials is reported as unconfigured, never treated as "
          "a provider that returned no data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
