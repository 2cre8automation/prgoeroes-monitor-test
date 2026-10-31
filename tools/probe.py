"""Verkenning 4: Emerce cms-api wire."""
import urllib.request, urllib.error, re, json
UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
B = "https://www.emerce.nl"
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, x.headers.get("content-type", ""), x.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, "", e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return type(e).__name__, "", ""
st, ct, b = get(B + "/robots.txt"); print("robots.txt inhoud:\n", b[:600])
st, ct, b = get(B + "/wire/"); print("\n/wire/ html:\n", b[:800])
root = json.loads(get(B + "/wp-json/")[2])
for r in ["/cms-api/v1/wire", "/cms-api/v1/wire/get"]:
    info = root["routes"].get(r, {})
    print("\nROUTE", r, json.dumps([{"methods": e.get("methods"), "args": list(e.get("args", {}).keys())} for e in info.get("endpoints", [])])[:600])
for p in ["/wp-json/cms-api/v1/wire", "/wp-json/cms-api/v1/wire?search=Aspyre", "/wp-json/cms-api/v1/wire/get",
          "/wp-json/cms-api/v1/wire/get?search=Aspyre", "/wp-json/cms-api/v1/wire/get?s=Aspyre",
          "/wp-json/cms-api/v1/wire/get?per_page=20", "/wp-json/cms-api/v1/wire/get-categories",
          "/wp-json/wp/v2/posts?search=Aspyre&per_page=5", "/wp-json/wp/v2/posts?search=Katapull&per_page=5",
          "/wp-json/wp/v2/posts?per_page=3"]:
    st, ct, b = get(B + p)
    print(f"\n{st} {p} len={len(b)} Aspyre x{len(re.findall('aspyre', b, re.I))} Katapull x{len(re.findall('katapull', b, re.I))}")
    print("  ", b[:500].replace("\n", " "))
