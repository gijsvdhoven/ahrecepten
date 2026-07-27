import os
import re
import sys
from datetime import date, datetime

import requests
from icalendar import Calendar

from ah_scraper import scrape_recipe

PREFIX = "Ik eet vandaag:"

URL_RE = re.compile(r"https?://\S+")


def require_env(name: str) -> str:
    """Lees een verplichte env var, met een leesbare fout i.p.v. een KeyError."""
    value = os.environ.get(name)
    if not value:
        sys.exit(
            f"Environment variable {name} is niet gezet. "
            "Zet 'm in .env (zie .env.example) en herstart de container."
        )
    return value


def normalize_ical_url(url: str) -> str:
    """iCloud deelt agenda's als webcal://; requests kent dat schema niet."""
    if url.startswith("webcal://"):
        return "https://" + url[len("webcal://") :]
    return url


def event_date(value):
    """Bepaal de datum van een DTSTART.

    All-day events geven een `date`, getimede events een `datetime`. Een
    getimede datetime met tijdzone rekenen we om naar lokale tijd, zodat de
    vergelijking met `date.today()` in dezelfde tijdzone gebeurt.
    """
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone()
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _strip_prefix(summary: str):
    """Geef de tekst na "Ik eet vandaag:" terug, of None als het prefix mist."""
    stripped = summary.strip()
    if stripped.lower().startswith(PREFIX.lower()):
        return stripped[len(PREFIX) :]
    return None


def _find_url(*values):
    for value in values:
        if not value:
            continue
        match = URL_RE.search(str(value))
        if match:
            # Leestekens die aan de URL vastgeplakt zitten horen er niet bij.
            return match.group(0).rstrip(').,;"\'')
    return None


def parse_todays_recipe(ical_text: str, today: date | None = None):
    """Zoek in een iCal-feed het "Ik eet vandaag: ..." event van vandaag.

    Geeft (url, titel) terug, of (None, None) als er niets voor vandaag staat.
    """
    today = today or date.today()
    cal = Calendar.from_ical(ical_text)

    for component in cal.walk("VEVENT"):
        dtstart = component.get("dtstart")
        if dtstart is None:  # een VEVENT zonder DTSTART mag ons niet laten crashen
            continue
        if event_date(dtstart.dt) != today:
            continue

        summary = str(component.get("summary", ""))
        # Als de agenda meer dan 1 event per dag bevat, pak alleen het
        # "Ik eet vandaag: ..." event.
        title = _strip_prefix(summary)
        if title is None:
            continue

        # De link staat meestal in de titel, maar Apple Agenda zet 'm net zo
        # vaak in de notities of het URL-veld.
        url = _find_url(summary, component.get("description"), component.get("url"))

        if url:
            title = title.replace(url, "")
        title = title.strip(" :-–")

        return url, (title or None)

    return None, None


def get_todays_recipe(ical_url: str, today: date | None = None):
    resp = requests.get(normalize_ical_url(ical_url), timeout=15)
    resp.raise_for_status()
    return parse_todays_recipe(resp.text, today=today)


def enrich_from_page(url):
    """Scrape de AH-receptpagina voor titel/afbeelding/tijd/porties (best effort)."""
    if not url:
        return {}
    try:
        return scrape_recipe(url)
    except Exception as e:
        print(f"Kon receptpagina niet scrapen ({url}): {e}", file=sys.stderr)
        return {}


def build_payload(url, fallback_title, extra, today: date | None = None):
    """Bouw de TRMNL webhook-payload.

    De webhook accepteert max. 2KB, dus we sturen alleen een compacte selectie
    door. `extra` (ah_scraper output) bevat meer (ingrediënten, stappen,
    rating) mocht je die ooit ergens anders willen gebruiken.
    """
    today = today or date.today()
    return {
        "merge_variables": {
            "title": extra.get("title")
            or fallback_title
            or "Geen recept gevonden voor vandaag",
            "url": url,
            "image": extra.get("image"),
            "servings": extra.get("servings"),
            "prep_time": extra.get("prep_time") or extra.get("total_time"),
            "kcal": extra.get("kcal"),
            "date": today.isoformat(),
        }
    }


def main():
    ical_url = require_env("ICAL_URL")
    webhook_url = require_env("TRMNL_WEBHOOK_URL")

    url, fallback_title = get_todays_recipe(ical_url)
    extra = enrich_from_page(url)
    payload = build_payload(url, fallback_title, extra)

    resp = requests.post(webhook_url, json=payload, timeout=15)
    resp.raise_for_status()
    print("Verstuurd naar TRMNL:", payload)


if __name__ == "__main__":
    main()
