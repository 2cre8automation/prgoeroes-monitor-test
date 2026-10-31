# PR Goeroes monitor (test)

Gratis test om te laten zien of we Nederlandse publicaties beter vinden dan Agility PR.

## Wat het doet
Elke ochtend zoekt `monitor.py` per klant naar vermeldingen via:
1. **WordPress-zoekfunctie** van vakmedia (`/wp-json/wp/v2/search`). Respecteert robots.txt.
2. **Google News RSS** als vangnet. Alleen voor de testfase: de voorwaarden staan geen commercieel gebruik toe.

Alleen artikelen waarin de klantnaam als heel woord voorkomt (en geen uitsluitwoord) worden bewaard.

## Bestanden
- `config.json` — klanten, zoektermen, woordvoerders, uitsluitwoorden en bronnen
- `data/mentions.csv` — alle gevonden publicaties, ontdubbeld
- `data/runs.log` — per run wat elke bron opleverde of waarom hij werd overgeslagen

## Draaien
- Automatisch: dagelijks via GitHub Actions (`.github/workflows/daily.yml`)
- Handmatig: tab **Actions** → *Dagelijkse monitor* → **Run workflow**
- Lokaal: `python3 monitor.py`

## Klant of bron toevoegen
Pas `config.json` aan. Woordvoerders (voor- en achternaam) toevoegen aan `spokespersons` maakt het zoeken preciezer, zoals Jennifer zelf zoekt.
