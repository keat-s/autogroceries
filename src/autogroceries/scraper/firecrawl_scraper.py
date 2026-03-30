from __future__ import annotations

import logging
import os
from typing import Any

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Nutrition, Recipe
from autogroceries.scraper.base import RecipeScraper
from autogroceries.scraper.ingredient_parser import parse_ingredient

logger = logging.getLogger(__name__)

EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "ingredients": {"type": "array", "items": {"type": "string"}},
        "instructions": {"type": "array", "items": {"type": "string"}},
        "servings": {"type": "string"},
        "prep_time_minutes": {"type": "integer"},
        "cook_time_minutes": {"type": "integer"},
        "calories_per_serving": {"type": "number"},
        "protein_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "fat_g": {"type": "number"},
    },
    "required": ["title", "ingredients", "instructions"],
}


class FirecrawlScraper(RecipeScraper):
    """Scraper using Firecrawl API for any recipe website.

    Requires a ``FIRECRAWL_API_KEY`` environment variable.  The scraper
    uses Firecrawl's structured-extraction feature to pull recipe data
    from arbitrary URLs and its ``/search`` endpoint for recipe discovery.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            logger.warning(
                "FIRECRAWL_API_KEY not set — FirecrawlScraper will not work."
            )
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazily initialise the Firecrawl client."""
        if self._client is None:
            try:
                from firecrawl import FirecrawlApp  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RecipeScrapeError(
                    "firecrawl-py is not installed. "
                    "Install it with: pip install 'autogroceries[ai]'"
                ) from exc
            if not self.api_key:
                raise RecipeScrapeError(
                    "FIRECRAWL_API_KEY environment variable is not set."
                )
            self._client = FirecrawlApp(api_key=self.api_key)
        return self._client

    def scrape(self, url: str) -> Recipe:
        """Scrape a recipe from *url* using Firecrawl structured extraction.

        Args:
            url: The recipe page URL.

        Returns:
            A parsed Recipe object.

        Raises:
            RecipeScrapeError: If the page cannot be scraped or parsed.
        """
        try:
            result = self.client.scrape_url(
                url,
                params={
                    "formats": ["extract"],
                    "extract": {"schema": EXTRACT_SCHEMA},
                },
            )
        except Exception as exc:
            raise RecipeScrapeError(
                f"Firecrawl failed to scrape {url}: {exc}"
            ) from exc

        data: dict[str, Any] = (result or {}).get("extract", {})
        if not data or not data.get("title"):
            raise RecipeScrapeError(
                f"Firecrawl returned no recipe data for {url}"
            )

        title: str = data["title"]
        raw_ingredients: list[str] = data.get("ingredients", [])
        instructions: list[str] = data.get("instructions", [])

        ingredients = [parse_ingredient(raw) for raw in raw_ingredients]

        servings = _parse_servings(data.get("servings"))
        prep_time = data.get("prep_time_minutes")
        cook_time = data.get("cook_time_minutes")

        nutrition = _build_nutrition(data)

        recipe_id = Recipe.make_id(title, "firecrawl")

        return Recipe(
            id=recipe_id,
            title=title,
            source="firecrawl",
            url=url,
            servings=servings,
            prep_time=prep_time,
            cook_time=cook_time,
            ingredients=ingredients,
            instructions=instructions,
            nutrition=nutrition,
        )

    def search(self, query: str) -> list[dict[str, str]]:
        """Search for recipes using Firecrawl's search endpoint.

        Args:
            query: Search term, e.g. "quick pasta recipes".

        Returns:
            List of dicts with 'title' and 'url' keys.
        """
        try:
            response = self.client.search(
                f"recipe {query}",
                params={"limit": 10},
            )
        except Exception:
            logger.exception("Firecrawl search failed for query: %s", query)
            return []

        results: list[dict[str, str]] = []
        items = response if isinstance(response, list) else (response or {}).get("data", [])
        for item in items:
            title = item.get("title") or item.get("metadata", {}).get("title", "")
            url = item.get("url", "")
            if title and url:
                results.append({"title": title, "url": url})
        return results[:20]


def _parse_servings(value: Any) -> int | None:
    """Extract an integer serving count from a string or number."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    import re

    m = re.search(r"\d+", str(value))
    return int(m.group()) if m else None


def _build_nutrition(data: dict[str, Any]) -> Nutrition | None:
    """Build a Nutrition object from extracted recipe data."""
    cals = data.get("calories_per_serving")
    protein = data.get("protein_g")
    carbs = data.get("carbs_g")
    fat = data.get("fat_g")
    if not any(v is not None for v in (cals, protein, carbs, fat)):
        return None
    return Nutrition(
        calories=cals,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
    )
