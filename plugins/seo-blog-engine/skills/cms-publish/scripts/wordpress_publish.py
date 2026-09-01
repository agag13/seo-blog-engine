#!/usr/bin/env python3
"""
WordPress REST publisher for the SEO blog engine.

Creates or updates a post as a DRAFT (never live). Stdlib-only (urllib) — no `requests`.
Auth: WordPress Application Password via HTTP Basic (WP_USER / WP_APP_PASSWORD in env).

Usage:
  python3 wordpress_publish.py --project ./project.yaml --content post.md --meta post.meta.json
                               [--featured hero.png] [--update <post_id>] [--dry-run]

meta.json fields (all optional except title + slug):
  title, slug, excerpt, seo_title, seo_description, category, author, tags[], published_date
"""
import argparse, base64, json, os, re, sys, urllib.request, urllib.error, urllib.parse

# ---------- tiny YAML reader (avoids a PyYAML dependency for simple configs) ----------
def load_config(path):
    if path.endswith(".json"):
        return json.load(open(path))
    try:
        import yaml  # use PyYAML if present (handles the full template)
        return yaml.safe_load(open(path))
    except ImportError:
        sys.exit("project.yaml needs PyYAML (pip install pyyaml) or pass a .json config.")

# ---------- minimal, controlled markdown -> WordPress block HTML ----------
def md_to_html(md):
    md = md.replace("\r\n", "\n")
    # strip a leading H1 (WordPress uses the post title for H1) and any '## JSON-LD'/checklist tail
    md = re.sub(r"^#\s+.*\n", "", md, count=1)
    for marker in ["\n## JSON-LD", "\n## Content quality checklist"]:
        i = md.find(marker)
        if i != -1:
            md = md[:i]
    md = re.sub(r"\s*\[LEGAL REVIEW\]|\s*\[VERIFY\]", "", md)  # strip internal markers
    def inline(s):
        s = re.sub(r"&(?!#?\w+;)", "&amp;", s).replace("<", "&lt;").replace(">", "&gt;")
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                   lambda m: f'<a href="{m.group(2)}"'
                             + ('' if ('/' == m.group(2)[:1] or '#' == m.group(2)[:1]) else ' target="_blank" rel="noopener"')
                             + f'>{m.group(1)}</a>', s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return s
    blocks, cur = [], []
    def flush():
        if cur: blocks.append(list(cur)); cur.clear()
    for ln in md.split("\n"):
        if ln.strip() == "": flush()
        else: cur.append(ln.rstrip())
    flush()
    typed = []
    for b in blocks:
        h = b[0]
        if h.startswith("### "): typed.append(("h3", [h[4:].strip()]))
        elif h.startswith("## "): typed.append(("h2", [h[3:].strip()]))
        elif re.match(r"^\d+\.\s", h): typed.append(("ol", [re.sub(r"^\d+\.\s+", "", x) for x in b]))
        elif h.startswith("- "): typed.append(("ul", [x[2:] for x in b]))
        else: typed.append(("p", [" ".join(b)]))
    merged = []
    for t, items in typed:
        if merged and t in ("ol", "ul") and merged[-1][0] == t: merged[-1][1].extend(items)
        else: merged.append([t, list(items)])
    out = []
    for t, items in merged:
        if t in ("h2", "h3"): out.append(f'<{t} class="wp-block-heading">{inline(items[0])}</{t}>')
        elif t == "ol": out.append('<ol class="wp-block-list">\n' + "\n\n".join(f"<li>{inline(i)}</li>" for i in items) + "\n</ol>")
        elif t == "ul": out.append('<ul class="wp-block-list">\n' + "\n\n".join(f"<li>{inline(i)}</li>" for i in items) + "\n</ul>")
        else: out.append(f'<p class="wp-block-paragraph">{inline(items[0])}</p>')
    return "\n\n\n\n".join(out)

# ---------- WP REST helpers ----------
def wp_request(api_base, path, method, user, app_pw, body=None, is_multipart=False, filename=None, ctype=None):
    url = api_base.rstrip("/") + path
    auth = base64.b64encode(f"{user}:{app_pw}".encode()).decode()
    headers = {"Authorization": "Basic " + auth}
    if is_multipart:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        headers["Content-Type"] = ctype
        data = body
    else:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:400]}

def resolve_category(api_base, name, cats_cfg, auth):
    if isinstance(name, int) or (isinstance(name, str) and name.isdigit()):
        return int(name)
    q = urllib.parse.urlencode({"search": name})
    st, data = wp_request(api_base, f"/categories?{q}", "GET", *auth)
    if st < 400 and data:
        for c in data:
            if c.get("name", "").lower() == str(name).lower():
                return c["id"]
        if data: return data[0]["id"]
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--featured")
    ap.add_argument("--update", help="existing post id to update instead of create")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = load_config(a.project)
    cms = cfg.get("cms", {})
    api_base = cms.get("api_base") or (cfg["site"]["url"].rstrip("/") + "/wp-json/wp/v2")
    fields = cms.get("fields", {})
    user, app_pw = os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD")
    if not a.dry_run and (not user or not app_pw):
        sys.exit("Set WP_USER and WP_APP_PASSWORD in the environment (.env).")
    auth = (user, app_pw)

    meta = json.load(open(a.meta))
    raw = open(a.content).read()
    html = raw if a.content.endswith((".html", ".htm")) else md_to_html(raw)

    payload = {
        "title": meta["title"],
        "slug": meta["slug"],
        "content": html,
        "excerpt": meta.get("excerpt", ""),
        "status": cms.get("default_status", "draft"),   # ALWAYS draft
    }
    if meta.get("published_date"): payload["date"] = meta["published_date"]
    if meta.get("author"):
        amap = cfg.get("authors", {})
        payload["author"] = amap.get(meta["author"], meta["author"])
    # SEO meta (best-effort; may require plugin REST support)
    seo_map = {}
    if meta.get("seo_title") and fields.get("seo_title", "").startswith("meta."):
        seo_map[fields["seo_title"].split(".", 1)[1]] = meta["seo_title"]
    if meta.get("seo_description") and fields.get("seo_description", "").startswith("meta."):
        seo_map[fields["seo_description"].split(".", 1)[1]] = meta["seo_description"]
    if seo_map: payload["meta"] = seo_map

    if a.dry_run:
        cat = meta.get("category")
        print("DRY-RUN — would POST to", api_base + "/posts")
        print(json.dumps({k: (v if k != "content" else f"<{len(v)} bytes html>") for k, v in payload.items()}, indent=2))
        print("category to resolve:", cat, "| featured:", a.featured, "| update id:", a.update)
        return

    if meta.get("category") is not None:
        cid = resolve_category(api_base, meta["category"], cfg.get("categories", []), auth)
        if cid: payload["categories"] = [cid]
        else: print("WARN: category not resolved:", meta["category"])

    if a.featured and os.path.exists(a.featured):
        ext = os.path.splitext(a.featured)[1].lstrip(".").lower()
        ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "application/octet-stream")
        st, media = wp_request(api_base, "/media", "POST", *auth, body=open(a.featured, "rb").read(),
                               is_multipart=True, filename=os.path.basename(a.featured), ctype=ctype)
        if st < 400 and media.get("id"):
            payload["featured_media"] = media["id"]
            if media.get("id") and not meta.get("_alt_set"):
                wp_request(api_base, f"/media/{media['id']}", "POST", *auth,
                           body={"alt_text": meta.get("featured_alt", meta["title"])})
        else:
            print("WARN: featured image upload failed:", st, media.get("error", ""))

    path = f"/posts/{a.update}" if a.update else "/posts"
    st, resp = wp_request(api_base, path, "POST", *auth, body=payload)
    if st >= 400:
        print("ERROR", st, resp.get("error", resp)); sys.exit(1)
    edit = api_base.split("/wp-json")[0] + f"/wp-admin/post.php?post={resp.get('id')}&action=edit"
    print(f"OK  post id={resp.get('id')}  status={resp.get('status')}  (DRAFT)")
    print("Review/edit:", edit)
    print("Preview:", resp.get("link", ""))

if __name__ == "__main__":
    main()
