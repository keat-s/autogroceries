from autogroceries.models import (
    DayPlan,
    Ingredient,
    Meal,
    MealPlan,
    Recipe,
)


class TestIngredient:
    def test_round_trip(self) -> None:
        ing = Ingredient(name="olive oil", quantity=2.0, unit="tbsp", raw="2 tbsp olive oil")
        assert Ingredient.from_dict(ing.to_dict()) == ing

    def test_none_fields(self) -> None:
        ing = Ingredient(name="salt", quantity=None, unit=None, raw="a pinch of salt")
        data = ing.to_dict()
        assert data["quantity"] is None
        assert Ingredient.from_dict(data) == ing


class TestRecipe:
    def test_make_id(self) -> None:
        assert Recipe.make_id("Chicken Tikka Masala", "mobkitchen") == "chicken-tikka-masala-mobkitchen"

    def test_make_id_special_chars(self) -> None:
        assert Recipe.make_id("Fish & Chips!", "waitrose") == "fish-chips-waitrose"

    def test_round_trip(self) -> None:
        recipe = Recipe(
            id="test-recipe-mob",
            title="Test Recipe",
            source="mobkitchen",
            url="https://example.com/recipe",
            servings=4,
            prep_time=10,
            cook_time=30,
            ingredients=[
                Ingredient(name="chicken", quantity=500.0, unit="g", raw="500g chicken"),
            ],
            instructions=["Step 1", "Step 2"],
        )
        assert Recipe.from_dict(recipe.to_dict()) == recipe


class TestMealPlan:
    def test_round_trip(self) -> None:
        plan = MealPlan(
            name="week-1",
            days=[
                DayPlan(
                    date="2026-03-30",
                    meals=[Meal(recipe_id="test-recipe-mob", servings=2)],
                ),
                DayPlan(date="2026-03-31", meals=[]),
            ],
        )
        assert MealPlan.from_dict(plan.to_dict()) == plan

    def test_empty_plan(self) -> None:
        plan = MealPlan(name="empty", days=[])
        data = plan.to_dict()
        assert data["days"] == []
        assert MealPlan.from_dict(data) == plan
