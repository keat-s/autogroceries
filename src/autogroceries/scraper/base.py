from __future__ import annotations

from abc import ABC, abstractmethod

from autogroceries.models import Recipe


class RecipeScraper(ABC):
    """Abstract base class for recipe scrapers."""

    @abstractmethod
    def scrape(self, url: str) -> Recipe:
        """Scrape a recipe from a URL.

        Args:
            url: The recipe page URL.

        Returns:
            A parsed Recipe object.
        """

    @abstractmethod
    def search(self, query: str) -> list[dict[str, str]]:
        """Search for recipes by keyword.

        Args:
            query: Search term.

        Returns:
            List of dicts with 'title' and 'url' keys.
        """
