"""Voegt een handmatig gevonden publicatie toe aan data/manual.csv.

Gebruik: python add_link.py <klant> <url> [titel] [outlet]
Ontbrekende titel/outlet/datum worden waar mogelijk van de pagina gehaald.
"""
import csv, html, re, sys, urllib.parse
from pathlib import Path
from monitor import fetch

PATH = Path(__file__).parent / "data" / "manual.csv"
FIELDS = ["client", "url", "outlet", "title", "published", "note"]


def main():
    if len(sys.argv) < 3:
        sys.exit("Gebruik: python add_link.py <klant> <url> [titel] [outlet]")
    client, url = sys.argv[1].strip(), sys.argv[2].strip()
    title = sys.argv[3].strip() if len(sys.argv) > 3 else ""
    outlet = sys.argv[4].strip() if len(sys.argv) > 4 else ""
    published = ""
    try:
        page = fetch(url)
        if not title:
            m = (re.search(r'property="og:title" content="([^"]+)"', page)
                 or re.search(r"<title>(.*?)</title>", page, re.S))
            title = html.unescape(m.group(1)).strip() if m else ""
        if not outlet:
            m = re.search(r'property="og:site_name" content="([^"]+)"', page)
            outlet = html.unescape(m.group(1)).strip() if m else ""
        m = (re.search(r'"datePublished"\s*:\s*"([^"]+)"', page)
             or re.search(r'article:published_time" content="([^"]+)"', page))
        published = m.group(1)[:10] if m else ""
    except Exception:
        pass  # pagina niet op te halen (bv. botcontrole): val terug op de link
    host = urllib.parse.urlsplit(url).netloc.replace("www.", "")
    outlet = outlet or host
    title = title or urllib.parse.urlsplit(url).path.rstrip("/").split("/")[-1].replace("-", " ")
    rows = list(csv.DictReader(PATH.open(encoding="utf-8"))) if PATH.exists() else []
    if any(r["url"] == url for r in rows):
        print("Staat er al in:", url)
        return
    rows.append({"client": client, "url": url, "outlet": outlet, "title": title,
                 "published": published, "note": "Handmatig toegevoegd"})
    with PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Toegevoegd: [{client}] {outlet}: {title}")


if __name__ == "__main__":
    main()
