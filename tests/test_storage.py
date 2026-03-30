import pytest

from autogroceries.exceptions import PlanNotFoundError, RecipeNotFoundError
from autogroceries.models import (
    DayPlan,
    Ingredient,
    Meal,
    MealPlan,
    Recipe,
)
from autogroceries.storage import (
    PLANS_DIR,
    RECIPES_DIR,
    delete_recipe,
    list_plans,
    list_recipes,
    load_plan,
    load_recipe,
    save_plan,
    save_recipe,
)


@pytest.fixture(autouse=True)
def _use_tmp_dirs(tmp_path, monkeypatch):
    """Redirect storage dirs to tmp_path for test isolation."""
    monkeypatch.setattr("autogroceries.storage.RECIPES_DIR", tmp_path / "recipes")
    monkeypatch.setattr("autogroceries.storage.PLANS_DIR", tmp_path / "plans")


def _make_recipe(recipe_id: str = "test-recipe-mob") -> Recipe:
    return Recipe(
        id=recipe_id,
        title="Test Recipe",
        source="mobkitchen",
        url="https://example.com/recipe",
        servings=4,
        prep_time=10,
        cook_time=30,
        ingredients=[
            Ingredient(name="chicken", quantity=500.0, unit="g", raw="500g chicken"),
        ],
        instructions=["Step 1"],
    )


class TestRecipeStorage:
    def test_save_and_load(self) -> None:
        recipe = _make_recipe()
        save_recipe(recipe)
        loaded = load_recipe("test-recipe-mob")
        assert loaded == recipe

    def test_load_not_found(self) -> None:
        with pytest.raises(RecipeNotFoundError):
            load_recipe("nonexistent")

    def test_list_recipes(self) -> None:
        save_recipe(_make_recipe("a-recipe"))
        save_recipe(_make_recipe("b-recipe"))
        recipes = list_recipes()
        assert len(recipes) == 2
        assert recipes[0].id == "a-recipe"

    def test_delete_recipe(self) -> None:
        save_recipe(_make_recipe())
        delete_recipe("test-recipe-mob")
        assert list_recipes() == []

    def test_delete_not_found(self) -> None:
        with pytest.raises(RecipeNotFoundError):
            delete_recipe("nonexistent")


class TestPlanStorage:
    def test_save_and_load(self) -> None:
        plan = MealPlan(
            name="week-14",
            days=[DayPlan(date="2026-03-30", meals=[Meal(recipe_id="x", servings=2)])],
        )
        save_plan(plan)
        loaded = load_plan("week-14")
        assert loaded == plan

    def test_load_not_found(self) -> None:
        with pytest.raises(PlanNotFoundError):
            load_plan("nonexistent")

    def test_list_plans(self) -> None:
        save_plan(MealPlan(name="a-plan", days=[]))
        save_plan(MealPlan(name="b-plan", days=[]))
        plans = list_plans()
        assert len(plans) == 2
