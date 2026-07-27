"""
Scraper voor Albert Heijn (Allerhande) receptpagina's.

Strategie:
1. Primair: JSON-LD structured data (schema.org/Recipe). Dit is wat AH
   waarschijnlijk toch al levert t.b.v. Google Recipe rich results, en is
   veel stabieler dan scrapen op CSS-classes die zonder aankondiging kunnen
   wijzigen.
2. Fallback: og:title / og:image / og:description meta tags, voor het geval
   er geen (bruikbare) JSON-LD aanwezig is. Dit levert alleen titel/afbeelding
   op, geen ingrediënten/stappen.

Let op: ik heb dit kunnen valideren tegen de zichtbare tekst van een AH-
receptpagina, maar niet tegen de ruwe HTML/JSON-LD zelf (die kon ik vanuit
mijn omgeving niet ophalen). Test dit dus even tegen een echte AH-receptlink
voordat je erop vertrouwt -- zie het `if __name__ == "__main__"` blok onderin.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TRMNL-AH-bot/1.0)"}


def scrape_recipe(url: str) -> dict:
    resp = requests.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = _from_json_ld(soup) or {}

    if not data.get("title") or not data.get("image"):
        og = _from_og_tags(soup)
        data["title"] = data.get("title") or og.get("title")
        data["image"] = data.get("image") or og.get("image")
        data["description"] = data.get("description") or og.get("description")

    data["source_url"] = resp.url  # uiteindelijke URL na de ah.nl/r/... redirect
    return data


def _from_json_ld(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue

        candidates = payload if isinstance(payload, list) else [payload]
        for item in list(candidates):
            if isinstance(item, dict) and "@graph" in item:
                candidates.extend(item["@graph"])

        for item in candidates:
            recipe = _parse_recipe_node(item)
            if recipe:
                return recipe
    return None


def _parse_recipe_node(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    types = item.get("@type")
    types = types if isinstance(types, list) else [types]
    if "Recipe" not in types:
        return None

    image = item.get("image")
    if isinstance(image, dict):
        image = image.get("url")
    elif isinstance(image, list) and image:
        image = image[0].get("url") if isinstance(image[0], dict) else image[0]

    steps = []
    for step in item.get("recipeInstructions") or []:
        if isinstance(step, dict):
            text = step.get("text") or step.get("name")
            if text:
                steps.append(text)
        elif isinstance(step, str):
            steps.append(step)

    rating = item.get("aggregateRating") or {}
    nutrition = item.get("nutrition") or {}

    return {
        "title": item.get("name"),
        "description": item.get("description"),
        "image": image,
        "servings": item.get("recipeYield"),
        "prep_time": item.get("prepTime"),
        "cook_time": item.get("cookTime"),
        "total_time": item.get("totalTime"),
        "ingredients": item.get("recipeIngredient") or [],
        "steps": steps,
        "rating": rating.get("ratingValue"),
        "rating_count": rating.get("ratingCount"),
        "kcal": nutrition.get("calories"),
    }


def _from_og_tags(soup: BeautifulSoup) -> dict:
    def content(prop):
        tag = soup.find("meta", property=prop)
        return tag["content"] if tag and tag.get("content") else None

    return {
        "title": content("og:title"),
        "image": content("og:image"),
        "description": content("og:description"),
    }


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.ah.nl/allerhande/recept/R-R484610/pastasalade-met-tomaat-en-mozzarella"
    result = scrape_recipe(url)
    print(json.dumps(result, indent=2, ensure_ascii=False))
