"""Verkenning 8: streekomroep via monitor.fetch (met terugval bij onvolledige certificaatketen)."""
import sys; sys.path.insert(0, ".")
import monitor
for q in ["Ecoware", "laaggeletterdheid"]:
    try:
        b = monitor.fetch(f"https://streekomroepzoetermeerlansingerland.nl/wp-json/wp/v2/search?search={q}&per_page=10")
        print(q, "OK:", b[:1500])
    except Exception as e:
        print(q, "FOUT", repr(e))
