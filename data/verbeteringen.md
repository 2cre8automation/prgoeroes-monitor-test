# Verbeterpunten monitor

Nieuwste punten bovenaan. Doorvoeren na beoordeling door Farrukh.

## 2026-11-05

### Drukwerkdeal — Fonk Magazine
- **Titel:** Drukwerkdeal genomineerd voor B2B Award bij Shopping Awards (4 nov)
- **Oorzaak:** (a) medium staat niet in onze bronnen (niet in data/runs.log). Google News vond eerder wel FONK-artikelen (zie mentions.csv: Drukwerkdeal 31 aug, Multitint 30 jul), maar dit artikel kwam in de runs tot en met 5 nov 07:15 niet mee: 44 items, 3 relevant, maar geen nieuwe publicatie (runs van 4 nov 23:00 en 5 nov 07:15: 0 nieuw).
- **Voorgestelde oplossing:** https://fonkmagazine.com als bron toevoegen. Route nog vaststellen: eerst de WordPress-zoekfunctie proberen, anders RSS of sitemap, en robots.txt controleren. De site was vanuit deze run niet te openen, dus dit is niet getest. Extra te controleren: Emerce heeft mogelijk hetzelfde bericht (https://www.emerce.nl/wire/drukwerkdeal-genomineerd-b2b-award-shopping-awards-2); datum onbekend, kan ook een oudere nominatie zijn.
- **Status:** open

### Straight Line Leadership — Fonk Magazine
- **Titel:** Van creatieve chaos naar concrete resultaten: de kracht van Straight-Line Leadership (4 nov)
- **Oorzaak:** (a) medium staat niet in onze bronnen (niet in data/runs.log). Daarnaast zou de bron alleen niet genoeg zijn: match_client keurt deze titel af vanwege het streepje (getest met de huidige config.json), net als bij Wees Meer op 4 nov. Google News: 12 items, 0 relevant.
- **Voorgestelde oplossing:** dezelfde bron als hierboven toevoegen en eerst het open punt van 4 nov doorvoeren ("Straight-Line Leadership" als zoekterm, Kristof Cuppens als woordvoerder, of streepje en spatie gelijk behandelen). Dat punt heeft nu 3 gemiste publicaties op 2 media.
- **Status:** open

## 2026-11-04

### Straight Line Leadership — Wees Meer
- **Titels:** Kristof Cuppens (Straight-Line Leadership): ‘Ondernemers krijgen dankzij ons meer mentale ruimte, lichtheid en overzicht' (3 nov) en Straight-Line Leadership geeft 1 miljoen boeken weg aan ondernemers (3 nov)
- **Oorzaak:** (b) medium wordt wel doorzocht, maar de zoekterm matchte niet. Beide artikelen schrijven "Straight-Line" met streepje. Onze term is "Straight Line Leadership" zonder streepje. De zoekfunctie van Wees Meer gaf in beide runs 2 resultaten, daarna keurde match_client ze af; getest met de titels uit de Agility-mail. Google News gaf 12 items en 0 relevant; vermoedelijk dezelfde oorzaak, niet vastgesteld.
- **Voorgestelde oplossing:** in de database "Straight-Line Leadership" als zoekterm toevoegen, plus woordvoerder Kristof Cuppens (Managing Partner). Bredere optie: match_client streepje en spatie als gelijk laten behandelen, zodat dit ook bij andere klantnamen niet meer gebeurt. Na de wijziging beide artikelen controleren in de eerstvolgende run; de artikelen: https://weesmeer.nl/kristof-cuppens-straight-line-leadership-ondernemers-krijgen-dankzij-ons-meer-mentale-ruimte-lichtheid-en-overzicht/ en https://weesmeer.nl/straight-line-leadership-geeft-1-miljoen-boeken-weg-aan-ondernemers/
- **Status:** open

## 2026-11-02

### Ecoware — Streekomroep Zoetermeer Lansingerland
- **Titel:** Zoetermeer zet in op jongeren en gezinnen in strijd tegen laaggeletterdheid (28 okt)
- **Oorzaak:** (a) medium staat niet in onze bronnen (niet in data/runs.log). Onzeker of het artikel Ecoware echt noemt; de samenvatting doet dat niet.
- **Voorgestelde oplossing:** eerst het artikel openen via de link in de Agility-mail. Noemt het Ecoware, voeg dan de site van de streekomroep toe als bron (url nog op te zoeken; niet kunnen vaststellen). Zo niet: vervalt, dan telt het als ruis voor Agility.
- **Status:** opgelost 2 nov. Artikel noemt Ecoware (WordPress-zoekfunctie van de streekomroep geeft precies dit artikel). Toegevoegd: Streekomroep Zoetermeer Lansingerland, Streekblad Zoetermeer en Zoetermeer Actief. De streekomroep heeft een onvolledige certificaatketen; de monitor vangt dat nu op.

### INSIFR — Wij Blijven Hier
- **Titel:** Islamic Finance ontwikkelingen (30 okt)
- **Oorzaak:** (a) medium staat niet in onze bronnen (niet in data/runs.log). Vermoedelijk ruis: de samenvatting noemt INSIFR niet en verwijst naar "rond 2015".
- **Voorgestelde oplossing:** eerst het artikel openen via de link in de Agility-mail. Noemt het INSIFR, voeg dan wijblijvenhier.nl toe als bron (route nog vaststellen). Zo niet: vervalt.
- **Status:** bron toegevoegd 2 nov (Wij Blijven Hier, via WordPress-zoekfunctie). Die zoekfunctie vindt INSIFR nergens op de site, dus het artikel noemt INSIFR waarschijnlijk niet: telt voorlopig als ruis voor Agility.

### Katapull — Drimble (uit briefing 1 nov, nog niet eerder vergeleken)
- **Titel:** Katapull neemt Picqer over (31 okt)
- **Oorzaak:** (a) medium staat niet in onze bronnen (niet in data/runs.log). Hetzelfde nieuws en dezelfde titel hadden wij wel via Warehouse Totaal.
- **Voorgestelde oplossing:** drimble.nl als bron toevoegen als er een RSS-feed of sitemap is (nog te controleren). Drimble lijkt een nieuwsverzamelaar, dus eerst beoordelen of doorplaatsingen meetellen voor Jennifer.
- **Status:** open, vraag voor Jennifer op vrijdag: tellen doorplaatsingen op nieuwsverzamelaars als Drimble mee?
