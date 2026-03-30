from __future__ import annotations

from datetime import date

from autogroceries.recommender.seasonal import (
    SEASONAL_INGREDIENTS,
    get_current_season,
    get_seasonal_ingredients,
)


class TestGetCurrentSeason:
    def test_spring(self) -> None:
        assert get_current_season(date(2026, 3, 15)) == "spring"
        assert get_current_season(date(2026, 4, 1)) == "spring"
        assert get_current_season(date(2026, 5, 31)) == "spring"

    def test_summer(self) -> None:
        assert get_current_season(date(2026, 6, 1)) == "summer"
        assert get_current_season(date(2026, 7, 15)) == "summer"
        assert get_current_season(date(2026, 8, 31)) == "summer"

    def test_autumn(self) -> None:
        assert get_current_season(date(2026, 9, 1)) == "autumn"
        assert get_current_season(date(2026, 10, 15)) == "autumn"
        assert get_current_season(date(2026, 11, 30)) == "autumn"

    def test_winter(self) -> None:
        assert get_current_season(date(2026, 12, 1)) == "winter"
        assert get_current_season(date(2026, 1, 15)) == "winter"
        assert get_current_season(date(2026, 2, 28)) == "winter"


class TestGetSeasonalIngredients:
    def test_returns_spring_ingredients(self) -> None:
        ingredients = get_seasonal_ingredients(date(2026, 4, 10))
        assert ingredients == SEASONAL_INGREDIENTS["spring"]

    def test_returns_winter_ingredients(self) -> None:
        ingredients = get_seasonal_ingredients(date(2026, 12, 25))
        assert ingredients == SEASONAL_INGREDIENTS["winter"]

    def test_returns_non_empty_list(self) -> None:
        for month in range(1, 13):
            ingredients = get_seasonal_ingredients(date(2026, month, 15))
            assert len(ingredients) > 0

    def test_all_seasons_have_ingredients(self) -> None:
        for season, items in SEASONAL_INGREDIENTS.items():
            assert len(items) > 5, f"{season} has too few ingredients"
