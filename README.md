# PR Goeroes monitor (test)

Gratis test om te laten zien of we Nederlandse publicaties beter vinden dan Agility PR.

## Wat het doet
Drie keer per dag zoekt `monitor.py` per klant naar vermeldingen via:
1. **WordPress-zoekfunctie** van vakmedia (`/wp-json/wp/v2/search`). Respecteert robots.txt.
2. **Google News RSS** als vangnet. Alleen voor de testfase: de voorwaarden staan geen commercieel gebruik toe.

Alleen artikelen waarin de klantnaam als heel woord voorkomt (en geen uitsluitwoord) worden bewaard.

## Bestanden
- `config.json` — klanten, zoektermen, woordvoerders, uitsluitwoorden en bronnen
- `data/mentions.csv` — alle gevonden publicaties, ontdubbeld
- `data/runs.log` — per run wat elke bron opleverde of waarom hij werd overgeslagen

## Draaien
- Automatisch: drie keer per dag via GitHub Actions (`.github/workflows/daily.yml`)
- Handmatig: tab **Actions** → *Monitor* → **Run workflow**
- Lokaal: `python3 monitor.py`

## Klant of bron toevoegen
Pas `config.json` aan. Woordvoerders (voor- en achternaam) toevoegen aan `spokespersons` maakt het zoeken preciezer, zoals Jennifer zelf zoekt.

## Bronnen per type (config.json)
- `wordpress_sources` — zoekfunctie van WordPress-sites
- `rss_sources` — RSS-feeds (AccountancyWorld, Persberichten.com)
- `sitemap_sources` — sitemaps, gezocht op klantnaam in de link (Logimerce; hun zoekpagina is volgens robots.txt verboden voor bots)
- Google News als vangnet

De monitor draait drie keer per dag (om de 8 uur), omdat de feed van Persberichten.com maar ongeveer 12 uur terug gaat.

## Handmatig een publicatie toevoegen
Voor sites die bots weren (zoals Emerce) of iets dat Jennifer zelf vond:
- Tab **Actions** → *Publicatie toevoegen* → **Run workflow** → klant en link invullen. Titel, medium en datum worden waar mogelijk van de pagina gehaald.
- Of lokaal: `python add_link.py Aspyre https://...`

De links staan in `data/manual.csv` en komen bij de volgende run in `data/mentions.csv` (methode `handmatig`).
