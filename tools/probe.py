"""Verkenning 2: opbouw van sitemaps en RSS-feeds."""
import urllib.request, re
UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=30) as x:
        return x.read().decode("utf-8", "replace")
def locs(xml): return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
for idx in ["https://logimerce.nl/sitemap/index.xml", "https://www.persberichten.com/sitemap.xml"]:
    print("\n=====", idx)
    try:
        x = get(idx); ls = locs(x); print("children:", len(ls))
        for l in ls[:15]: print("  ", l)
        for l in ls[-3:]: print("  (eind)", l)
        news = [l for l in ls if re.search(r"news|nieuws|persbericht|artikel|article", l, re.I)] or ls
        for child in news[:2] + news[-1:]:
            c = get(child); cl = locs(c)
            lm = re.findall(r"<lastmod>([^<]+)</lastmod>", c)
            print(f"  -> {child}: {len(cl)} urls, lastmod {lm[:1]} .. {lm[-1:]}")
            for l in cl[:3]: print("       ", l)
            hits = [l for l in cl if re.search("katapull|aspyre", l, re.I)]
            for h in hits[:5]: print("     HIT", h)
    except Exception as e:
        print("fout", e)
for feed in ["https://www.accountancyworld.nl/rss.xml", "https://www.persberichten.com/rss"]:
    print("\n=====", feed)
    x = get(feed)
    items = re.findall(r"<item>(.*?)</item>", x, re.S)
    print("items:", len(items))
    for it in items[:2] + [i for i in items if re.search("aspyre", i, re.I)][:1]:
        t = re.search(r"<title>(.*?)</title>", it, re.S); l = re.search(r"<link>(.*?)</link>", it, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        print("  ", (t.group(1) if t else "")[:90], "|", (l.group(1) if l else "")[:90], "|", d.group(1) if d else "")
    dates = re.findall(r"<pubDate>(.*?)</pubDate>", x)
    print("  oudste item:", dates[-1:] )
