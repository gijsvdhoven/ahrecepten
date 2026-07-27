import os
import re
import sys
import requests
from datetime import date
from icalendar import Calendar

from ah_scraper import scrape_recipe

ICAL_URL = os.environ["ICAL_URL"]
WEBHOOK_URL = os.environ["TRMNL_WEBHOOK_URL"]

PREFIX = "Ik eet vandaag:"


def get_todays_recipe():
    """Haal de iCal-feed op en zoek het (all-day of getimede) event van vandaag."""
    resp = requests.get(ICAL_URL, timeout=15)
    resp.raise_for_status()
    cal = Calendar.from_ical(resp.text)
    today = date.today()

    for component in cal.walk("VEVENT"):
        start = component.get("dtstart").dt
        # All-day events geven een `date`, getimede events een `datetime`
        start_date = start.date() if hasattr(start, "date") else start
        summary = str(component.get("summary", ""))

        if start_date != today:
            continue

        # Extra veiligheid: als de agenda ooit meer dan 1 event/dag bevat,
        # pak alleen het "Ik eet vandaag: ..." event.
        if not summary.startswith(PREFIX):
            continue

        match = re.search(r"https?://\S+", summary)
        url = match.group(0) if match else None

        title = summary
        if title.startswith(PREFIX):
            title = title[len(PREFIX):]
        if url:
            title = title.replace(url, "")
        title = title.strip(" :")

        return url, title

    return None, None


def enrich_from_page(url):
    """Scrape de AH-receptpagina voor titel/afbeelding/tijd/porties (best effort)."""
    if not url:
        return {}
    try:
        return scrape_recipe(url)
    except Exception as e:
        print(f"Kon receptpagina niet scrapen ({url}): {e}", file=sys.stderr)
        return {}


def main():
    url, fallback_title = get_todays_recipe()
    extra = enrich_from_page(url)

    # Webhook payload mag max. 2KB zijn, dus we sturen alleen een compacte
    # selectie door. `extra` (ah_scraper output) bevat meer (ingrediënten,
    # stappen, rating) mocht je die ooit ergens anders willen gebruiken.
    payload = {
        "merge_variables": {
            "title": extra.get("title") or fallback_title or "Geen recept gevonden voor vandaag",
            "url": url,
            "image": extra.get("image"),
            "servings": extra.get("servings"),
            "prep_time": extra.get("prep_time"),
            "kcal": extra.get("kcal"),
            "date": date.today().isoformat(),
        }
    }

    resp = requests.post(WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    print("Verstuurd naar TRMNL:", payload)


if __name__ == "__main__":
    main()
