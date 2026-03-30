from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import SchemaOrgException  # type: ignore[import-untyped]

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Nutrition, Recipe
from autogroceries.scraper.base import RecipeScraper
from autogroceries.scraper.ingredient_parser import parse_ingredient

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.6 Safari/605.1.15"
    )
}


class UniversalScraper(RecipeScraper):
    """Smart scraper that tries multiple extraction methods.

    The scraping order (cheapest first):

    1. ``recipe-scrapers`` library (free, works for many popular sites).
    2. JSON-LD / Schema.org Recipe markup embedded in the page HTML.
    3. Firecrawl structured extraction (requires ``FIRECRAWL_API_KEY``).
    4. Exa content retrieval (requires ``EXA_API_KEY``).
    """

    def scrape(self, url: str) -> Recipe:
        """Scrape a recipe, trying progressively more expensive methods.

        Args:
            url: The recipe page URL.

        Returns:
            A parsed Recipe object.

        Raises:
            RecipeScrapeError: If all methods fail.
        """
        errors: list[str] = []

        # 1. recipe-scrapers
        try:
            return _scrape_with_recipe_scrapers(url)
        except Exception as exc:
            errors.append(f"recipe-scrapers: {exc}")
            logger.debug("recipe-scrapers failed for %s: %s", url, exc)

        # 2. JSON-LD
        try:
            return _scrape_with_jsonld(url)
        except Exception as exc:
            errors.append(f"json-ld: {exc}")
            logger.debug("JSON-LD extraction failed for %s: %s", url, exc)

        # 3. Firecrawl
        if os.getenv("FIRECRAWL_API_KEY"):
            try:
                from autogroceries.scraper.firecrawl_scraper import (
                    FirecrawlScraper,
                )

                return FirecrawlScraper().scrape(url)
            except Exception as exc:
                errors.append(f"firecrawl: {exc}")
                logger.debug("Firecrawl failed for %s: %s", url, exc)

        # 4. Exa
        if os.getenv("EXA_API_KEY"):
            try:
                from autogroceries.scraper.exa_scraper import ExaScraper

                return ExaScraper().scrape(url)
            except Exception as exc:
                errors.append(f"exa: {exc}")
                logger.debug("Exa failed for %s: %s", url, exc)

        raise RecipeScrapeError(
            f"All scraping methods failed for {url}:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    def search(self, query: str) -> list[dict[str, str]]:
        """Search for recipes, preferring Exa then falling back to Firecrawl.

        Args:
            query: Natural-language search query.

        Returns:
            List of dicts with 'title' and 'url' keys.
        """
        # Prefer Exa for search (best semantic search)
        if os.getenv("EXA_API_KEY"):
            try:
                from autogroceries.scraper.exa_scraper import ExaScraper

                results = ExaScraper().search(query)
                if results:
                    return results
            except Exception:
                logger.debug("Exa search failed, trying Firecrawl.")

        # Fall back to Firecrawl
        if os.getenv("FIRECRAWL_API_KEY"):
            try:
                from autogroceries.scraper.firecrawl_scraper import (
                    FirecrawlScraper,
                )

                results = FirecrawlScraper().search(query)
                if results:
                    return results
            except Exception:
                logger.debug("Firecrawl search also failed.")

        logger.warning(
            "No AI search backend available. "
            "Set EXA_API_KEY or FIRECRAWL_API_KEY for recipe search."
        )
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _scrape_with_recipe_scrapers(url: str) -> Recipe:
    """Attempt to scrape using the recipe-scrapers library."""
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    scraper = scrape_html(html=resp.text, org_url=url)

    title = scraper.title()
    ingredients = [parse_ingredient(i) for i in scraper.ingredients()]
    try:
        instructions = scraper.instructions_list()
    except Exception:
        instructions = [scraper.instructions()]

    servings = _parse_servings(scraper.yields())

    def _safe_int(method: object) -> int | None:
        try:
            val = method()  # type: ignore[operator]
            return int(val) if val else None
        except Exception:
            return None

    nutrition = _extract_rs_nutrition(scraper)

    recipe_id = Recipe.make_id(title, "universal")
    return Recipe(
        id=recipe_id,
        title=title,
        source="universal",
        url=url,
        servings=servings,
        prep_time=_safe_int(scraper.prep_time),
        cook_time=_safe_int(scraper.cook_time),
        ingredients=ingredients,
        instructions=instructions,
        nutrition=nutrition,
    )


def _scrape_with_jsonld(url: str) -> Recipe:
    """Extract recipe data from Schema.org JSON-LD markup."""
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(resp.text, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    recipe_data: dict[str, Any] | None = None
    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        recipe_data = _find_recipe_in_jsonld(data)
        if recipe_data:
            break

    if not recipe_data:
        raise RecipeScrapeError("No JSON-LD Recipe found")

    title = recipe_data.get("name", "Unknown Recipe")

    raw_ingredients = recipe_data.get("recipeIngredient", [])
    ingredients = [parse_ingredient(i) for i in raw_ingredients]

    raw_instructions = recipe_data.get("recipeInstructions", [])
    instructions = _normalise_instructions(raw_instructions)

    servings = _parse_servings(recipe_data.get("recipeYield"))

    prep_time = _parse_iso_duration(recipe_data.get("prepTime"))
    cook_time = _parse_iso_duration(recipe_data.get("cookTime"))

    nutrition = _extract_jsonld_nutrition(recipe_data.get("nutrition", {}))

    recipe_id = Recipe.make_id(title, "universal")
    return Recipe(
        id=recipe_id,
        title=title,
        source="universal",
        url=url,
        servings=servings,
        prep_time=prep_time,
        cook_time=cook_time,
        ingredients=ingredients,
        instructions=instructions,
        nutrition=nutrition,
    )


def _find_recipe_in_jsonld(data: Any) -> dict[str, Any] | None:
    """Recursively find a Recipe object in JSON-LD data."""
    if isinstance(data, dict):
        if data.get("@type") == "Recipe":
            return data
        # Check @graph
        for val in data.values():
            found = _find_recipe_in_jsonld(val)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_recipe_in_jsonld(item)
            if found:
                return found
    return None


def _normalise_instructions(raw: Any) -> list[str]:
    """Normalise JSON-LD recipeInstructions into a flat list of strings."""
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    out.append(text)
        return out
    return []


def _parse_iso_duration(value: Any) -> int | None:
    """Parse an ISO-8601 duration like ``PT30M`` into minutes."""
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", value)
    if not m:
        return None
    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2)) if m.group(2) else 0
    total = hours * 60 + minutes
    return total if total > 0 else None


def _parse_servings(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    m = re.search(r"\d+", str(value))
    return int(m.group()) if m else None


def _extract_rs_nutrition(scraper: object) -> Nutrition | None:
    """Extract nutrition from a recipe-scrapers object."""
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


def _extract_jsonld_nutrition(data: Any) -> Nutrition | None:
    """Extract nutrition from JSON-LD nutrition object."""
    if not data or not isinstance(data, dict):
        return None

    def _float(key: str) -> float | None:
        val = data.get(key, "")
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
