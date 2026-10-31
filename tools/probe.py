"""Verkenning 5: welke media die we nu via Google News vinden kunnen we direct uitlezen?"""
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
SITES = ["ad.nl", "gelderlander.nl", "emerce.nl", "mena.nl", "dutchitchannel.nl", "warehousetotaal.nl",
         "fonkonline.nl", "cashcow.nl", "duurzaam-ondernemen.nl", "amsterdamsdagblad.nl", "quasa.io",
         "frankwatching.com", "banken.nl", "infinance.nl", "accountancyvanmorgen.nl", "headliner.nl",
         "ictmagazine.nl", "persberichten.com", "drimble.nl", "nieuws.nl", "nu.nl", "rtvutrecht.nl", "duic.nl"]
FEEDS = ["/feed/", "/rss", "/rss.xml", "/feed.xml", "/home/rss.xml", "/nieuws/rss", "/rss/nieuws", "/index.xml"]
TERMS = ["katapull", "picqer", "aspyre"]


def get(u, n=400_000):
    r = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(r, timeout=25) as x:
            return x.status, x.geturl(), x.headers.get("content-type", ""), x.read(n).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, u, "", ""
    except Exception as e:
        return type(e).__name__, u, "", ""


def is_feed(body):
    return bool(re.search(r"<(rss|feed|rdf:RDF)\b", body[:3000]))


def hits(body):
    b = body.lower()
    return {t: b.count(t) for t in TERMS if t in b}


for d in SITES:
    base = f"https://www.{d}" if d.count(".") == 1 else f"https://{d}"
    print(f"\n===== {d}")
    st, url, ct, home = get(base + "/")
    print(f"home: {st} -> {url[:80]}  {'COOKIEWALL?' if re.search('privacy|consent|myprivacy', url) else ''}")
    st, _, _, rob = get(base + "/robots.txt", 60_000)
    star, block = False, []
    cur = []
    for line in rob.splitlines():
        l = line.split("#")[0].strip()
        if l.lower().startswith("user-agent:"):
            cur.append(l.split(":", 1)[1].strip())
        elif l.lower().startswith("disallow:"):
            path = l.split(":", 1)[1].strip()
            if "*" in cur and path:
                block.append(path)
        elif l and not l.lower().startswith(("allow", "crawl", "sitemap", "host")):
            pass
        if l.lower().startswith(("allow:", "disallow:")) is False and l.lower().startswith("user-agent:") is False:
            cur = [] if l and not l.lower().startswith("sitemap") else cur
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rob)
    print(f"robots: {st}; disallow voor *: {block[:12]}{' ...' if len(block) > 12 else ''}")
    print(f"  alles verboden: {'/' in block}")
    print(f"  sitemaps: {sitemaps[:8]}")
    # feeds
    links = re.findall(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]*>', home)
    hrefs = [urllib.parse.urljoin(base + "/", h) for l in links for h in re.findall(r'href="([^"]+)"', l)]
    found = []
    for f in dict.fromkeys(hrefs[:4] + [base + p for p in FEEDS]):
        st, url, ct, b = get(f, 300_000)
        if st == 200 and is_feed(b):
            found.append(f"{f} ({len(re.findall('<item|<entry', b))} items)")
    print(f"feeds: {found[:4] or 'geen'}")
    st, _, _, wp = get(base + "/wp-json/", 2000)
    print(f"wordpress api: {st == 200 and wp.strip().startswith('{')}")
    # nieuws-sitemap
    cands = [s for s in sitemaps if "news" in s.lower() or "nieuws" in s.lower()]
    cands += [base + p for p in ["/news-sitemap.xml", "/sitemap-news.xml", "/sitemap_news.xml", "/news_sitemap.xml"]]
    for s in dict.fromkeys(cands):
        st, url, ct, b = get(s)
        if st == 200 and "<urlset" in b:
            print(f"nieuws-sitemap: {s} ({b.count('<url>')} urls, met titel: {'<news:title>' in b})")
            break
    else:
        print("nieuws-sitemap: geen")
    # gewone sitemap: zoek klantnamen in slugs (eerste index, max 6 subsitemaps, laatste eerst)
    if sitemaps:
        st, url, ct, idx = get(sitemaps[0])
        subs = re.findall(r"<loc>([^<]+)</loc>", idx) if "<sitemapindex" in idx else []
        tot = hits(idx)
        for s in subs[-6:]:
            for k, v in hits(get(s)[3]).items():
                tot[k] = tot.get(k, 0) + v
        print(f"sitemap-index: {len(subs)} subsitemaps; klantnamen in laatste 6: {tot or 'geen'}")
