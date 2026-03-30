from __future__ import annotations

import logging
import os
import re
from typing import Any

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Recipe
from autogroceries.scraper.base import RecipeScraper
from autogroceries.scraper.ingredient_parser import parse_ingredient

logger = logging.getLogger(__name__)


class ExaScraper(RecipeScraper):
    """Scraper using Exa neural search API for recipe discovery.

    Requires an ``EXA_API_KEY`` environment variable.  Exa excels at
    semantic search (e.g. "healthy chicken recipes under 30 minutes")
    and can retrieve page content for parsing.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("EXA_API_KEY")
        if not self.api_key:
            logger.warning("EXA_API_KEY not set — ExaScraper will not work.")
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazily initialise the Exa client."""
        if self._client is None:
            try:
                from exa_py import Exa  # type: ignore[import-untyped]
            except ImportError as exc:
                raise RecipeScrapeError(
                    "exa-py is not installed. "
                    "Install it with: pip install 'autogroceries[ai]'"
                ) from exc
            if not self.api_key:
                raise RecipeScrapeError(
                    "EXA_API_KEY environment variable is not set."
                )
            self._client = Exa(api_key=self.api_key)
        return self._client

    def scrape(self, url: str) -> Recipe:
        """Scrape a recipe by fetching page content through Exa.

        Args:
            url: The recipe page URL.

        Returns:
            A parsed Recipe object.

        Raises:
            RecipeScrapeError: If the page cannot be retrieved or parsed.
        """
        try:
            response = self.client.get_contents(
                ids=[url],
                text=True,
            )
        except Exception as exc:
            raise RecipeScrapeError(
                f"Exa failed to fetch content for {url}: {exc}"
            ) from exc

        results = getattr(response, "results", [])
        if not results:
            raise RecipeScrapeError(f"Exa returned no content for {url}")

        result = results[0]
        text: str = getattr(result, "text", "") or ""
        page_title: str = getattr(result, "title", "") or ""

        if not text:
            raise RecipeScrapeError(f"Exa returned empty text for {url}")

        return _parse_recipe_text(text, page_title, url)

    def search(self, query: str) -> list[dict[str, str]]:
        """Search for recipes using Exa neural search.

        Args:
            query: Natural-language search query.

        Returns:
            List of dicts with 'title' and 'url' keys.
        """
        try:
            response = self.client.search(
                f"recipe: {query}",
                num_results=10,
                type="neural",
            )
        except Exception:
            logger.exception("Exa search failed for query: %s", query)
            return []

        results: list[dict[str, str]] = []
        for item in getattr(response, "results", []):
            title = getattr(item, "title", "") or ""
            url = getattr(item, "url", "") or ""
            if title and url:
                results.append({"title": title, "url": url})
        return results[:20]


# ---------------------------------------------------------------------------
# Helpers for parsing plain-text recipe content
# ---------------------------------------------------------------------------

_INGREDIENTS_HEADER_RE = re.compile(
    r"^#+\s*ingredients\s*$|^ingredients\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_INSTRUCTIONS_HEADER_RE = re.compile(
    r"^#+\s*(instructions|directions|method|steps)\s*$"
    r"|^(instructions|directions|method|steps)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_recipe_text(text: str, title: str, url: str) -> Recipe:
    """Best-effort recipe extraction from plain/markdown text."""
    ingredients_raw = _extract_section(text, _INGREDIENTS_HEADER_RE)
    instructions_raw = _extract_section(text, _INSTRUCTIONS_HEADER_RE)

    # Fall back: use bullet/numbered lines as ingredients if no header found
    if not ingredients_raw:
        ingredients_raw = _extract_list_lines(text)

    ingredients = [parse_ingredient(line) for line in ingredients_raw if line.strip()]
    instructions = instructions_raw if instructions_raw else [text[:500]]

    if not title:
        # Use first non-empty line as a title fallback
        for line in text.splitlines():
            stripped = line.strip("# \t")
            if stripped:
                title = stripped[:120]
                break
        title = title or "Unknown Recipe"

    recipe_id = Recipe.make_id(title, "exa")

    return Recipe(
        id=recipe_id,
        title=title,
        source="exa",
        url=url,
        servings=None,
        prep_time=None,
        cook_time=None,
        ingredients=ingredients,
        instructions=instructions,
    )


def _extract_section(text: str, header_re: re.Pattern[str]) -> list[str]:
    """Extract lines between a header and the next header or blank gap."""
    match = header_re.search(text)
    if not match:
        return []

    start = match.end()
    lines: list[str] = []
    for raw_line in text[start:].splitlines():
        line = raw_line.strip()
        if not line:
            if lines:
                break
            continue
        # Stop at the next markdown header
        if line.startswith("#"):
            break
        # Strip leading bullets / numbers
        cleaned = re.sub(r"^[-*•]\s*|\d+[.)]\s*", "", line)
        if cleaned:
            lines.append(cleaned)
    return lines


def _extract_list_lines(text: str) -> list[str]:
    """Extract bullet or numbered list items from text."""
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        m = re.match(r"^[-*•]\s+(.+)", line)
        if m:
            lines.append(m.group(1))
    return lines
