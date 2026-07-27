# TRMNL - AH recept van de dag

Haalt dagelijks (06:00) het "Ik eet vandaag: ..." event van vandaag uit een
iCal-feed, haalt de titel/afbeelding van de AH-receptpagina op, en stuurt dit
via een webhook naar een TRMNL private plugin.

## Setup

1. **TRMNL**: maak een Private Plugin aan met strategy **Webhook**. Kopieer de
   webhook-URL (`https://usetrmnl.com/api/custom_plugins/<id>`).
2. **Markup**: plak `trmnl-full.liquid` in de "Edit Markup" editor van de plugin
   (evt. ook voor half_horizontal/half_vertical/quadrant, pas naar smaak aan).
3. **.env**: `cp .env.example .env` en vul beide URL's in — je publieke
   iCal-link en de webhook-URL uit stap 1. `.env` staat in `.gitignore` en zit
   dus niet in deze repo.
4. **Run**:
   ```bash
   docker compose up -d
   ```
   Dit haalt de kant-en-klare image van GHCR. Zelf bouwen uit de source kan met
   `docker compose -f compose.build.yaml up -d --build`.

   Bij het opstarten draait het script direct 1x (zie logs met
   `docker compose logs -f`), en daarna elke dag om 06:00 via cron.

## Deployen met Dockge

De GitHub Action in `.github/workflows/docker-publish.yml` bouwt bij elke push
naar `main` een image voor `linux/amd64` en `linux/arm64` en publiceert die als
`ghcr.io/gijsvdhoven/ahrecepten:latest`. Daardoor heeft een Dockge-stack alleen
`compose.yaml` en `.env` nodig, en die kun je allebei in de Dockge-UI beheren —
geen Dockerfile of source op de host nodig.

1. Zet het GHCR-package op **public** (of log op de host eenmalig in met
   `docker login ghcr.io`), anders kan Dockge de image niet pullen. Dat doe je
   op GitHub bij Packages → `ahrecepten` → Package settings → Change visibility.
2. Maak in Dockge een nieuwe stack `trmnl-ah-recept` en plak de inhoud van
   `compose.yaml` erin.
3. Vul in het `.env`-tabblad `ICAL_URL` en `TRMNL_WEBHOOK_URL` in.
4. Deploy. Bij een nieuwe versie is Dockge's **Update** genoeg: die doet een
   `pull` + `up`, en omdat de image uit de registry komt hoeft er niets
   gebouwd te worden.

Let op: `build:` staat met opzet niet in `compose.yaml`. Dockge is gebouwd rond
de compose-file en heeft geen ondersteuning voor het bouwen van een Dockerfile,
dus een stack met `build:` zou bij elke Update de oude image blijven draaien.

## Env vars

| Variabele           | Omschrijving                                      |
|----------------------|----------------------------------------------------|
| `ICAL_URL`           | Publieke iCal-link (`webcal://` mag, wordt omgezet)  |
| `TRMNL_WEBHOOK_URL`  | Webhook-URL van je TRMNL private plugin             |
| `RUN_ON_START`       | `true`/`false` — direct draaien bij container-start |

## Tests

De parser heeft een testsuite die geen netwerk nodig heeft:

```bash
pip install -r requirements.txt pytest
python -m pytest tests/ -q
```

De fixtures in `tests/fixtures.py` zijn gemodelleerd op de JSON-LD van een
echte Allerhande-pagina, inclusief de AH-eigenaardigheden: `recipeYield` als
lijst, ISO-8601 duren (`PT20M`), en `recipeInstructions` met "Stap 1" in
`name` en de echte instructie in `text`.

Los uitproberen tegen een echte receptlink:

```bash
python ah_scraper.py https://www.ah.nl/allerhande/recept/R-R484610/pastasalade-met-tomaat-en-mozzarella
```

## Tips

- Overweeg een aparte iCloud-agenda alleen voor deze "Ik eet vandaag"-events
  en gebruik die publieke link als `ICAL_URL`. Scheelt filteren op andere
  events die op dezelfde dag kunnen staan.
- `.env` staat in `.gitignore` — commit 'm niet, de iCal-link en webhook-URL
  zijn in feite geheimen (iedereen met de iCal-link kan je agenda-inhoud zien).
- Logs bekijken: `docker compose logs -f trmnl-ah-recept`
- Los testen zonder cron: `docker compose exec trmnl-ah-recept python main.py`
