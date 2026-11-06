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
import ssl
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

import supa

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


_LAX_SSL = ssl.create_default_context()
_LAX_SSL.check_hostname = False
_LAX_SSL.verify_mode = ssl.CERT_NONE


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        # Sommige (lokale) sites hebben een onvolledige certificaatketen; browsers vangen dat op, Python niet.
        # Alleen openbare pagina's lezen, geen inloggegevens: dan opnieuw zonder certificaatcontrole.
        if not isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            raise
        with urllib.request.urlopen(req, timeout=timeout, context=_LAX_SSL) as r:
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


_NL = {"het", "een", "van", "voor", "met", "niet", "zijn", "naar", "bij", "ook", "wordt", "deze", "dat", "die",
       "en", "op", "aan", "uit", "nieuwe", "heeft", "werd", "kan", "maar", "nog", "over", "door", "worden", "hun"}
_EN = {"the", "of", "and", "to", "for", "with", "from", "at", "by", "this", "that", "are", "was", "new", "has",
       "your", "you", "will", "its", "their", "after", "before", "into", "how", "what", "who", "be", "days", "day"}


def looks_dutch(text):
    """Grove taalcheck: meer Nederlandse dan Engelse functiewoorden."""
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    return sum(w in _NL for w in words) > sum(w in _EN for w in words)


def _term_pattern(term):
    """Heel woord; spatie en streepje gelden als gelijk ("Straight Line" = "Straight-Line")."""
    parts = [re.escape(p) for p in re.split(r"[\s\-\u2010-\u2014]+", term.strip()) if p]
    return r"(?<![\w-])" + r"[\s\-\u2010-\u2014]+".join(parts) + r"(?![\w-])"


def match_client(client, text):
    """Zoekterm als heel woord, geen uitsluitwoord; bij only_dutch alleen Nederlandstalige tekst (woordvoerder telt altijd)."""
    for ex in client.get("exclude", []):
        if ex.lower() in text.lower():
            return None
    for term in client.get("spokespersons", []):
        if re.search(_term_pattern(term), text, re.I):
            return term
    for term in client["match"]:
        if re.search(_term_pattern(term), text, re.I):
            if client.get("only_dutch") and not looks_dutch(text):
                return None
            return term
    return None


def search_wordpress(source, client, since, log):
    hits = []
    term = client["match"][0]
    url = (source["base"] + "/wp-json/wp/v2/search?"
           + urllib.parse.urlencode({"search": term, "per_page": 10, "_embed": "self"}))
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
        # titel + samenvatting komen in één verzoek mee (_embed)
        detail = (r.get("_embedded", {}).get("self") or [{}])[0] or {}
        excerpt = strip_tags(detail.get("excerpt", {}).get("rendered", ""))
        matched = match_client(client, title + " " + excerpt)
        # niet in titel/samenvatting? open het volledige artikel, maar hooguit 5 per zoekopdracht
        self_links = r.get("_links", {}).get("self", [])
        if not matched and self_links and checked < 5:
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


GN_EDITIONS = [("nl", "NL", "NL:nl"), ("en-GB", "GB", "GB:en")]  # Nederlands + internationaal (Engelstalig)


def search_google_news(client, since, log):
    hits, seen = [], set()
    q = " OR ".join(f'"{t}"' for t in client["match"] + client.get("spokespersons", []))
    total = 0
    for hl, gl, ceid in GN_EDITIONS:
        url = ("https://news.google.com/rss/search?"
               + urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid}))
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:
            log.append(f"Google News ({gl}): fout ({type(e).__name__})")
            continue
        items = root.findall("./channel/item")
        total += len(items)
        for it in items:
            title = it.findtext("title", "")
            source = it.findtext("source", "")
            # Google zet " - Bron" achter de titel
            if source and title.endswith(" - " + source):
                title = title[: -len(" - " + source)]
            k = (source.lower(), re.sub(r"\W+", " ", title.lower()).strip())
            if k in seen:
                continue
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
            seen.add(k)
            hits.append({
                "client": client["name"], "outlet": source, "title": title,
                "url": it.findtext("link", ""), "published": published,
                "method": "google_news", "kind": "", "matched_on": matched,
            })
        time.sleep(1)
    log.append(f"Google News: {total} items, {len(hits)} relevant ({client['name']})")
    return hits


_feed_cache = {}


def search_rss(source, client, since, log):
    """Gewone RSS-feed van een site: titel + beschrijving doorzoeken."""
    hits = []
    url = source["url"]
    if url not in _feed_cache:
        try:
            _feed_cache[url] = ET.fromstring(fetch(url)).findall(".//item")
        except Exception as e:
            _feed_cache[url] = None
            log.append(f"{source['outlet']}: feed-fout ({type(e).__name__})")
    items = _feed_cache[url]
    if items is None:
        return hits
    for it in items:
        title = strip_tags(it.findtext("title", ""))
        title = re.sub(r"^Persbericht:\s*", "", title)
        matched = match_client(client, title + " " + strip_tags(it.findtext("description", "")))
        if not matched:
            continue
        published = ""
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate", ""))
            if pub < since:
                continue
            published = pub.date().isoformat()
        except Exception:
            pass
        link = (it.findtext("link", "") or "").strip().replace("/rss/nieuws/", "/nieuws/")
        hits.append({
            "client": client["name"], "outlet": source["outlet"], "title": title,
            "url": link, "published": published, "method": "rss",
            "kind": source.get("kind", ""), "matched_on": matched,
        })
    log.append(f"{source['outlet']}: feed met {len(items)} items, {len(hits)} relevant ({client['name']})")
    return hits


SITEMAP_MAX_CHILDREN = 12
SITEMAP_BUDGET_S = 120
_sitemap_cache = {}


def search_sitemap(source, client, since, log):
    """Sitemap doorzoeken op de klantnaam in de link; treffers openen voor titel en datum."""
    hits = []
    idx = source["index"]
    if idx not in _sitemap_cache:
        urls = []
        try:
            body = fetch(idx)
            if "<sitemapindex" in body:
                # Grote sites hebben honderden deel-sitemaps: alleen de recentste, met tijdslimiet
                entries = re.findall(r"<sitemap>(.*?)</sitemap>", body, re.S)
                kids = []
                for e in entries:
                    loc = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", e)
                    mod = re.search(r"<lastmod>\s*([^<\s]+)\s*</lastmod>", e)
                    if loc:
                        kids.append((mod.group(1) if mod else "", loc.group(1)))
                if any(m for m, _ in kids):
                    kids.sort(reverse=True)
                else:
                    kids.reverse()  # zonder datum staan de nieuwste meestal achteraan
                deadline = time.time() + SITEMAP_BUDGET_S
                for _, child in kids[:SITEMAP_MAX_CHILDREN]:
                    if time.time() > deadline:
                        log.append(f"{source['outlet']}: sitemap ingekort (tijdslimiet)")
                        break
                    try:
                        urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", fetch(child, timeout=30))
                    except Exception:
                        pass
                    time.sleep(1)
            else:
                urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
        except Exception as e:
            log.append(f"{source['outlet']}: sitemap-fout ({type(e).__name__})")
        _sitemap_cache[idx] = urls
    urls = _sitemap_cache[idx]
    for u in urls:
        slug = urllib.parse.urlsplit(u).path.replace("-", " ").replace("/", " ")
        if not match_client(client, slug) or not robots_allows(u):
            continue
        try:
            page = fetch(u)
            time.sleep(1)
        except Exception:
            continue
        m = (re.search(r'property="og:title" content="([^"]+)"', page)
             or re.search(r"<title>(.*?)</title>", page, re.S))
        title = html.unescape(m.group(1)).strip() if m else slug.strip()
        title = re.sub(r"\s*[|\-–]\s*Logimerce.*$", "", title)
        d = (re.search(r'"datePublished"\s*:\s*"([^"]+)"', page)
             or re.search(r'article:published_time" content="([^"]+)"', page))
        published = d.group(1)[:10] if d else ""
        if published:
            try:
                if datetime.fromisoformat(published).replace(tzinfo=timezone.utc) < since:
                    continue
            except ValueError:
                pass
        matched = match_client(client, title + " " + strip_tags(page)) or match_client(client, slug)
        hits.append({
            "client": client["name"], "outlet": source["outlet"], "title": title,
            "url": u, "published": published, "method": "sitemap",
            "kind": "", "matched_on": matched,
        })
    log.append(f"{source['outlet']}: sitemap met {len(urls)} links, {len(hits)} relevant ({client['name']})")
    return hits


def manual_links(client, log):
    """Links die Jennifer (of wij) handmatig doorgaven, uit data/manual.csv."""
    path = DATA / "manual.csv"
    if not path.exists():
        return []
    hits = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["client"].strip().lower() != client["name"].lower():
                continue
            hits.append({
                "client": client["name"], "outlet": r["outlet"], "title": r["title"],
                "url": r["url"], "published": r.get("published", ""),
                "method": "handmatig", "kind": "", "matched_on": "",
            })
    if hits:
        log.append(f"Handmatig: {len(hits)} links ({client['name']})")
    return hits


def write_summary(cfg, rows, now):
    """data/overzicht.md: per klant hoeveel publicaties, via welke route, laatste 5."""
    lines = [f"# Overzicht monitor", "", f"Bijgewerkt: {now:%Y-%m-%d %H:%M} UTC", "",
             "| Klant | Lijst | Publicaties | Automatisch | Handmatig | Via Google News |",
             "|---|---|---|---|---|---|"]
    for c in cfg["clients"]:
        rs = [r for r in rows if r["client"] == c["name"]]
        man = sum(r["method"] == "handmatig" for r in rs)
        gn = sum(r["method"] == "google_news" for r in rs)
        lines.append(f"| {c['name']} | {c.get('list', '')} | {len(rs)} | {len(rs) - man} | {man} | {gn} |")
    for c in cfg["clients"]:
        rs = [r for r in rows if r["client"] == c["name"]]
        if not rs:
            continue
        lines += ["", f"## {c['name']}", ""]
        for r in sorted(rs, key=lambda r: r["published"], reverse=True)[:10]:
            lines.append(f"- {r['published'] or '?'} — **{r['outlet']}**: [{r['title']}]({r['url']}) _({r['method']})_")
    (DATA / "overzicht.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def norm_key(row):
    """Ontdubbelen: zelfde outlet + zelfde titel telt als één publicatie."""
    t = re.sub(r"\W+", " ", row["title"].lower()).strip()
    outlet = row["outlet"].lower().replace("/", "").replace("www.", "").strip()
    outlet = re.sub(r"\.nl$", "", outlet)  # "Computable.nl" (Google) == "Computable" (site)
    outlet = re.sub(r"[\s\u00b7|\-\u2013]+$", "", outlet)  # "Accountancy Vanmorgen ·" (Google) == "Accountancy Vanmorgen"
    return (row["client"].lower(), outlet, t)


def load_from_db(cfg):
    """Klanten, bronnen en bestaande publicaties uit Supabase (de bron van waarheid)."""
    clients = supa.select("clients", active="eq.true", order="id")
    cfg["clients"] = [{"name": c["name"], "list": c["list"], "match": c["match"] or [c["name"]],
                       "spokespersons": c["spokespersons"] or [], "exclude": c["exclude"] or [],
                       "only_dutch": bool(c.get("only_dutch")), "id": c["id"]} for c in clients]
    sources = supa.select("sources", active="eq.true", order="id")
    cfg["wordpress_sources"] = [{"outlet": s["outlet"], "base": s["url"]}
                                for s in sources if s["type"] == "wordpress"]
    cfg["rss_sources"] = [{"outlet": s["outlet"], "url": s["url"],
                           "kind": "press_release" if (s["notes"] or "") == "press_release" else ""}
                          for s in sources if s["type"] == "rss"]
    cfg["sitemap_sources"] = [{"outlet": s["outlet"], "index": s["url"]}
                              for s in sources if s["type"] == "sitemap"]
    names = {c["id"]: c["name"] for c in clients}
    existing = []
    for m in supa.select("mentions", select="id,client_id,outlet,title,url,published,method,kind,matched_on,found_at"):
        if m["client_id"] in names:
            existing.append({**m, "client": names[m["client_id"]], "published": m["published"] or "",
                             "kind": m["kind"] or "", "matched_on": m["matched_on"] or ""})
    return existing


def main():
    cfg = json.loads((ROOT / "config.json").read_text())
    DATA.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=cfg.get("lookback_days", 30))
    use_db = supa.enabled()

    existing = []
    if use_db:
        existing = load_from_db(cfg)
    elif CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing.append(r)
    # bestaande dubbelen opruimen; directe site-link gaat voor Google-link
    existing.sort(key=lambda r: r["method"] == "google_news")
    seen_urls, seen_keys, kept = set(), set(), []
    for r in existing:
        if r["url"] in seen_urls or norm_key(r) in seen_keys:
            continue
        kept.append(r)
        seen_urls.add(r["url"])
        seen_keys.add(norm_key(r))
    existing = kept

    log, new_rows, replaced = [], [], []
    for client in cfg["clients"]:
        found = []
        for src in cfg["wordpress_sources"]:
            found += search_wordpress(src, client, since, log)
            time.sleep(1)
        for src in cfg.get("rss_sources", []):
            found += search_rss(src, client, since, log)
        for src in cfg.get("sitemap_sources", []):
            found += search_sitemap(src, client, since, log)
        if cfg.get("google_news"):
            found += search_google_news(client, since, log)
        if not use_db:
            found += manual_links(client, log)
        found.sort(key=lambda r: r["method"] == "google_news")
        for row in found:
            key = norm_key(row)
            if row["method"] != "google_news":
                # directe link vervangt een eerder bewaarde Google-link van hetzelfde artikel
                for old in existing:
                    if old["method"] == "google_news" and norm_key(old) == key:
                        row["found_at"] = old["found_at"]
                        old.update(row)
                        replaced.append(old)
                        seen_urls.add(row["url"])
            if row["url"] in seen_urls or key in seen_keys:
                continue
            row["found_at"] = now.isoformat(timespec="seconds")
            new_rows.append(row)
            seen_urls.add(row["url"])
            seen_keys.add(key)

    if use_db:
        ids = {c["name"]: c["id"] for c in cfg["clients"]}
        for old in replaced:
            if old.get("id"):
                supa.update("mentions", {"id": old["id"]}, {
                    "outlet": old["outlet"], "title": old["title"], "url": old["url"],
                    "published": old["published"] or None, "method": old["method"],
                    "kind": old["kind"] or None, "matched_on": old["matched_on"] or None})
        payload = [{"client_id": ids[r["client"]], "outlet": r["outlet"], "title": r["title"],
                    "url": r["url"], "published": r["published"] or None, "method": r["method"],
                    "kind": r["kind"] or None, "matched_on": r["matched_on"] or None,
                    "found_at": r["found_at"]} for r in new_rows]
        for i in range(0, len(payload), 200):
            supa.insert("mentions", payload[i:i + 200], on_conflict="client_id,url", ignore_duplicates=True)
        # CSV blijft als leesbare export naast de database
        existing = [{k: v for k, v in r.items() if k in FIELDS} for r in load_from_db(cfg)]
        new_rows_export = []
    else:
        new_rows_export = new_rows

    all_rows = sorted(existing + new_rows_export,
                      key=lambda r: (r["client"], r["published"]), reverse=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    write_summary(cfg, all_rows, now)

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
