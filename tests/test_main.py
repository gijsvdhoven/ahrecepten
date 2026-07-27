import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import (
    MAX_INGREDIENTS,
    PAYLOAD_LIMIT_BYTES,
    build_payload,
    normalize_ical_url,
    parse_todays_recipe,
    payload_size,
)

TODAY = date(2026, 7, 27)
AH_URL = "https://www.ah.nl/allerhande/recept/R-R484610/pastasalade"


def _cal(*events: str) -> str:
    body = "".join(events)
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n" + body + "END:VCALENDAR\r\n"
    )


def _allday(summary, day="20260727", description=None, url=None, uid="1"):
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART;VALUE=DATE:{day}",
        f"SUMMARY:{summary}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if url:
        lines.append(f"URL:{url}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines) + "\r\n"


# --- het event van vandaag vinden ------------------------------------------


def test_finds_todays_allday_event():
    ical = _cal(_allday(f"Ik eet vandaag: Pastasalade {AH_URL}"))
    url, title = parse_todays_recipe(ical, today=TODAY)
    assert url == AH_URL
    assert title == "Pastasalade"


def test_ignores_events_on_other_days():
    ical = _cal(_allday(f"Ik eet vandaag: Gisteren {AH_URL}", day="20260726"))
    assert parse_todays_recipe(ical, today=TODAY) == (None, None)


def test_ignores_other_events_on_the_same_day():
    ical = _cal(
        _allday("Tandarts", uid="1"),
        _allday(f"Ik eet vandaag: Pastasalade {AH_URL}", uid="2"),
    )
    url, title = parse_todays_recipe(ical, today=TODAY)
    assert (url, title) == (AH_URL, "Pastasalade")


def test_handles_timed_event_with_timezone():
    ical = _cal(
        "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260727T180000Z\r\n"
        f"SUMMARY:Ik eet vandaag: Pastasalade {AH_URL}\r\nEND:VEVENT\r\n"
    )
    url, _ = parse_todays_recipe(ical, today=TODAY)
    assert url == AH_URL


def test_survives_vevent_without_dtstart():
    """Een VEVENT zonder DTSTART mag de hele run niet laten crashen."""
    ical = _cal(
        "BEGIN:VEVENT\r\nUID:1\r\nSUMMARY:kapot event\r\nEND:VEVENT\r\n",
        _allday(f"Ik eet vandaag: Pastasalade {AH_URL}", uid="2"),
    )
    url, _ = parse_todays_recipe(ical, today=TODAY)
    assert url == AH_URL


# --- de link terugvinden ---------------------------------------------------


def test_finds_url_in_description():
    ical = _cal(_allday("Ik eet vandaag: Pastasalade", description=AH_URL))
    url, title = parse_todays_recipe(ical, today=TODAY)
    assert url == AH_URL
    assert title == "Pastasalade"


def test_finds_url_in_url_property():
    ical = _cal(_allday("Ik eet vandaag: Pastasalade", url=AH_URL))
    assert parse_todays_recipe(ical, today=TODAY)[0] == AH_URL


def test_strips_trailing_punctuation_from_url():
    ical = _cal(_allday(f"Ik eet vandaag: Pastasalade ({AH_URL})"))
    assert parse_todays_recipe(ical, today=TODAY)[0] == AH_URL


def test_event_without_url_still_returns_title():
    ical = _cal(_allday("Ik eet vandaag: Boerenkool met worst"))
    url, title = parse_todays_recipe(ical, today=TODAY)
    assert url is None
    assert title == "Boerenkool met worst"


@pytest.mark.parametrize(
    "summary",
    [
        "ik eet vandaag: Pastasalade",
        "  Ik eet vandaag:Pastasalade",
        "IK EET VANDAAG: Pastasalade",
    ],
)
def test_prefix_matching_is_forgiving(summary):
    ical = _cal(_allday(summary))
    assert parse_todays_recipe(ical, today=TODAY)[1] == "Pastasalade"


# --- webcal:// -------------------------------------------------------------


def test_normalize_ical_url_rewrites_webcal():
    assert normalize_ical_url("webcal://p140-caldav.icloud.com/published/2/abc") == (
        "https://p140-caldav.icloud.com/published/2/abc"
    )


def test_normalize_ical_url_leaves_https_alone():
    assert normalize_ical_url("https://example.com/a.ics") == "https://example.com/a.ics"


# --- payload ---------------------------------------------------------------


def test_payload_prefers_scraped_title_and_stays_small():
    extra = {
        "title": "Pastasalade met tomaat en mozzarella",
        "image": "https://static.ah.nl/img.jpg",
        "servings": "4 personen",
        "prep_time": "20 min",
        "kcal": "560 kcal",
    }
    payload = build_payload(AH_URL, "Pastasalade", extra, today=TODAY)
    mv = payload["merge_variables"]

    assert mv["title"] == "Pastasalade met tomaat en mozzarella"
    assert mv["servings"] == "4 personen"
    assert mv["prep_time"] == "20 min"
    assert mv["date"] == "2026-07-27"

    import json

    assert len(json.dumps(payload)) < 2048, "TRMNL webhook accepteert max 2KB"


def test_payload_falls_back_to_calendar_title_then_placeholder():
    assert build_payload(AH_URL, "Pastasalade", {}, today=TODAY)["merge_variables"][
        "title"
    ] == "Pastasalade"
    assert build_payload(None, None, {}, today=TODAY)["merge_variables"]["title"] == (
        "Geen recept gevonden voor vandaag"
    )


def test_payload_uses_total_time_when_prep_time_missing():
    extra = {"title": "X", "total_time": "40 min"}
    payload = build_payload(AH_URL, None, extra, today=TODAY)
    assert payload["merge_variables"]["prep_time"] == "40 min"


# --- ingrediënten in de payload -------------------------------------------


def test_payload_includes_ingredients():
    extra = {"title": "X", "ingredients": ["250 g schelpenpasta", "4 tomaten"]}
    mv = build_payload(AH_URL, None, extra, today=TODAY)["merge_variables"]
    assert mv["ingredients"] == ["250 g schelpenpasta", "4 tomaten"]


def test_ingredients_key_always_present_for_liquid():
    """Het template loopt over `ingredients`; die moet altijd bestaan."""
    assert build_payload(None, None, {}, today=TODAY)["merge_variables"][
        "ingredients"
    ] == []


def test_ingredients_are_capped():
    extra = {"title": "X", "ingredients": [f"ingredient {i}" for i in range(40)]}
    mv = build_payload(AH_URL, None, extra, today=TODAY)["merge_variables"]
    assert len(mv["ingredients"]) <= MAX_INGREDIENTS


def test_payload_stays_under_2kb_with_absurd_ingredients():
    """Een extreem lange lijst mag de webhook niet over de 2KB duwen."""
    extra = {
        "title": "Zeer uitgebreide stoofpot met heel veel ingrediënten",
        "image": "https://static.ah.nl/" + "x" * 180 + ".jpg",
        "servings": "6 personen",
        "prep_time": "2 u 30 min",
        "kcal": "890 kcal",
        "ingredients": [f"{i} gram van een ingrediënt met een lange naam" for i in range(40)],
    }
    payload = build_payload(AH_URL, None, extra, today=TODAY)
    assert payload_size(payload) <= PAYLOAD_LIMIT_BYTES
    # de rest van de velden mag niet gesneuveld zijn
    assert payload["merge_variables"]["title"].startswith("Zeer uitgebreide")
    assert payload["merge_variables"]["kcal"] == "890 kcal"


def test_payload_size_counts_utf8_bytes():
    """é is twee bytes; een naïeve len() zou de limiet onderschatten."""
    assert payload_size({"a": "é"}) > len(str({"a": "é"})) - 4


def test_realistic_recipe_payload_is_comfortably_small():
    extra = {
        "title": "Pastasalade met tomaat en mozzarella",
        "image": "https://static.ah.nl/static/recepten/img_R-R484610_1024x1024.jpg",
        "servings": "4 personen",
        "prep_time": "20 min",
        "kcal": "560 kcal",
        "ingredients": [
            "250 g schelpenpasta",
            "1 knoflookteen",
            "30 g verse basilicum",
            "2 el citroensap",
            "5 el extra vierge olijfolie",
            "2 el water",
            "3 lente-uitjes",
            "4 tomaten",
            "250 g mini-mozzarellabolletjes",
        ],
    }
    payload = build_payload(AH_URL, None, extra, today=TODAY)
    assert len(payload["merge_variables"]["ingredients"]) == 9
    assert payload_size(payload) < 1024


def test_importing_main_does_not_require_env_vars(monkeypatch):
    """main.py moet importeerbaar zijn zonder ICAL_URL/TRMNL_WEBHOOK_URL."""
    monkeypatch.delenv("ICAL_URL", raising=False)
    monkeypatch.delenv("TRMNL_WEBHOOK_URL", raising=False)
    import importlib

    import main

    importlib.reload(main)  # mag geen KeyError geven
