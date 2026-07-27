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
    "steps": [
        "Kook de pasta volgens de aanwijzingen op de verpakking.",
        "Pureer de helft van de basilicum met de knoflook, het citroensap, de "
        "olijfolie en het water tot een dressing.",
        "Giet de pasta af en meng direct in een schaal met de dressing.",
        "Scheur de rest van de basilicum in stukjes en meng er vlak voor het "
        "serveren de lente-ui, tomaat en mozzarella door.",
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


def test_full_layout_shows_every_ingredient_and_step():
    out = render("trmnl-full.liquid", FULL_RECIPE)
    for ingredient in FULL_RECIPE["ingredients"]:
        assert ingredient in out
    for step in FULL_RECIPE["steps"]:
        assert step in out


def test_full_layout_numbers_the_steps():
    out = render("trmnl-full.liquid", FULL_RECIPE)
    for n in range(1, 5):
        assert f'<span class="index">{n}</span>' in out


def test_full_layout_keeps_the_recipe_photo():
    out = render("trmnl-full.liquid", FULL_RECIPE)
    assert FULL_RECIPE["image"] in out
    assert "image-dither" in out


def test_steps_block_disappears_when_there_are_no_steps():
    out = render("trmnl-full.liquid", {"title": "X", "ingredients": ["1 ui"]})
    assert "Bereiding" not in out
    assert "Ingrediënten" in out


def test_ingredients_block_disappears_when_there_are_none():
    out = render("trmnl-full.liquid", {"title": "X", "steps": ["Kook de pasta."]})
    assert "Ingrediënten" not in out
    assert "Bereiding" in out


def test_meta_line_has_no_leading_separator_when_servings_missing():
    out = render("trmnl-full.liquid", {"title": "X", "kcal": "560 kcal"})
    assert "560 kcal" in out
    assert ">·" not in out.replace(" ", "")


def test_quadrant_omits_ingredients_steps_and_image():
    out = render("trmnl-quadrant.liquid", FULL_RECIPE)
    assert "Ingrediënten" not in out
    assert "Bereiding" not in out
    assert "image-dither" not in out
    assert "4 personen · 20 min · 560 kcal" in out


def test_half_vertical_limits_ingredients_and_steps():
    out = render("trmnl-half-vertical.liquid", FULL_RECIPE)
    assert out.count('class="description"') <= 5 + 3
    assert '<span class="index">3</span>' in out
    assert '<span class="index">4</span>' not in out


def test_half_horizontal_is_a_summary_only():
    out = render("trmnl-half-horizontal.liquid", FULL_RECIPE)
    assert "Bereiding" not in out
    assert "Ingrediënten" not in out
    assert FULL_RECIPE["image"] in out
