"""Verkenning 7: waarom faalt Streekomroep Zoetermeer Lansingerland vanaf GitHub?"""
import urllib.request, urllib.error, ssl, socket
UA = "PRGoeroesMonitorTest/0.1 (+https://2cre8.eu)"
for u in ["https://streekomroepzoetermeerlansingerland.nl/robots.txt",
          "https://streekomroepzoetermeerlansingerland.nl/wp-json/wp/v2/search?search=Ecoware&per_page=10",
          "https://www.streekomroepzoetermeerlansingerland.nl/wp-json/wp/v2/search?search=Ecoware&per_page=10",
          "https://streekomroepzoetermeerlansingerland.nl/wp-json/wp/v2/search?search=laaggeletterdheid&per_page=5"]:
    try:
        r = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=25) as x:
            b = x.read().decode("utf-8", "replace")
            print("OK", x.status, u, "\n  ", b[:700].replace("\n", " "))
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, u)
    except Exception as e:
        print("FOUT", repr(e), u)
try: print("DNS", socket.gethostbyname("streekomroepzoetermeerlansingerland.nl"))
except Exception as e: print("DNS fout", e)
