"""PR Goeroes monitor (test).

Zoekt dagelijks naar vermeldingen van klanten via:
  1. de ingebouwde zoekfunctie van WordPress-sites (/wp-json/wp/v2/search)
  2. Google News RSS (alleen voor de testfase; niet commercieel bruikbaar)

Resultaten worden ontdubbeld op URL en toegevoegd aan data/mentions.csv.
Per run komt er een regel in data/runs.log met wat er per bron gebeurde.
Alleen standaardbibliotheek, zodat het zonder installatie draait.
"""

import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CSV_PATH = DATA / "mentions.csv"
LOG_PATH = DATA / "runs.log"
UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
FIELDS = [
    "found_at", "client", "outlet", "title", "url", "published",
    "method", "kind", "matched_on",
]

_robots_cache = {}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def robots_allows(url):
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.parse(fetch(base + "/robots.txt").splitlines())
        except Exception:
            rp = None  # geen robots.txt bereikbaar = geen beperking bekend
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    return True if rp is None else rp.can_fetch(UA, url)


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def match_client(client, text):
    """True als een zoekterm als heel woord voorkomt en geen uitsluiting."""
    for ex in client.get("exclude", []):
        if ex.lower() in text.lower():
            return None
    for term in client["match"] + client.get("spokespersons", []):
        if re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", text, re.I):
            return term
    return None


def search_wordpress(source, client, since, log):
    hits = []
    term = client["match"][0]
    url = (source["base"] + "/wp-json/wp/v2/search?"
           + urllib.parse.urlencode({"search": term, "per_page": 20}))
    if not robots_allows(url):
        log.append(f"{source['outlet']}: overgeslagen (robots.txt verbiedt bots)")
        return hits
    try:
        results = json.loads(fetch(url))
    except urllib.error.HTTPError as e:
        log.append(f"{source['outlet']}: geen WordPress-zoekfunctie (HTTP {e.code})")
        return hits
    except Exception as e:
        log.append(f"{source['outlet']}: fout ({type(e).__name__})")
        return hits
    if not isinstance(results, list):
        log.append(f"{source['outlet']}: onverwacht antwoord")
        return hits

    checked = 0
    for r in results:
        title = strip_tags(r.get("title", ""))
        self_links = r.get("_links", {}).get("self", [])
        detail = {}
        if self_links:
            try:
                detail = json.loads(fetch(self_links[0]["href"]))
                checked += 1
                time.sleep(0.5)
            except Exception:
                detail = {}
        body = strip_tags(detail.get("content", {}).get("rendered", ""))
        matched = match_client(client, title + " " + body)
        if not matched:
            continue
        published = detail.get("date_gmt") or detail.get("date") or ""
        if published:
            try:
                pub = datetime.fromisoformat(published).replace(tzinfo=timezone.utc)
                if pub < since:
                    continue
            except ValueError:
                pass
        hits.append({
            "client": client["name"], "outlet": source["outlet"],
            "title": title, "url": r.get("url", ""), "published": published[:10],
            "method": "wordpress", "kind": r.get("subtype", ""),
            "matched_on": matched,
        })
    log.append(f"{source['outlet']}: {len(results)} zoekresultaten, "
               f"{len(hits)} relevant ({client['name']})")
    return hits


def search_google_news(client, since, log):
    hits = []
    q = " OR ".join(f'"{t}"' for t in client["match"])
    url = ("https://news.google.com/rss/search?"
           + urllib.parse.urlencode({"q": q, "hl": "nl", "gl": "NL", "ceid": "NL:nl"}))
    try:
        root = ET.fromstring(fetch(url))
    except Exception as e:
        log.append(f"Google News: fout ({type(e).__name__})")
        return hits
    items = root.findall("./channel/item")
    for it in items:
        title = it.findtext("title", "")
        source = it.findtext("source", "")
        # Google zet " - Bron" achter de titel
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        matched = match_client(client, title + " " + it.findtext("description", ""))
        if not matched:
            continue
        pub_raw = it.findtext("pubDate", "")
        try:
            pub = parsedate_to_datetime(pub_raw)
            if pub < since:
                continue
            published = pub.date().isoformat()
        except Exception:
            published = ""
        hits.append({
            "client": client["name"], "outlet": source, "title": title,
            "url": it.findtext("link", ""), "published": published,
            "method": "google_news", "kind": "", "matched_on": matched,
        })
    log.append(f"Google News: {len(items)} items, {len(hits)} relevant ({client['name']})")
    return hits


def norm_key(row):
    """Ontdubbelen: zelfde outlet + zelfde titel telt als één publicatie."""
    t = re.sub(r"\W+", " ", row["title"].lower()).strip()
    outlet = row["outlet"].lower().replace("/", "").replace("www.", "").strip()
    outlet = re.sub(r"\.nl$", "", outlet)  # "Computable.nl" (Google) == "Computable" (site)
    return (row["client"].lower(), outlet, t)


def main():
    cfg = json.loads((ROOT / "config.json").read_text())
    DATA.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=cfg.get("lookback_days", 30))

    existing = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing.append(r)
    # bestaande dubbelen opruimen; directe site-link gaat voor Google-link
    existing.sort(key=lambda r: r["method"] != "wordpress")
    seen_urls, seen_keys, kept = set(), set(), []
    for r in existing:
        if r["url"] in seen_urls or norm_key(r) in seen_keys:
            continue
        kept.append(r)
        seen_urls.add(r["url"])
        seen_keys.add(norm_key(r))
    existing = kept

    log, new_rows = [], []
    for client in cfg["clients"]:
        found = []
        for src in cfg["wordpress_sources"]:
            found += search_wordpress(src, client, since, log)
            time.sleep(1)
        if cfg.get("google_news"):
            found += search_google_news(client, since, log)
        found.sort(key=lambda r: r["method"] != "wordpress")
        for row in found:
            key = norm_key(row)
            if row["url"] in seen_urls or key in seen_keys:
                continue
            row["found_at"] = now.isoformat(timespec="seconds")
            new_rows.append(row)
            seen_urls.add(row["url"])
            seen_keys.add(key)

    all_rows = sorted(existing + new_rows,
                      key=lambda r: (r["client"], r["published"]), reverse=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n== {now.isoformat(timespec='seconds')} — {len(new_rows)} nieuw ==\n")
        f.write("\n".join(log) + "\n")
        for r in new_rows:
            f.write(f"  + [{r['client']}] {r['outlet']}: {r['title']} ({r['method']})\n")

    print("\n".join(log))
    print(f"\n{len(new_rows)} nieuwe vermeldingen")
    for r in new_rows:
        print(f"  + [{r['client']}] {r['outlet']}: {r['title']} ({r['method']}, {r['kind']})")


if __name__ == "__main__":
    sys.exit(main())
