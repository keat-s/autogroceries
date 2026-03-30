from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.scraper.exa_scraper import ExaScraper


@pytest.fixture()
def scraper() -> ExaScraper:
    """Return an ExaScraper with a dummy API key."""
    with patch.dict("os.environ", {"EXA_API_KEY": "test-key"}):
        return ExaScraper()


RECIPE_TEXT = """\
# Chicken Stir Fry

A quick weeknight dinner.

## Ingredients

- 500g chicken breast
- 2 tbsp soy sauce
- 1 red pepper
- 200g noodles

## Instructions

1. Slice the chicken.
2. Stir fry the chicken and pepper.
3. Add soy sauce and noodles.
4. Serve hot.
"""


class TestExaScrape:
    def test_scrape_success(self, scraper: ExaScraper) -> None:
        result_obj = SimpleNamespace(
            text=RECIPE_TEXT,
            title="Chicken Stir Fry",
        )
        mock_client = MagicMock()
        mock_client.get_contents.return_value = SimpleNamespace(results=[result_obj])
        scraper._client = mock_client

        recipe = scraper.scrape("https://example.com/chicken-stir-fry")

        assert recipe.title == "Chicken Stir Fry"
        assert recipe.source == "exa"
        assert len(recipe.ingredients) == 4
        assert recipe.ingredients[0].name == "chicken breast"
        assert recipe.ingredients[0].quantity == 500.0
        assert len(recipe.instructions) == 4
        assert "Slice the chicken" in recipe.instructions[0]

    def test_scrape_no_results(self, scraper: ExaScraper) -> None:
        mock_client = MagicMock()
        mock_client.get_contents.return_value = SimpleNamespace(results=[])
        scraper._client = mock_client

        with pytest.raises(RecipeScrapeError, match="no content"):
            scraper.scrape("https://example.com/empty")

    def test_scrape_empty_text(self, scraper: ExaScraper) -> None:
        result_obj = SimpleNamespace(text="", title="Empty")
        mock_client = MagicMock()
        mock_client.get_contents.return_value = SimpleNamespace(results=[result_obj])
        scraper._client = mock_client

        with pytest.raises(RecipeScrapeError, match="empty text"):
            scraper.scrape("https://example.com/empty-text")

    def test_scrape_api_error(self, scraper: ExaScraper) -> None:
        mock_client = MagicMock()
        mock_client.get_contents.side_effect = RuntimeError("network error")
        scraper._client = mock_client

        with pytest.raises(RecipeScrapeError, match="Exa failed"):
            scraper.scrape("https://example.com/fail")

    def test_scrape_missing_api_key(self) -> None:
        with patch.dict("os.environ", {"EXA_API_KEY": ""}):
            s = ExaScraper()
            s.api_key = None
            with pytest.raises(RecipeScrapeError):
                s.scrape("https://example.com/any")


class TestExaSearch:
    def test_search_success(self, scraper: ExaScraper) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = SimpleNamespace(
            results=[
                SimpleNamespace(title="Thai Curry", url="https://example.com/curry"),
                SimpleNamespace(title="Pad Thai", url="https://example.com/padthai"),
            ]
        )
        scraper._client = mock_client

        results = scraper.search("thai recipes")
        assert len(results) == 2
        assert results[0]["title"] == "Thai Curry"
        assert results[1]["url"] == "https://example.com/padthai"

    def test_search_returns_empty_on_error(self, scraper: ExaScraper) -> None:
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("timeout")
        scraper._client = mock_client

        results = scraper.search("anything")
        assert results == []

    def test_search_no_results(self, scraper: ExaScraper) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = SimpleNamespace(results=[])
        scraper._client = mock_client

        results = scraper.search("obscure query")
        assert results == []
