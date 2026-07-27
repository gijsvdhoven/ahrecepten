# TRMNL - AH recept van de dag

Haalt dagelijks (06:00) het "Ik eet vandaag: ..." event van vandaag uit een
iCal-feed, haalt de titel/afbeelding van de AH-receptpagina op, en stuurt dit
via een webhook naar een TRMNL private plugin.

## Setup

1. **TRMNL**: maak een Private Plugin aan met strategy **Webhook**. Kopieer de
   webhook-URL (`https://usetrmnl.com/api/custom_plugins/<id>`).
2. **Markup**: plak `trmnl-full.liquid` in de "Edit Markup" editor van de plugin
   (evt. ook voor half_horizontal/half_vertical/quadrant, pas naar smaak aan).
3. **.env**: is al ingevuld met je iCal-link. Vul `TRMNL_WEBHOOK_URL` nog aan
   met de echte webhook-ID uit stap 1.
4. **Build & run**:
   ```bash
   docker compose up -d --build
   ```
   Bij het opstarten draait het script direct 1x (zie logs met
   `docker compose logs -f`), en daarna elke dag om 06:00 via cron.

## Env vars

| Variabele           | Omschrijving                                      |
|----------------------|----------------------------------------------------|
| `ICAL_URL`           | Publieke iCal-link (webcal:// omgezet naar https://) |
| `TRMNL_WEBHOOK_URL`  | Webhook-URL van je TRMNL private plugin             |
| `RUN_ON_START`       | `true`/`false` — direct draaien bij container-start |

## Tips

- Overweeg een aparte iCloud-agenda alleen voor deze "Ik eet vandaag"-events
  en gebruik die publieke link als `ICAL_URL`. Scheelt filteren op andere
  events die op dezelfde dag kunnen staan.
- `.env` staat in `.gitignore` — commit 'm niet, de iCal-link en webhook-URL
  zijn in feite geheimen (iedereen met de iCal-link kan je agenda-inhoud zien).
- Logs bekijken: `docker compose logs -f trmnl-ah-recept`
- Los testen zonder cron: `docker compose exec trmnl-ah-recept python main.py`
