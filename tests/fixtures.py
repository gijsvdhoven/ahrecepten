"""Testfixtures voor de AH-receptparser.

De JSON-LD hieronder is gemodelleerd op een echte Allerhande-receptpagina
(R-R484610, "Pastasalade met tomaat en mozzarella"). De veldwaarden komen
overeen met wat die pagina toont: 4 porties, 20 min bereidingstijd, 560 kcal,
9 ingredienten en 4 bereidingsstappen.

Twee vormdetails zijn met opzet zo gemodelleerd, omdat ze bij AH echt zo
voorkomen en de parser er eerder op stuk liep:

* `recipeInstructions` bestaat uit HowToStep-objecten met `name` = "Stap 1"
  en de echte tekst in `text`. De AH-scraper in de recipe-scrapers-library
  filtert daarom expliciet regels weg die met "stap" beginnen.
* de Recipe zit in een `@graph`, samen met niet-Recipe nodes.
"""

import json

AH_INGREDIENTS = [
    "250 g schelpenpasta",
    "1 knoflookteen",
    "30 g verse basilicum",
    "2 el citroensap",
    "5 el extra vierge olijfolie",
    "2 el water",
    "3 lente-uitjes",
    "4 tomaten",
    "250 g mini-mozzarellabolletjes",
]

AH_STEPS = [
    "Kook de pasta volgens de aanwijzingen op de verpakking.",
    "Pureer de helft van de basilicum met de knoflook, het citroensap, de "
    "olijfolie en het water tot een dressing. Breng op smaak met peper en zout.",
    "Giet de pasta af en meng direct in een schaal met de dressing. Laat "
    "minimaal 20 min afkoelen.",
    "Scheur de rest van de basilicum in stukjes. Meng vlak voor het serveren "
    "de lente-ui, de tomaat, de mozzarella en de basilicum door de salade.",
]

_RECIPE_NODE = {
    "@type": "Recipe",
    "name": "Pastasalade met tomaat en mozzarella",
    "description": "Een frisse pastasalade met tomaat, mozzarella en basilicum.",
    "image": [
        {
            "@type": "ImageObject",
            "url": "https://static.ah.nl/static/recepten/img_R-R484610_1024x1024.jpg",
        }
    ],
    "recipeYield": ["4 personen"],
    "prepTime": "PT20M",
    "cookTime": "PT0M",
    "totalTime": "PT40M",
    "recipeIngredient": AH_INGREDIENTS,
    "recipeInstructions": [
        {"@type": "HowToStep", "name": f"Stap {i + 1}", "text": text}
        for i, text in enumerate(AH_STEPS)
    ],
    "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "4.2",
        "ratingCount": "127",
    },
    "nutrition": {"@type": "NutritionInformation", "calories": "560 kcal"},
}


def _page(*blocks: str, og: bool = True) -> str:
    og_tags = ""
    if og:
        og_tags = (
            '<meta property="og:title" content="Pastasalade met tomaat en mozzarella | Albert Heijn">'
            '<meta property="og:image" content="https://static.ah.nl/static/recepten/og_R-R484610.jpg">'
            '<meta property="og:description" content="Een frisse pastasalade.">'
        )
    return f"<html><head>{og_tags}{''.join(blocks)}</head><body></body></html>"


def _ld(payload) -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(payload, ensure_ascii=False)
        + "</script>"
    )


def ah_page() -> str:
    """Realistische AH-pagina: Recipe binnen een @graph."""
    return _page(
        _ld(
            {
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "WebSite", "name": "Albert Heijn"},
                    {"@type": "BreadcrumbList", "itemListElement": []},
                    _RECIPE_NODE,
                ],
            }
        )
    )


def ah_page_toplevel_recipe() -> str:
    """Recipe als los top-level object (geen @graph)."""
    return _page(_ld({"@context": "https://schema.org", **_RECIPE_NODE}))


def ah_page_list_payload() -> str:
    """JSON-LD waarvan de payload zelf een lijst is."""
    return _page(_ld([{"@type": "WebPage"}, _RECIPE_NODE]))


def ah_page_nested_graph() -> str:
    """Recipe in een @graph binnen een @graph."""
    return _page(
        _ld(
            {
                "@context": "https://schema.org",
                "@graph": [{"@graph": [_RECIPE_NODE]}],
            }
        )
    )


def ah_page_howto_sections() -> str:
    """recipeInstructions als HowToSection-wrappers om de losse stappen."""
    node = dict(_RECIPE_NODE)
    node["recipeInstructions"] = [
        {
            "@type": "HowToSection",
            "name": "Bereiden",
            "itemListElement": [
                {"@type": "HowToStep", "name": f"Stap {i + 1}", "text": text}
                for i, text in enumerate(AH_STEPS)
            ],
        }
    ]
    return _page(_ld({"@context": "https://schema.org", "@graph": [node]}))


def ah_page_raw_newlines() -> str:
    """JSON-LD met een letterlijke newline in een string.

    Dat is strikt genomen ongeldige JSON, maar het komt in het wild voor in
    door templates gegenereerde JSON-LD. `json.loads` weigert dit standaard.
    """
    body = json.dumps({"@context": "https://schema.org", "@graph": [_RECIPE_NODE]},
                      ensure_ascii=False)
    body = body.replace("Een frisse pastasalade", "Een frisse\npastasalade", 1)
    return _page(f'<script type="application/ld+json">{body}</script>')


def ah_page_script_with_comment() -> str:
    """JSON-LD-script met een HTML-commentaar ernaast in dezelfde tag.

    Hierdoor heeft de script-tag meerdere child nodes en geeft
    BeautifulSoup's `.string` None terug.
    """
    body = json.dumps({"@context": "https://schema.org", "@graph": [_RECIPE_NODE]},
                      ensure_ascii=False)
    return _page(
        f'<script type="application/ld+json"><!-- ld+json -->{body}</script>'
    )


def ah_page_og_only() -> str:
    """Geen (bruikbare) JSON-LD, alleen og:-tags."""
    return _page(_ld({"@context": "https://schema.org", "@type": "WebPage"}))


def ah_page_no_metadata() -> str:
    """Niets bruikbaars op de pagina."""
    return _page(og=False)
