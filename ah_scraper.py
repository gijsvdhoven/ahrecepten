"""
Scraper voor Albert Heijn (Allerhande) receptpagina's.

Strategie:
1. Primair: JSON-LD structured data (schema.org/Recipe). AH levert dit t.b.v.
   Google Recipe rich results, en het is veel stabieler dan scrapen op
   CSS-classes die zonder aankondiging kunnen wijzigen.
2. Fallback: og:title / og:image / og:description meta tags, voor het geval
   er geen (bruikbare) JSON-LD aanwezig is. Dit levert alleen titel/afbeelding
   op, geen ingrediënten/stappen.

`scrape_recipe` geeft altijd dezelfde sleutels terug (zie `_empty_recipe`),
zodat de aanroeper niet hoeft te controleren of een veld bestaat.

Over de AH-specifieke vorm van de JSON-LD:
* `recipeYield` is een lijst (`["4 personen"]`), geen string.
* `prepTime`/`cookTime`/`totalTime` zijn ISO-8601 duren (`"PT20M"`), die
  onleesbaar zijn op een display; `format_duration` maakt er "20 min" van.
* `recipeInstructions` bestaat uit HowToStep-objecten waarvan `name` een
  label is ("Stap 1") en `text` de echte instructie. We nemen alleen `text`.
* de Recipe-node zit doorgaans in een `@graph`, soms genest.
"""

import json
import re

import requests
from bs4 import BeautifulSoup, Comment, NavigableString

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TRMNL-AH-bot/1.0)"}

_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>[\d.]+)S)?)?$"
)


def _empty_recipe() -> dict:
    return {
        "title": None,
        "description": None,
        "image": None,
        "servings": None,
        "prep_time": None,
        "cook_time": None,
        "total_time": None,
        "ingredients": [],
        "steps": [],
        "rating": None,
        "rating_count": None,
        "kcal": None,
    }


def format_duration(value):
    """Maak van een ISO-8601 duur ("PT1H15M") een leesbare string ("1 u 15 min").

    Een duur van nul levert None op: "0 min" op een display is ruis. Waarden
    die geen ISO-duur zijn worden ongewijzigd doorgegeven, zodat we niets
    kapotmaken als AH ooit gewoon "20 min" in de JSON-LD zet.
    """
    if not value or not isinstance(value, str):
        return None

    value = value.strip()
    if not value:
        return None

    match = _ISO_DURATION.match(value)
    if not match:
        return value

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)

    total_minutes = days * 24 * 60 + hours * 60 + minutes + int(seconds // 60)
    if total_minutes <= 0:
        return None

    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} u {minutes} min"
    if hours:
        return f"{hours} u"
    return f"{minutes} min"


def scrape_recipe(url: str) -> dict:
    resp = requests.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = _empty_recipe()
    data.update(_from_json_ld(soup) or {})

    if not data.get("title") or not data.get("image"):
        og = _from_og_tags(soup)
        data["title"] = data.get("title") or og.get("title")
        data["image"] = data.get("image") or og.get("image")
        data["description"] = data.get("description") or og.get("description")

    data["source_url"] = resp.url  # uiteindelijke URL na de ah.nl/r/... redirect
    return data


def _script_json(script):
    """Parse de inhoud van een <script type="application/ld+json">.

    Twee dingen die in het wild stukgaan en die we hier opvangen:
    * `script.string` is None zodra de tag meer dan één tekstnode bevat
      (bijvoorbeeld een HTML-commentaar), dus we plakken de tekstnodes zelf
      aan elkaar en slaan commentaren over.
    * door templates gegenereerde JSON-LD bevat soms letterlijke newlines in
      strings. Dat is strikt genomen ongeldig, maar `strict=False` accepteert
      het en dat is beter dan de hele node weggooien.
    """
    raw = "".join(
        str(child)
        for child in script.contents
        if isinstance(child, NavigableString) and not isinstance(child, Comment)
    ).strip()

    # Binnen een <script> ziet html.parser een HTML-commentaar niet als
    # commentaar maar als gewone tekst, dus die wrappers pellen we zelf af.
    for prefix, suffix in (("<!--", "-->"), ("<![CDATA[", "]]>")):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :].removesuffix(suffix).removesuffix("//").strip()

    if not raw:
        return None

    try:
        return json.loads(raw, strict=False)
    except ValueError:
        pass

    # Laatste redmiddel: snijd het buitenste object/array eruit, voor het geval
    # er nog wat omheen staat dat geen JSON is.
    start = min((i for i in (raw.find("{"), raw.find("[")) if i != -1), default=-1)
    end = max(raw.rfind("}"), raw.rfind("]"))
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1], strict=False)
    except ValueError:
        return None


def _iter_nodes(payload):
    """Loop recursief door een JSON-LD payload heen, inclusief @graph-nesting."""
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_nodes(item)
    elif isinstance(payload, dict):
        yield payload
        graph = payload.get("@graph")
        if graph is not None:
            yield from _iter_nodes(graph)


def _from_json_ld(soup: BeautifulSoup):
    for script in soup.find_all("script", type="application/ld+json"):
        payload = _script_json(script)
        if payload is None:
            continue

        for node in _iter_nodes(payload):
            recipe = _parse_recipe_node(node)
            if recipe:
                return recipe
    return None


def _first_text(value):
    """Pak één string uit een waarde die string, getal of lijst kan zijn.

    Bij een lijst krijgt een omschrijvende waarde ("4 personen") voorrang op
    een kale ("4"), want die leest beter op het display.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _first_text(value.get("value") or value.get("name"))
    if isinstance(value, list):
        texts = [t for t in (_first_text(v) for v in value) if t]
        if not texts:
            return None
        for text in texts:
            if re.search(r"[a-zA-Z]", text):
                return text
        return texts[0]
    return None


def _image_url(value):
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _image_url(value.get("url") or value.get("contentUrl"))
    if isinstance(value, list):
        for item in value:
            url = _image_url(item)
            if url:
                return url
    return None


def _steps(value) -> list:
    """Vlak recipeInstructions uit naar een lijst instructieteksten.

    HowToSection-wrappers worden doorgelopen i.p.v. als enkele stap geteld;
    anders zou "Bereiden" de vier echte stappen vervangen. Bij een HowToStep
    heeft `text` voorrang op `name`, omdat `name` bij AH het label "Stap 1" is.
    """
    steps = []

    def walk(item):
        if isinstance(item, str):
            text = item.strip()
            if text:
                steps.append(text)
            return
        if isinstance(item, list):  # sommige sites nesten lijsten
            for sub in item:
                walk(sub)
            return
        if not isinstance(item, dict):
            return

        children = item.get("itemListElement")
        if children is not None:
            walk(children if not isinstance(children, dict) else [children])
            return

        text = item.get("text") or item.get("name")
        if isinstance(text, str) and text.strip():
            steps.append(text.strip())

    if isinstance(value, dict):
        value = value.get("itemListElement") or []
    walk(value or [])

    return steps


def _ingredients(value) -> list:
    if isinstance(value, str):
        value = [value]
    out = []
    for item in value or []:
        text = _first_text(item)
        if text:
            out.append(text)
    return out


def _parse_recipe_node(item):
    if not isinstance(item, dict):
        return None
    types = item.get("@type")
    types = types if isinstance(types, list) else [types]
    if "Recipe" not in types:
        return None

    rating = item.get("aggregateRating")
    nutrition = item.get("nutrition")
    rating = rating if isinstance(rating, dict) else {}
    nutrition = nutrition if isinstance(nutrition, dict) else {}

    return {
        "title": _first_text(item.get("name")),
        "description": _first_text(item.get("description")),
        "image": _image_url(item.get("image")),
        "servings": _first_text(item.get("recipeYield")),
        "prep_time": format_duration(item.get("prepTime")),
        "cook_time": format_duration(item.get("cookTime")),
        "total_time": format_duration(item.get("totalTime")),
        "ingredients": _ingredients(item.get("recipeIngredient")),
        "steps": _steps(item.get("recipeInstructions")),
        "rating": rating.get("ratingValue"),
        "rating_count": rating.get("ratingCount"),
        "kcal": _first_text(nutrition.get("calories")),
    }


def _from_og_tags(soup: BeautifulSoup) -> dict:
    def content(prop):
        tag = soup.find("meta", property=prop) or soup.find(
            "meta", attrs={"name": prop}
        )
        return tag["content"].strip() if tag and tag.get("content") else None

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
