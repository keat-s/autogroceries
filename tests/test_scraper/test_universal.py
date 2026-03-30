from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Ingredient, Nutrition, Recipe
from autogroceries.scraper.universal import (
    UniversalScraper,
    _find_recipe_in_jsonld,
    _normalise_instructions,
    _parse_iso_duration,
)


@pytest.fixture()
def scraper() -> UniversalScraper:
    return UniversalScraper()


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestParseIsoDuration:
    def test_minutes(self) -> None:
        assert _parse_iso_duration("PT30M") == 30

    def test_hours_and_minutes(self) -> None:
        assert _parse_iso_duration("PT1H15M") == 75

    def test_hours_only(self) -> None:
        assert _parse_iso_duration("PT2H") == 120

    def test_none(self) -> None:
        assert _parse_iso_duration(None) is None

    def test_empty_string(self) -> None:
        assert _parse_iso_duration("") is None

    def test_invalid(self) -> None:
        assert _parse_iso_duration("not-a-duration") is None


class TestFindRecipeInJsonld:
    def test_direct_recipe(self) -> None:
        data = {"@type": "Recipe", "name": "Test"}
        assert _find_recipe_in_jsonld(data) == data

    def test_recipe_in_graph(self) -> None:
        data = {
            "@graph": [
                {"@type": "WebPage"},
                {"@type": "Recipe", "name": "Nested"},
            ]
        }
        result = _find_recipe_in_jsonld(data)
        assert result is not None
        assert result["name"] == "Nested"

    def test_recipe_in_list(self) -> None:
        data = [{"@type": "WebPage"}, {"@type": "Recipe", "name": "InList"}]
        result = _find_recipe_in_jsonld(data)
        assert result is not None
        assert result["name"] == "InList"

    def test_no_recipe(self) -> None:
        assert _find_recipe_in_jsonld({"@type": "WebPage"}) is None


class TestNormaliseInstructions:
    def test_string(self) -> None:
        assert _normalise_instructions("Do this.") == ["Do this."]

    def test_list_of_strings(self) -> None:
        assert _normalise_instructions(["a", "b"]) == ["a", "b"]

    def test_list_of_dicts(self) -> None:
        data = [{"text": "Step 1"}, {"text": "Step 2"}]
        assert _normalise_instructions(data) == ["Step 1", "Step 2"]


# ---------------------------------------------------------------------------
# Fallback chain tests
# ---------------------------------------------------------------------------

FAKE_RECIPE = Recipe(
    id="test-recipe-universal",
    title="Test Recipe",
    source="universal",
    url="https://example.com/recipe",
    servings=4,
    prep_time=10,
    cook_time=20,
    ingredients=[Ingredient(name="eggs", quantity=3, unit=None, raw="3 eggs")],
    instructions=["Cook the eggs."],
)


class TestUniversalScrapeFallback:
    @patch("autogroceries.scraper.universal._scrape_with_recipe_scrapers")
    def test_recipe_scrapers_succeeds(
        self, mock_rs: MagicMock, scraper: UniversalScraper
    ) -> None:
        mock_rs.return_value = FAKE_RECIPE
        result = scraper.scrape("https://example.com/recipe")
        assert result.title == "Test Recipe"
        mock_rs.assert_called_once()

    @patch("autogroceries.scraper.universal._scrape_with_jsonld")
    @patch("autogroceries.scraper.universal._scrape_with_recipe_scrapers")
    def test_falls_back_to_jsonld(
        self,
        mock_rs: MagicMock,
        mock_jsonld: MagicMock,
        scraper: UniversalScraper,
    ) -> None:
        mock_rs.side_effect = Exception("unsupported site")
        mock_jsonld.return_value = FAKE_RECIPE
        result = scraper.scrape("https://example.com/recipe")
        assert result.title == "Test Recipe"
        mock_rs.assert_called_once()
        mock_jsonld.assert_called_once()

    @patch("autogroceries.scraper.universal._scrape_with_jsonld")
    @patch("autogroceries.scraper.universal._scrape_with_recipe_scrapers")
    def test_falls_back_to_firecrawl(
        self,
        mock_rs: MagicMock,
        mock_jsonld: MagicMock,
        scraper: UniversalScraper,
    ) -> None:
        mock_rs.side_effect = Exception("fail")
        mock_jsonld.side_effect = Exception("no json-ld")

        mock_fc = MagicMock()
        mock_fc.return_value.scrape.return_value = FAKE_RECIPE

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "key"}):
            with patch(
                "autogroceries.scraper.firecrawl_scraper.FirecrawlScraper",
                mock_fc,
            ):
                result = scraper.scrape("https://example.com/recipe")

        assert result.title == "Test Recipe"
        mock_fc.return_value.scrape.assert_called_once()

    @patch("autogroceries.scraper.universal._scrape_with_jsonld")
    @patch("autogroceries.scraper.universal._scrape_with_recipe_scrapers")
    def test_falls_back_to_exa(
        self,
        mock_rs: MagicMock,
        mock_jsonld: MagicMock,
        scraper: UniversalScraper,
    ) -> None:
        mock_rs.side_effect = Exception("fail")
        mock_jsonld.side_effect = Exception("fail")

        mock_exa = MagicMock()
        mock_exa.return_value.scrape.return_value = FAKE_RECIPE

        with patch.dict(
            "os.environ",
            {"EXA_API_KEY": "key"},
            clear=False,
        ):
            # Ensure FIRECRAWL_API_KEY is not set so we skip firecrawl
            with patch.dict("os.environ", {"FIRECRAWL_API_KEY": ""}, clear=False):
                with patch(
                    "autogroceries.scraper.exa_scraper.ExaScraper", mock_exa
                ):
                    result = scraper.scrape("https://example.com/recipe")

        assert result.title == "Test Recipe"

    @patch("autogroceries.scraper.universal._scrape_with_jsonld")
    @patch("autogroceries.scraper.universal._scrape_with_recipe_scrapers")
    def test_all_methods_fail(
        self,
        mock_rs: MagicMock,
        mock_jsonld: MagicMock,
        scraper: UniversalScraper,
    ) -> None:
        mock_rs.side_effect = Exception("fail")
        mock_jsonld.side_effect = Exception("fail")

        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "", "EXA_API_KEY": ""}):
            with pytest.raises(RecipeScrapeError, match="All scraping methods failed"):
                scraper.scrape("https://example.com/recipe")


class TestUniversalSearch:
    def test_search_uses_exa_first(self, scraper: UniversalScraper) -> None:
        mock_exa = MagicMock()
        mock_exa.return_value.search.return_value = [
            {"title": "Exa Result", "url": "https://example.com/exa"}
        ]

        with patch.dict("os.environ", {"EXA_API_KEY": "key"}):
            with patch(
                "autogroceries.scraper.exa_scraper.ExaScraper", mock_exa
            ):
                results = scraper.search("dinner ideas")

        assert len(results) == 1
        assert results[0]["title"] == "Exa Result"

    def test_search_falls_back_to_firecrawl(
        self, scraper: UniversalScraper
    ) -> None:
        mock_exa = MagicMock()
        mock_exa.return_value.search.return_value = []

        mock_fc = MagicMock()
        mock_fc.return_value.search.return_value = [
            {"title": "FC Result", "url": "https://example.com/fc"}
        ]

        with patch.dict(
            "os.environ",
            {"EXA_API_KEY": "key", "FIRECRAWL_API_KEY": "key"},
        ):
            with patch(
                "autogroceries.scraper.exa_scraper.ExaScraper", mock_exa
            ), patch(
                "autogroceries.scraper.firecrawl_scraper.FirecrawlScraper",
                mock_fc,
            ):
                results = scraper.search("dinner ideas")

        assert len(results) == 1
        assert results[0]["title"] == "FC Result"

    def test_search_no_keys_returns_empty(
        self, scraper: UniversalScraper
    ) -> None:
        with patch.dict(
            "os.environ", {"EXA_API_KEY": "", "FIRECRAWL_API_KEY": ""}
        ):
            results = scraper.search("anything")
        assert results == []
