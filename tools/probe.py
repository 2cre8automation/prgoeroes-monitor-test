"""Verkenning 3: Emerce (wire = persberichten)."""
import urllib.request, urllib.error, re, json
UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
B = "https://www.emerce.nl"
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, x.headers.get("content-type", ""), x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, "", ""
    except Exception as e:
        return type(e).__name__, "", ""
st, ct, body = get(B + "/robots.txt")
print("robots", st); print("\n".join(l for l in body.splitlines() if re.match(r"(?i)(user-agent|disallow|allow|sitemap)", l.strip()))[:1500])
st, ct, body = get(B + "/wp-json/")
print("\nwp-json", st, ct[:30], len(body))
if st == 200:
    try:
        routes = json.loads(body).get("routes", {})
        print("routes met wire/press/pers:", [r for r in routes if re.search("wire|press|pers", r)][:20])
    except Exception as e: print("parse", e)
st, ct, body = get(B + "/wp-json/wp/v2/types")
print("\ntypes", st, list(json.loads(body).keys()) if st == 200 else "")
for p in ["/wp-json/wp/v2/wire?search=Aspyre", "/wp-json/wp/v2/search?search=Aspyre&subtype=any",
          "/wp-json/wp/v2/search?search=Katapull", "/wire/feed/", "/wire/feed", "/feed/", "/wire/",
          "/sitemap_index.xml", "/sitemap.xml", "/wp-sitemap.xml", "/?s=Aspyre"]:
    st, ct, body = get(B + p)
    print(f"\n{st} {p} {ct[:30]} len={len(body)} Aspyre x{len(re.findall('aspyre', body, re.I))} Katapull x{len(re.findall('katapull', body, re.I))}")
    for m in re.findall(r"<loc>([^<]+)</loc>", body)[:40]:
        if re.search("wire|sitemap", m): print("   loc", m)
    for m in re.findall(r'href="([^"]*(?:aspyre|katapull)[^"]*)"', body, re.I)[:5]: print("   link", m)
    if p.startswith("/wp-json") and st == 200: print("  ", body[:400])
    if p.endswith("feed/") or p.endswith("feed"):
        for t in re.findall(r"<title>(.*?)</title>", body)[:3]: print("   title", t[:100])
        d = re.findall(r"<pubDate>(.*?)</pubDate>", body); print("   items", len(d), d[-1:] )
