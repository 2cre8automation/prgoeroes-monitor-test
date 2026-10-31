"""Verkenning 6: logo en huisstijl van prgoeroes.com ophalen."""
import re, os, urllib.request, urllib.parse, collections
UA = "Mozilla/5.0 (PRGoeroesMonitorTest; +https://2cre8.eu)"
B = "https://prgoeroes.com/"
os.makedirs("tools/brand", exist_ok=True)
def get(u, binary=False):
    r = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=30) as x:
        d = x.read(); return x.geturl(), x.headers.get("content-type",""), (d if binary else d.decode("utf-8","replace"))
url, ct, html = get(B)
print("final:", url)
cands = []
for m in re.finditer(r'<img[^>]+>', html):
    t = m.group(0)
    if re.search(r'logo', t, re.I):
        for s in re.findall(r'(?:src|data-src|srcset)="([^" ]+)', t): cands.append(s)
cands += re.findall(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
cands += re.findall(r'<link[^>]+rel="[^"]*icon[^"]*"[^>]+href="([^"]+)"', html)
cands += re.findall(r'url\(([^)]*logo[^)]*)\)', html, re.I)
print("kandidaten:", cands[:20])
n = 0
for c in dict.fromkeys(cands):
    u = urllib.parse.urljoin(url, c.strip("'\""))
    try:
        _, ct2, d = get(u, True)
        ext = os.path.splitext(urllib.parse.urlsplit(u).path)[1] or ".bin"
        fn = f"tools/brand/{n:02d}{ext}"; open(fn, "wb").write(d); n += 1
        print("opgeslagen", fn, ct2, len(d), u)
    except Exception as e: print("fout", u, e)
print("theme-color:", re.findall(r'theme-color"[^>]+content="([^"]+)"', html))
css = html
for h in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)[:8]:
    try: css += get(urllib.parse.urljoin(url, h))[2]
    except Exception: pass
cols = collections.Counter(c.lower() for c in re.findall(r'#[0-9a-fA-F]{6}\b', css))
print("kleuren:", cols.most_common(15))
fonts = collections.Counter(f.strip() for f in re.findall(r'font-family:\s*([^;}"]+)', css))
print("fonts:", fonts.most_common(8))
print("google fonts:", re.findall(r'fonts.googleapis.com/css[^"\')]+', html)[:4])
