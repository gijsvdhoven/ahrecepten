"""Rendert de Liquid-templates zodat een typefout er niet pas op het display uitkomt.

Vereist `python-liquid`; zonder dat pakket worden deze tests overgeslagen.
TRMNL gebruikt de Ruby-implementatie van Liquid, dus dit dekt de syntax en de
logica -- niet de opmaak. Voor de opmaak is de live previewer in TRMNL de test.
"""

import os
import sys
from datetime import date

import pytest

liquid = pytest.importorskip("liquid", reason="python-liquid niet geinstalleerd")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import build_payload

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = [
    "trmnl-full.liquid",
    "trmnl-half-horizontal.liquid",
    "trmnl-half-vertical.liquid",
    "trmnl-quadrant.liquid",
]

FULL_RECIPE = {
    "title": "Pastasalade met tomaat en mozzarella",
    "image": "https://static.ah.nl/static/recepten/img_R-R484610.jpg",
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


def render(template_name, extra):
    env = liquid.Environment()
    with open(os.path.join(ROOT, template_name), encoding="utf-8") as fh:
        template = env.from_string(fh.read())
    mv = build_payload(
        "https://www.ah.nl/allerhande/recept/R-R484610/pastasalade",
        None,
        extra,
        today=date(2026, 7, 27),
    )["merge_variables"]
    return template.render(**mv)


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_renders(name):
    out = render(name, FULL_RECIPE)
    assert "Pastasalade met tomaat en mozzarella" in out
    # layout en title_bar moeten broers zijn, geen genest paar
    assert '<div class="layout">' in out
    assert '<div class="title_bar">' in out
    assert "27-07-2026" in out


@pytest.mark.parametrize("name", TEMPLATES)
def test_template_renders_without_any_data(name):
    """"Geen recept vandaag" mag geen kapotte markup of losse scheidingstekens geven."""
    out = render(name, {})
    assert "Geen recept gevonden voor vandaag" in out
    assert "·" not in out
    assert "None" not in out


@pytest.mark.parametrize("name", TEMPLATES)
def test_no_image_tag_when_there_is_no_image(name):
    out = render(name, {"title": "Boerenkool met worst", "servings": "4 personen"})
    assert "image-dither" not in out


def test_full_layout_splits_ingredients_over_two_columns():
    out = render("trmnl-full.liquid", FULL_RECIPE)
    first, second = out.split('<div class="column">')[-2:]
    # 9 ingredienten -> 5 links, 4 rechts
    assert first.count('class="description"') == 5
    assert second.count('class="description"') == 4
    assert "250 g schelpenpasta" in first
    assert "250 g mini-mozzarellabolletjes" in second


def test_full_layout_splits_odd_count_without_losing_an_ingredient():
    extra = {"title": "X", "ingredients": [f"ingredient {i}" for i in range(1, 8)]}
    out = render("trmnl-full.liquid", extra)
    for i in range(1, 8):
        assert f"ingredient {i}" in out


def test_meta_line_has_no_leading_separator_when_servings_missing():
    out = render("trmnl-full.liquid", {"title": "X", "kcal": "560 kcal"})
    assert "560 kcal" in out
    assert ">·" not in out.replace(" ", "")


def test_quadrant_omits_ingredients_and_image():
    out = render("trmnl-quadrant.liquid", FULL_RECIPE)
    assert "Ingrediënten" not in out
    assert "image-dither" not in out
    assert "4 personen · 20 min · 560 kcal" in out
