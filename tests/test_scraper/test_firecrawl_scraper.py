from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.scraper.firecrawl_scraper import FirecrawlScraper


@pytest.fixture()
def scraper() -> FirecrawlScraper:
    """Return a FirecrawlScraper with a dummy API key."""
    with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test-key"}):
        return FirecrawlScraper()


FAKE_EXTRACT = {
    "title": "Classic Tomato Pasta",
    "ingredients": [
        "400g spaghetti",
        "2 tbsp olive oil",
        "3 cloves garlic",
        "400g tinned tomatoes",
    ],
    "instructions": [
        "Boil the pasta.",
        "Fry the garlic in olive oil.",
        "Add tinned tomatoes and simmer.",
        "Toss the pasta with the sauce.",
    ],
    "servings": "4 servings",
    "prep_time_minutes": 10,
    "cook_time_minutes": 20,
    "calories_per_serving": 450,
    "protein_g": 12.0,
    "carbs_g": 70.0,
    "fat_g": 10.5,
}


class TestFirecrawlScrape:
    def test_scrape_success(self, scraper: FirecrawlScraper) -> None:
        mock_client = MagicMock()
        mock_client.scrape_url.return_value = {"extract": FAKE_EXTRACT}
        scraper._client = mock_client

        recipe = scraper.scrape("https://example.com/recipe/tomato-pasta")

        mock_client.scrape_url.assert_called_once()
        assert recipe.title == "Classic Tomato Pasta"
        assert recipe.source == "firecrawl"
        assert len(recipe.ingredients) == 4
        assert recipe.ingredients[0].name == "spaghetti"
        assert recipe.ingredients[0].quantity == 400.0
        assert len(recipe.instructions) == 4
        assert recipe.servings == 4
        assert recipe.prep_time == 10
        assert recipe.cook_time == 20
        assert recipe.nutrition is not None
        assert recipe.nutrition.calories == 450
        assert recipe.nutrition.protein_g == 12.0
        assert recipe.nutrition.carbs_g == 70.0
        assert recipe.nutrition.fat_g == 10.5

    def test_scrape_no_extract_data(self, scraper: FirecrawlScraper) -> None:
        mock_client = MagicMock()
        mock_client.scrape_url.return_value = {"extract": {}}
        scraper._client = mock_client

        with pytest.raises(RecipeScrapeError, match="no recipe data"):
            scraper.scrape("https://example.com/empty")

    def test_scrape_api_error(self, scraper: FirecrawlScraper) -> None:
        mock_client = MagicMock()
        mock_client.scrape_url.side_effect = RuntimeError("API down")
        scraper._client = mock_client

        with pytest.raises(RecipeScrapeError, match="Firecrawl failed"):
            scraper.scrape("https://example.com/fail")

    def test_scrape_no_nutrition(self, scraper: FirecrawlScraper) -> None:
        data = {
            "title": "Simple Salad",
            "ingredients": ["1 lettuce", "2 tomatoes"],
            "instructions": ["Chop and mix."],
        }
        mock_client = MagicMock()
        mock_client.scrape_url.return_value = {"extract": data}
        scraper._client = mock_client

        recipe = scraper.scrape("https://example.com/salad")
        assert recipe.nutrition is None

    def test_scrape_missing_api_key(self) -> None:
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": ""}):
            s = FirecrawlScraper()
            s.api_key = None
            with pytest.raises(RecipeScrapeError):
                s.scrape("https://example.com/any")


class TestFirecrawlSearch:
    def test_search_success(self, scraper: FirecrawlScraper) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {"title": "Pasta Recipe", "url": "https://example.com/pasta"},
            {"title": "Rice Recipe", "url": "https://example.com/rice"},
        ]
        scraper._client = mock_client

        results = scraper.search("easy dinner")
        assert len(results) == 2
        assert results[0]["title"] == "Pasta Recipe"
        assert results[1]["url"] == "https://example.com/rice"

    def test_search_returns_empty_on_error(self, scraper: FirecrawlScraper) -> None:
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("timeout")
        scraper._client = mock_client

        results = scraper.search("anything")
        assert results == []

    def test_search_with_dict_response(self, scraper: FirecrawlScraper) -> None:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "data": [
                {"title": "Soup", "url": "https://example.com/soup"},
            ]
        }
        scraper._client = mock_client

        results = scraper.search("soup")
        assert len(results) == 1
        assert results[0]["title"] == "Soup"
