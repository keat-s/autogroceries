from pathlib import Path

import pytest

from autogroceries.models import (
    DayPlan,
    Ingredient,
    Meal,
    MealPlan,
    Recipe,
)
from autogroceries.planner.consolidator import (
    _normalise_name,
    generate_shopping_list,
    write_shopping_csv,
)


@pytest.fixture(autouse=True)
def _use_tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr("autogroceries.storage.RECIPES_DIR", tmp_path / "recipes")
    monkeypatch.setattr("autogroceries.storage.PLANS_DIR", tmp_path / "plans")


def _save_recipe(recipe: Recipe) -> None:
    from autogroceries.storage import save_recipe

    save_recipe(recipe)


class TestNormaliseName:
    def test_lowercase(self) -> None:
        assert _normalise_name("Olive Oil") == "olive oil"

    def test_strips_adjectives(self) -> None:
        assert _normalise_name("fresh basil") == "basil"
        assert _normalise_name("large eggs") == "egg"

    def test_strips_plural(self) -> None:
        assert _normalise_name("onions") == "onion"

    def test_no_double_strip(self) -> None:
        assert _normalise_name("grass") == "grass"


class TestGenerateShoppingList:
    def test_single_recipe(self) -> None:
        _save_recipe(
            Recipe(
                id="r1",
                title="R1",
                source="test",
                url="http://x",
                servings=2,
                prep_time=None,
                cook_time=None,
                ingredients=[
                    Ingredient(name="chicken", quantity=500, unit="g", raw="500g chicken"),
                    Ingredient(name="rice", quantity=200, unit="g", raw="200g rice"),
                ],
                instructions=["Cook"],
            )
        )

        plan = MealPlan(
            name="test",
            days=[DayPlan(date="2026-03-30", meals=[Meal(recipe_id="r1", servings=2)])],
        )
        result = generate_shopping_list(plan)
        assert "chicken" in result
        assert "rice" in result

    def test_deduplication_across_days(self) -> None:
        _save_recipe(
            Recipe(
                id="r1",
                title="R1",
                source="test",
                url="http://x",
                servings=2,
                prep_time=None,
                cook_time=None,
                ingredients=[
                    Ingredient(name="onion", quantity=1, unit=None, raw="1 onion"),
                ],
                instructions=["Cook"],
            )
        )
        _save_recipe(
            Recipe(
                id="r2",
                title="R2",
                source="test",
                url="http://y",
                servings=2,
                prep_time=None,
                cook_time=None,
                ingredients=[
                    Ingredient(name="onions", quantity=2, unit=None, raw="2 onions"),
                ],
                instructions=["Cook"],
            )
        )

        plan = MealPlan(
            name="test",
            days=[
                DayPlan(date="2026-03-30", meals=[Meal(recipe_id="r1", servings=2)]),
                DayPlan(date="2026-03-31", meals=[Meal(recipe_id="r2", servings=2)]),
            ],
        )
        result = generate_shopping_list(plan)
        # "onion" and "onions" should normalise to the same key
        assert result["onion"] == 2

    def test_empty_plan(self) -> None:
        plan = MealPlan(name="empty", days=[])
        assert generate_shopping_list(plan) == {}


class TestWriteShoppingCsv:
    def test_csv_output(self, tmp_path: Path) -> None:
        out = tmp_path / "shopping.csv"
        write_shopping_csv({"chicken": 1, "rice": 2}, out)
        lines = out.read_text().strip().split("\n")
        assert "chicken,1" in lines
        assert "rice,2" in lines
