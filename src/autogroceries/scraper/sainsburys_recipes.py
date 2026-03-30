from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup, Tag

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Recipe
from autogroceries.scraper.base import RecipeScraper
from autogroceries.scraper.ingredient_parser import parse_ingredient

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.6 Safari/605.1.15"
    )
}


class SainsburysScraper(RecipeScraper):
    """Custom scraper for Sainsbury's recipes (not supported by recipe-scrapers)."""

    BASE_URL = "https://recipes.sainsburys.co.uk"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def scrape(self, url: str) -> Recipe:
        """Scrape a Sainsbury's recipe from its URL."""
        resp = self._session.get(url)
        if not resp.ok:
            raise RecipeScrapeError(
                f"Failed to fetch {url}: HTTP {resp.status_code}"
            )

        soup = BeautifulSoup(resp.text, "html.parser")

        # Try JSON-LD structured data first
        recipe_data = self._extract_json_ld(soup)
        if recipe_data:
            return self._from_json_ld(recipe_data, url)

        # Fallback to HTML parsing
        return self._from_html(soup, url)

    def _extract_json_ld(self, soup: BeautifulSoup) -> dict | None:  # type: ignore[type-arg]
        """Extract Recipe JSON-LD structured data if present."""
        import json

        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Recipe":
                            return item  # type: ignore[no-any-return]
                elif isinstance(data, dict):
                    if data.get("@type") == "Recipe":
                        return data
            except json.JSONDecodeError:
                continue
        return None

    def _from_json_ld(self, data: dict, url: str) -> Recipe:  # type: ignore[type-arg]
        """Build a Recipe from JSON-LD data."""
        title = data.get("name", "Unknown")
        raw_ingredients = data.get("recipeIngredient", [])
        ingredients = [parse_ingredient(i) for i in raw_ingredients]

        instructions_data = data.get("recipeInstructions", [])
        instructions: list[str] = []
        for item in instructions_data:
            if isinstance(item, str):
                instructions.append(item)
            elif isinstance(item, dict):
                instructions.append(item.get("text", ""))

        servings = _parse_servings(str(data.get("recipeYield", "")))
        prep_time = _parse_iso_duration(data.get("prepTime"))
        cook_time = _parse_iso_duration(data.get("cookTime"))

        recipe_id = Recipe.make_id(title, "sainsburys")

        return Recipe(
            id=recipe_id,
            title=title,
            source="sainsburys",
            url=url,
            servings=servings,
            prep_time=prep_time,
            cook_time=cook_time,
            ingredients=ingredients,
            instructions=instructions,
        )

    def _from_html(self, soup: BeautifulSoup, url: str) -> Recipe:
        """Fallback HTML-based extraction."""
        # Title
        title_el = soup.select_one(
            "h1, .recipe-title, [class*='title'], [data-testid='recipe-title']"
        )
        title = title_el.get_text(strip=True) if title_el else "Unknown"

        # Ingredients
        ingredient_els = soup.select(
            "[class*='ingredient'] li, "
            ".recipe-ingredients li, "
            "[data-testid*='ingredient']"
        )
        ingredients = [
            parse_ingredient(el.get_text(strip=True))
            for el in ingredient_els
            if el.get_text(strip=True)
        ]

        # Instructions
        method_els = soup.select(
            "[class*='method'] li, "
            "[class*='instruction'] li, "
            ".recipe-method li, "
            "[data-testid*='method']"
        )
        instructions = [
            el.get_text(strip=True)
            for el in method_els
            if el.get_text(strip=True)
        ]

        # Servings
        serves_el = soup.select_one(
            "[class*='serves'], [class*='yield'], [data-testid*='serves']"
        )
        servings = (
            _parse_servings(serves_el.get_text()) if serves_el else None
        )

        # Times
        prep_el = soup.select_one("[class*='prep']")
        cook_el = soup.select_one("[class*='cook']")
        prep_time = _extract_minutes(prep_el) if prep_el else None
        cook_time = _extract_minutes(cook_el) if cook_el else None

        recipe_id = Recipe.make_id(title, "sainsburys")

        return Recipe(
            id=recipe_id,
            title=title,
            source="sainsburys",
            url=url,
            servings=servings,
            prep_time=prep_time,
            cook_time=cook_time,
            ingredients=ingredients,
            instructions=instructions,
        )

    def search(self, query: str) -> list[dict[str, str]]:
        """Search Sainsbury's for recipes matching a query."""
        resp = self._session.get(
            f"{self.BASE_URL}/recipes/search",
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


def _parse_servings(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _parse_iso_duration(duration: str | None) -> int | None:
    """Parse ISO 8601 duration like 'PT30M' or 'PT1H15M' to minutes."""
    if not duration:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration)
    if not m:
        return None
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2)) if m.group(2) else 0
    return hours * 60 + minutes


def _extract_minutes(el: Tag) -> int | None:
    """Extract minutes from an element's text."""
    text = el.get_text()
    m = re.search(r"(\d+)\s*(?:min|m\b)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(?:hour|hr|h)", text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 60
    return None
