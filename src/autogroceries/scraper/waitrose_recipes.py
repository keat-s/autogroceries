from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Nutrition, Recipe
from autogroceries.scraper.base import RecipeScraper
from autogroceries.scraper.ingredient_parser import parse_ingredient

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.6 Safari/605.1.15"
    )
}


class WaitroseScraper(RecipeScraper):
    """Scraper for Waitrose recipes."""

    BASE_URL = "https://www.waitrose.com"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def scrape(self, url: str) -> Recipe:
        """Scrape a Waitrose recipe from its URL."""
        resp = self._session.get(url)
        if not resp.ok:
            raise RecipeScrapeError(
                f"Failed to fetch {url}: HTTP {resp.status_code}"
            )

        scraper = scrape_html(html=resp.text, org_url=url)

        title = scraper.title()
        ingredients = [parse_ingredient(i) for i in scraper.ingredients()]

        try:
            instructions = scraper.instructions_list()
        except Exception:
            instructions = [scraper.instructions()]

        servings_str = scraper.yields()
        servings = _parse_servings(servings_str)

        recipe_id = Recipe.make_id(title, "waitrose")

        nutrition = _extract_nutrition(scraper)

        return Recipe(
            id=recipe_id,
            title=title,
            source="waitrose",
            url=url,
            servings=servings,
            prep_time=_safe_int(scraper.prep_time),
            cook_time=_safe_int(scraper.cook_time),
            ingredients=ingredients,
            instructions=instructions,
            nutrition=nutrition,
        )

    def search(self, query: str) -> list[dict[str, str]]:
        """Search Waitrose for recipes matching a query."""
        resp = self._session.get(
            f"{self.BASE_URL}/ecom/shop/recipes",
            params={"query": query},
        )
        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[dict[str, str]] = []

        for link in soup.select("a[href*='/recipes/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or not href:
                continue
            url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            if url not in [r["url"] for r in results]:
                results.append({"title": title, "url": url})

        return results[:20]


def _extract_nutrition(scraper: object) -> Nutrition | None:
    """Extract nutrition data from a recipe-scrapers object."""
    try:
        nutrients = scraper.nutrients()  # type: ignore[attr-defined]
        if not nutrients:
            return None

        def _float(key: str) -> float | None:
            val = nutrients.get(key, "")
            if not val:
                return None
            m = re.search(r"[\d.]+", str(val))
            return float(m.group()) if m else None

        return Nutrition(
            calories=_float("calories"),
            protein_g=_float("proteinContent"),
            carbs_g=_float("carbohydrateContent"),
            fat_g=_float("fatContent"),
            fibre_g=_float("fiberContent"),
            sugar_g=_float("sugarContent"),
            salt_g=_float("sodiumContent"),
        )
    except Exception:
        return None


def _parse_servings(yields: str) -> int | None:
    if not yields:
        return None
    m = re.search(r"\d+", yields)
    return int(m.group()) if m else None


def _safe_int(method: object) -> int | None:
    try:
        val = method()  # type: ignore[operator]
        return int(val) if val else None
    except Exception:
        return None
