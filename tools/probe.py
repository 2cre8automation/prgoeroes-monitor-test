"""Eenmalige verkenning: welke route werkt per niet-WordPress-site?"""
import urllib.request, urllib.error, re
UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
SITES = {
 "https://www.accountancyworld.nl": "Aspyre",
 "https://www.logimerce.nl": "Katapull",
 "https://www.persberichten.com": "Aspyre",
}
PATHS = ["/robots.txt", "/sitemap.xml", "/sitemap_index.xml", "/rss", "/rss.xml", "/feed",
         "/nieuws/rss", "/zoeken?q={q}", "/search?q={q}", "/zoeken?query={q}", "/?s={q}",
         "/search/?q={q}", "/zoek?q={q}"]
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(r, timeout=20) as x:
            return x.status, x.headers.get("content-type",""), x.read().decode("utf-8","replace"), x.geturl()
    except urllib.error.HTTPError as e:
        return e.code, "", "", u
    except Exception as e:
        return type(e).__name__, "", "", u
for base, q in SITES.items():
    print("\n=====", base)
    for p in PATHS:
        st, ct, body, final = get(base + p.format(q=q))
        hits = len(re.findall(q, body, re.I))
        print(f"{st} {p:22} {ct[:30]:30} len={len(body):7} '{q}'x{hits} -> {final[:80]}")
        if p == "/robots.txt" and st == 200:
            for line in body.splitlines():
                if re.match(r"(?i)(user-agent|disallow|sitemap)", line.strip()):
                    print("    ", line.strip()[:120])
        if hits and p not in ("/robots.txt",):
            for m in list(re.finditer(r'href="([^"]*)"[^>]*>[^<]*'+q, body, re.I))[:3]:
                print("     link:", m.group(1)[:140])
            for m in list(re.finditer(r'<loc>([^<]*)</loc>', body))[:5]:
                print("     loc:", m.group(1)[:140])
