import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ah_scraper
from ah_scraper import format_duration, scrape_recipe
from tests import fixtures


class _FakeResponse:
    def __init__(self, text, url):
        self.text = text
        self.url = url

    def raise_for_status(self):
        pass


@pytest.fixture
def fetch(monkeypatch):
    """Laat scrape_recipe een vaste HTML-string teruggeven i.p.v. te netwerken."""

    def _fetch(html, url="https://www.ah.nl/allerhande/recept/R-R484610/pastasalade"):
        def fake_get(_url, **_kwargs):
            return _FakeResponse(html, url)

        monkeypatch.setattr(ah_scraper.requests, "get", fake_get)
        return scrape_recipe("https://www.ah.nl/r/R-R484610")

    return _fetch


# --- velden uit realistische AH JSON-LD -------------------------------------


def test_extracts_all_core_fields(fetch):
    data = fetch(fixtures.ah_page())

    assert data["title"] == "Pastasalade met tomaat en mozzarella"
    assert data["image"] == (
        "https://static.ah.nl/static/recepten/img_R-R484610_1024x1024.jpg"
    )
    assert data["ingredients"] == fixtures.AH_INGREDIENTS
    assert data["rating"] == "4.2"
    assert data["rating_count"] == "127"
    assert data["kcal"] == "560 kcal"


def test_servings_is_a_string_not_a_list(fetch):
    """recipeYield is bij AH een lijst; TRMNL moet een string krijgen."""
    data = fetch(fixtures.ah_page())
    assert data["servings"] == "4 personen"


def test_durations_are_human_readable(fetch):
    """ISO-8601 duur (PT20M) is onleesbaar op een TRMNL-display."""
    data = fetch(fixtures.ah_page())
    assert data["prep_time"] == "20 min"
    assert data["total_time"] == "40 min"


def test_steps_drop_the_stap_n_labels(fetch):
    """AH zet 'Stap 1' in `name`; alleen `text` is de echte instructie."""
    data = fetch(fixtures.ah_page())
    assert data["steps"] == fixtures.AH_STEPS
    assert not any(s.lower().startswith("stap") for s in data["steps"])


def test_source_url_is_the_url_after_redirect(fetch):
    final = "https://www.ah.nl/allerhande/recept/R-R484610/pastasalade"
    data = fetch(fixtures.ah_page(), url=final)
    assert data["source_url"] == final


# --- verschillende JSON-LD verpakkingen ------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(fixtures.ah_page(), id="graph"),
        pytest.param(fixtures.ah_page_toplevel_recipe(), id="top-level"),
        pytest.param(fixtures.ah_page_list_payload(), id="list-payload"),
        pytest.param(fixtures.ah_page_nested_graph(), id="nested-graph"),
    ],
)
def test_finds_recipe_in_any_json_ld_shape(fetch, html):
    data = fetch(html)
    assert data["title"] == "Pastasalade met tomaat en mozzarella"
    assert len(data["ingredients"]) == 9


def test_handles_howto_section_wrappers(fetch):
    """Stappen mogen niet verdwijnen als AH ze in een HowToSection stopt."""
    data = fetch(fixtures.ah_page_howto_sections())
    assert data["steps"] == fixtures.AH_STEPS


# --- robuustheid tegen kapotte / rommelige JSON-LD -------------------------


def test_survives_literal_newline_in_json_ld(fetch):
    """Een letterlijke newline mag niet de hele JSON-LD onbruikbaar maken."""
    data = fetch(fixtures.ah_page_raw_newlines())
    assert data["title"] == "Pastasalade met tomaat en mozzarella"
    assert len(data["ingredients"]) == 9


def test_survives_comment_inside_json_ld_script(fetch):
    """`.string` is None bij meerdere child nodes; parser moet doorgaan."""
    data = fetch(fixtures.ah_page_script_with_comment())
    assert data["title"] == "Pastasalade met tomaat en mozzarella"
    assert len(data["ingredients"]) == 9


# --- fallbacks -------------------------------------------------------------


def test_falls_back_to_og_tags(fetch):
    data = fetch(fixtures.ah_page_og_only())
    assert data["title"] == "Pastasalade met tomaat en mozzarella | Albert Heijn"
    assert data["image"] == "https://static.ah.nl/static/recepten/og_R-R484610.jpg"
    assert data["ingredients"] == []
    assert data["steps"] == []


def test_returns_empty_shape_when_page_has_nothing(fetch):
    """Alle sleutels moeten bestaan, zodat main.py niet hoeft te raden."""
    data = fetch(fixtures.ah_page_no_metadata())
    for key in (
        "title",
        "image",
        "description",
        "servings",
        "prep_time",
        "total_time",
        "kcal",
        "rating",
    ):
        assert key in data, key
        assert data[key] is None, key
    assert data["ingredients"] == []
    assert data["steps"] == []


# --- duurformattering ------------------------------------------------------


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("PT20M", "20 min"),
        ("PT0M", None),
        ("PT1H", "1 u"),
        ("PT1H15M", "1 u 15 min"),
        ("PT2H0M", "2 u"),
        ("P0D", None),
        (None, None),
        ("", None),
        ("20 min", "20 min"),
        ("niet-iso", "niet-iso"),
    ],
)
def test_format_duration(iso, expected):
    assert format_duration(iso) == expected
