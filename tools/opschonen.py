"""Bestaande vermeldingen opnieuw toetsen voor klanten met only_dutch: wat nu niet meer matcht wordt ruis."""
import sys
sys.path.insert(0, ".")
import monitor  # noqa: E402
import supa  # noqa: E402

clients = [c for c in supa.select("clients", active="eq.true") if c.get("only_dutch")]
for c in clients:
    cl = {"name": c["name"], "match": c["match"] or [c["name"]], "spokespersons": c["spokespersons"] or [],
          "exclude": c["exclude"] or [], "only_dutch": True}
    rows = supa.select("mentions", client_id=f"eq.{c['id']}", status="neq.ruis", method="neq.handmatig",
                       select="id,title,outlet")
    weg = [r for r in rows if not monitor.match_client(cl, r["title"])]
    for r in weg:
        supa.update("mentions", {"id": r["id"]}, {"status": "ruis", "notes": "Niet Nederlandstalig (alleen-Nederlands-filter)"})
    print(f"{c['name']}: {len(rows)} gecontroleerd, {len(weg)} als ruis gemarkeerd, {len(rows) - len(weg)} blijven staan")
    for r in rows:
        if r not in weg:
            print("  blijft:", r["outlet"], "|", r["title"][:100])
