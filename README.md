# TRMNL - AH recept van de dag

Haalt dagelijks (06:00) het "Ik eet vandaag: ..." event van vandaag uit een
iCal-feed, haalt de titel/afbeelding van de AH-receptpagina op, en stuurt dit
via een webhook naar een TRMNL private plugin.

## Setup

1. **TRMNL**: maak een Private Plugin aan met strategy **Webhook**. Kopieer de
   webhook-URL (`https://usetrmnl.com/api/custom_plugins/<id>`).
2. **Markup**: plak per layout het bijbehorende bestand in de "Edit Markup"
   editor van de plugin (zie [Schermontwerp](#schermontwerp)).
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

## Schermontwerp

Het display is 800x480 en 2-bit grijs: vier tinten, geen accentkleur. Hiërarchie
moet dus uit lettergrootte, gewicht en witruimte komen.

| Layout            | Bestand                        | Formaat   | Toont                                          |
|-------------------|--------------------------------|-----------|------------------------------------------------|
| `full`            | `trmnl-full.liquid`            | 800 x 480 | foto, ingrediënten én bereidingswijze          |
| `half_horizontal` | `trmnl-half-horizontal.liquid` | 800 x 240 | titel, meta, foto                              |
| `half_vertical`   | `trmnl-half-vertical.liquid`   | 400 x 480 | foto, 5 ingrediënten, 3 stappen (geklemd)      |
| `quadrant`        | `trmnl-quadrant.liquid`        | 400 x 240 | titel, meta                                    |

Uitgangspunten:

- **Het volle scherm is een kookscherm.** Kopstrook met titel, meta en een
  compacte foto; daaronder de ingrediënten links (smalle kolom, want korte
  regels) en de bereidingswijze rechts (brede kolom, want lange regels).
- **De foto is klein met opzet** (180 x 104). Groot genoeg om het gerecht te
  herkennen, klein genoeg om de bereidingswijze niet van het scherm te drukken.
  De URL komt uit de JSON-LD; TRMNL haalt de foto zelf op en dithert hem.
- **De stappen zijn genummerd** via de `item`/`index`-component, zodat je kunt
  terugvinden waar je was.
- **De metaregel** ("4 personen · 20 min · 560 kcal") wordt in Liquid opgebouwd,
  zodat er geen losse `·` overblijft als AH een veld niet levert.
- **Elke layout degradeert netjes**: zonder foto valt die weg, zonder
  ingrediënten of stappen verdwijnt dat blok, en zonder recept staat er "Geen
  recept gevonden voor vandaag".

Loopt de bereidingswijze bij een lang recept tegen de titelbalk aan? Verlaag
`MAX_STEPS` in `main.py`, of klem de stappen met `data-clamp="2"` zoals
`trmnl-half-vertical.liquid` doet.

Op het TRMNL-platform wordt je markup automatisch in de juiste `view`-div
gewikkeld, dus de templates leveren alleen `layout` + `title_bar` — en die
moeten broers zijn, niet genest.

De lettergroottes en marges van het framework zelf zijn niet in deze repo te
verifiëren; gebruik de live previewer van de plugin om de typografie te checken.
Let daarbij vooral op de hoogte van het volle scherm bij recepten met veel
ingrediënten.

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
pip install -r requirements-dev.txt
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
