"""Zet config.json en de bestaande CSV-data over naar Supabase. Veilig om opnieuw te draaien."""
import csv
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import supa  # noqa: E402


def domain_of(url):
    return urllib.parse.urlsplit(url).netloc.lower().replace("www.", "")


def main():
    if not supa.enabled():
        sys.exit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY ontbreken")
    cfg = json.loads((ROOT / "config.json").read_text())

    clients = [{"name": c["name"], "list": c.get("list", "vast"), "match": c["match"],
                "spokespersons": c.get("spokespersons", []), "exclude": c.get("exclude", [])}
               for c in cfg["clients"]]
    supa.insert("clients", clients, on_conflict="name", ignore_duplicates=True)

    sources = [{"outlet": s["outlet"], "type": "wordpress", "url": s["base"], "domain": domain_of(s["base"])}
               for s in cfg["wordpress_sources"]]
    sources += [{"outlet": s["outlet"], "type": "rss", "url": s["url"], "domain": domain_of(s["url"]),
                 "notes": s.get("kind")} for s in cfg.get("rss_sources", [])]
    sources += [{"outlet": s["outlet"], "type": "sitemap", "url": s["index"], "domain": domain_of(s["index"])}
                for s in cfg.get("sitemap_sources", [])]
    # Emerce weert bots: alleen handmatig
    for s in sources:
        if s["domain"] == "emerce.nl":
            s["type"] = "handmatig"
            s["notes"] = "Botcontrole op de site; alleen handmatig of via nieuwsbron"
    sources = [{"outlet": x["outlet"], "type": x["type"], "url": x["url"], "domain": x["domain"],
                "notes": x.get("notes")} for x in sources]  # alle rijen dezelfde velden
    supa.insert("sources", sources, on_conflict="url", ignore_duplicates=True)

    ids = {c["name"]: c["id"] for c in supa.select("clients", select="id,name")}
    rows = []
    csv_path = ROOT / "data" / "mentions.csv"
    if csv_path.exists():
        for r in csv.DictReader(csv_path.open(encoding="utf-8")):
            if r["client"] not in ids:
                continue
            rows.append({"client_id": ids[r["client"]], "outlet": r["outlet"], "title": r["title"],
                         "url": r["url"], "published": r["published"] or None, "method": r["method"],
                         "kind": r["kind"] or None, "matched_on": r["matched_on"] or None,
                         "found_at": r["found_at"]})
    # ontdubbelen binnen de batch (zelfde klant + url)
    seen, uniq = set(), []
    for r in rows:
        k = (r["client_id"], r["url"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    for i in range(0, len(uniq), 200):
        supa.insert("mentions", uniq[i:i + 200], on_conflict="client_id,url", ignore_duplicates=True)

    media_path = ROOT / "db" / "media.json"
    if media_path.exists():
        media = json.loads(media_path.read_text())
        keys = ["outlet", "domain", "monthly_visitors", "cpm_eur", "confidence", "source_urls", "notes"]
        media = [{k: m.get(k) for k in keys} for m in media]
        supa.insert("media", media, on_conflict="outlet", ignore_duplicates=True)  # aanpassingen van Jennifer niet overschrijven
        print(f"mediatabel: {len(media)} media")

    print(f"klanten: {len(ids)}, bronnen: {len(sources)}, publicaties overgezet: {len(uniq)}")


if __name__ == "__main__":
    main()
