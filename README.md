# Dividend Dashboard

Zelf-hosted dashboard om je aandelenportefeuille en dividendinkomen bij te
houden. Koersen, sector en dividendhistorie komen live van Yahoo Finance (via
`yfinance`, geen API key nodig). Alle bedragen worden omgerekend naar euro's.
Data (je holdings) wordt lokaal opgeslagen in een SQLite-bestand — er wordt
niets naar een externe partij verstuurd, behalve de koers-opvragingen bij
Yahoo Finance zelf.

## Features

- **Portfolio overzicht**: koers, waarde, rendement en dividendrendement per
  positie, plus een totaalregel.
- **Dividend income forecasting**: verwacht dividendinkomen per maand (op
  basis van historische betaalmaanden) en op jaarbasis, inclusief
  yield-on-cost per holding.
- **Dividendkalender**: eerstvolgende ex-dividenddatum per aandeel. Waar Yahoo
  geen exacte datum geeft, wordt deze geschat op basis van de historische
  betaalfrequentie (gemarkeerd als "geschat").
- **Sectorspreiding**: donutgrafiek van je portefeuille per sector.
- **Ticker zoeken**: typ een naam of symbool (aandeel of crypto) bij "Aandeel
  toevoegen" en kies uit live suggesties van Yahoo Finance, in plaats van de
  exacte tickernotatie te moeten kennen.

Niet (nog) ingebouwd: dividend safety scores, stock comparison, een dividend-
calculator en live brokerkoppelingen. Dat past qua architectuur prima later
bovenop dezelfde backend.

## 1. Lokaal draaien (aanbevolen om eerst te testen)

Vereist: Docker + Docker Compose.

```bash
docker compose up --build
```

Open daarna `http://localhost:8000`. Voeg een aandeel toe via **+ Aandeel
toevoegen**: typ een naam of ticker en kies uit de live suggesties, of gebruik
zelf de Yahoo Finance-tickernotatie, bijvoorbeeld:

| Beurs | Ticker-formaat | Voorbeeld |
|---|---|---|
| VS (Nasdaq/NYSE) | geen suffix | `AAPL`, `KO` |
| Euronext Amsterdam | `.AS` | `ASML.AS`, `UNA.AS` |
| Euronext Brussel | `.BR` | `KBC.BR` |
| Londen | `.L` | `ULVR.L` |
| Frankfurt/Xetra | `.DE` | `SAP.DE` |

Je data staat in `./data/dividend.db`. Maak hier af en toe een kopie van als
back-up — dit bestand bevat al je holdings.

Koersen/dividenddata worden 15 minuten server-side gecachet. Klik op
**Ververs koersen** rechtsboven om direct verse data op te halen.

## 2. Draaien op je Umbrel

Er zijn twee routes. Route A werkt altijd en direct. Route B geeft een echte
app-tegel met icoon in je Umbrel-dashboard, maar vereist dat je een eigen
Community App Store hebt (of aanmaakt) — en Umbrel's manifest-schema kan per
versie licht verschillen, dus controleer dit tegen een actueel voorbeeld in
[getumbrel/umbrel-apps](https://github.com/getumbrel/umbrel-apps) voordat je
het installeert.

### Route A — direct via SSH (gegarandeerd werkend)

1. Kopieer deze hele map naar je Umbrel (bv. via Nextcloud-sync, `scp`, of een
   git-repo die je op de Umbrel clonet).
2. SSH naar je Umbrel en ga naar de map.
3. Start de stack:
   ```bash
   docker compose up --build -d
   ```
4. Open `http://<umbrel-ip>:8000`.

Back-ups, updates en herstarts doe je met de normale `docker compose`
commando's. Dit verschijnt niet als tegel in de Umbrel-appenlijst, maar werkt
verder identiek.

### Route B — als Umbrel App Store tegel

De map `umbrel-store/` bevat een kant-en-klare Community App Store: een
`umbrel-app-store.yml` op de root, en daaronder `michael-apps-dividend-dashboard/`
met het app-manifest, de Umbrel-compose file en een kopie van de broncode + icoon.

Belangrijk: Umbrel eist dat de **app-id begint met de store-id** uit
`umbrel-app-store.yml` (hier: `michael-apps`), en dat de **mapnaam exact gelijk
is aan die app-id** — anders wordt de app stilletjes uit de lijst gefilterd
zonder foutmelding. Vandaar de wat omslachtige naam
`michael-apps-dividend-dashboard`.

Daarnaast bouwt Umbrel bij installatie **niet** zelf een image vanuit
broncode (`build:` in `docker-compose.yml` wordt genegeerd) — de app moet een
kant-en-klare, al gepubliceerde Docker-image gebruiken, net als bijvoorbeeld
Nextcloud dat doet. Daarom bouwt en publiceert een GitHub Actions-workflow
(`.github/workflows/build-image.yml`) de image automatisch naar GitHub
Container Registry (ghcr.io) zodra je naar de `main`-branch pusht.

1. **Maak een (publiek) GitHub-repo aan**, bijvoorbeeld genaamd
   `umbrel-apps-michael`.
2. **Upload de inhoud van de `umbrel-store/`-map** naar de root van dat repo
   (dus `umbrel-app-store.yml`, `michael-apps-dividend-dashboard/` én de map
   `.github/` komen direct in de repo-root te staan, niet in een submap). Kan
   via `git push` of gewoon door de map naar de GitHub-website te slepen (Add
   file → Upload files).
3. **Pas 2 regels aan** in
   `michael-apps-dividend-dashboard/umbrel-app.yml` voordat je uploadt, en
   vervang `<jouw-github-gebruiker>` en `<repo-naam>` door je eigen
   GitHub-gebruikersnaam en de repo-naam die je bij stap 1 koos:
   ```yaml
   submission: https://github.com/<jouw-github-gebruiker>/<repo-naam>
   icon: https://raw.githubusercontent.com/<jouw-github-gebruiker>/<repo-naam>/main/michael-apps-dividend-dashboard/icon.svg
   ```
4. **Wacht tot de GitHub Actions-build klaar is**: ga naar het **Actions**-tabblad
   van je repo, de workflow "Build and publish Docker image" moet groen
   (geslaagd) worden. Duurt een paar minuten.
5. **Maak de gepubliceerde image openbaar**: ga naar je GitHub-profiel →
   **Packages** → `dividend-dashboard` → **Package settings** (rechts
   onderaan) → **Change visibility** → **Public**. Zonder deze stap kan Umbrel
   de image niet downloaden.
6. Ga op je Umbrel-dashboard naar **App Store → instellingen-icoon (of
   Settings) → Community App Stores** en voeg de URL van je nieuwe repo toe,
   bijvoorbeeld `https://github.com/<jouw-github-gebruiker>/<repo-naam>`.
7. Zoek in de App Store naar **Dividend Dashboard** en klik **Install**. Umbrel
   haalt nu de kant-en-klare image op (in plaats van zelf te bouwen) en zet 'm
   als tegel op je startscherm, met data in `${APP_DATA_DIR}/data` (neemt
   Umbrel automatisch mee in zijn eigen back-upmechanisme).

Update je later de code in `app/`? Push die wijziging naar dezelfde repo, dan
bouwt GitHub Actions automatisch een nieuwe image, en kun je in Umbrel op
**Update** klikken bij de app.

Umbrel's manifest-schema kan per versie licht verschillen — werkt de
installatie niet meteen, val dan terug op Route A, die blijft functioneel
identiek draaien. Draait de app al via Route A op poort 8000? Stop die eerst
met `docker compose down` in de oude map, anders
botst de poort met de nieuwe Umbrel-installatie.

## Architectuur

- **Backend**: FastAPI (Python), SQLite via SQLModel, `yfinance` voor koersen/
  dividenden/sector, met een 15-minuten in-memory cache om Yahoo Finance niet
  te overspoelen.
- **Frontend**: vanilla HTML/JS + Chart.js (via CDN), geen build-stap nodig.
- Eén Docker-image bevat zowel backend als frontend; de backend serveert de
  statische bestanden mee op dezelfde poort (8000).

## Bekende beperkingen

- `yfinance` is een niet-officiële wrapper rond Yahoo Finance-data en kan af
  en toe haperen als Yahoo iets aan hun website wijzigt.
- Ex-dividenddata is niet voor elk aandeel/ETF even compleet; waar nodig wordt
  een schatting gemaakt op basis van historische betaalfrequentie.
- Er is geen authenticatie op het dashboard zelf — dit is bedoeld voor gebruik
  binnen je eigen lokale netwerk (zoals gebruikelijk voor Umbrel-apps).
