"""Minimale Supabase-client (PostgREST) op basis van de standaardbibliotheek."""
import json
import os
import urllib.parse
import urllib.request

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def enabled():
    return bool(URL and KEY)


def _req(method, path, body=None, prefer=None, params=None):
    q = ("?" + urllib.parse.urlencode(params, safe=",.()*:")) if params else ""
    headers = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{URL}/rest/v1/{path}{q}", data=data,
                                 headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else None


def select(table, **params):
    params.setdefault("select", "*")
    out, offset = [], 0
    while True:
        page = _req("GET", table, params={**params, "limit": 1000, "offset": offset})
        out += page
        if len(page) < 1000:
            return out
        offset += 1000


def insert(table, rows, on_conflict=None, ignore_duplicates=False, merge=False):
    if not rows:
        return []
    params = {"on_conflict": on_conflict} if on_conflict else None
    prefer = ["return=representation"]
    if ignore_duplicates:
        prefer.append("resolution=ignore-duplicates")
    elif merge:
        prefer.append("resolution=merge-duplicates")
    return _req("POST", table, rows, prefer=",".join(prefer), params=params)


def update(table, match, values):
    params = {k: f"eq.{v}" for k, v in match.items()}
    return _req("PATCH", table, values, prefer="return=representation", params=params)
