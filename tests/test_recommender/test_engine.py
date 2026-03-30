from __future__ import annotations

from datetime import date
from unittest.mock import patch

from autogroceries.models import (
    Ingredient,
    Nutrition,
    PantryItem,
    Recipe,
    UserProfile,
)
from autogroceries.recommender.engine import RecipeRecommender, _closeness


def _make_recipe(
    id: str = "test-recipe",
    title: str = "Test Recipe",
    ingredients: list[Ingredient] | None = None,
    nutrition: Nutrition | None = None,
) -> Recipe:
    """Helper to build a minimal Recipe for testing."""
    return Recipe(
        id=id,
        title=title,
        source="test",
        url="https://example.com",
        servings=4,
        prep_time=10,
        cook_time=20,
        ingredients=ingredients or [],
        instructions=["Step 1"],
        nutrition=nutrition,
    )


# ------------------------------------------------------------------
# Dietary scoring
# ------------------------------------------------------------------


class TestDietaryScoring:
    def test_vegetarian_recipe_scores_full(self) -> None:
        """A veggie recipe should score 1.0 for a vegetarian user."""
        profile = UserProfile(dietary_restrictions=["vegetarian"])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="pasta", quantity=200, unit="g", raw="200g pasta"),
                Ingredient(name="tomatoes", quantity=400, unit="g", raw="400g tomatoes"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dietary(recipe) == 1.0

    def test_meat_recipe_scores_zero_for_vegetarian(self) -> None:
        """A meat recipe should score 0.0 for a vegetarian user."""
        profile = UserProfile(dietary_restrictions=["vegetarian"])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="chicken breast", quantity=500, unit="g", raw="500g chicken breast"),
                Ingredient(name="rice", quantity=200, unit="g", raw="200g rice"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dietary(recipe) == 0.0

    def test_no_restrictions_always_passes(self) -> None:
        profile = UserProfile(dietary_restrictions=[])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="steak", quantity=300, unit="g", raw="300g steak"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dietary(recipe) == 1.0

    def test_vegan_rejects_dairy(self) -> None:
        profile = UserProfile(dietary_restrictions=["vegan"])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="cheese", quantity=100, unit="g", raw="100g cheese"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dietary(recipe) == 0.0

    def test_gluten_free_rejects_flour(self) -> None:
        profile = UserProfile(dietary_restrictions=["gluten-free"])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="plain flour", quantity=200, unit="g", raw="200g plain flour"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dietary(recipe) == 0.0


# ------------------------------------------------------------------
# Disliked ingredients scoring
# ------------------------------------------------------------------


class TestDislikesScoring:
    def test_disliked_ingredient_scores_zero(self) -> None:
        profile = UserProfile(disliked_ingredients=["mushrooms"])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="mushrooms", quantity=200, unit="g", raw="200g mushrooms"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dislikes(recipe) == 0.0

    def test_no_dislikes_scores_full(self) -> None:
        profile = UserProfile(disliked_ingredients=[])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="mushrooms", quantity=200, unit="g", raw="200g mushrooms"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dislikes(recipe) == 1.0

    def test_recipe_without_disliked_ingredient_scores_full(self) -> None:
        profile = UserProfile(disliked_ingredients=["anchovies"])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="tomatoes", quantity=400, unit="g", raw="400g tomatoes"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_dislikes(recipe) == 1.0


# ------------------------------------------------------------------
# Cuisine scoring
# ------------------------------------------------------------------


class TestCuisineScoring:
    def test_italian_recipe_matches_italian_preference(self) -> None:
        profile = UserProfile(cuisine_preferences=["italian"])
        recipe = _make_recipe(
            title="Spaghetti Bolognese",
            ingredients=[
                Ingredient(name="pasta", quantity=300, unit="g", raw="300g pasta"),
                Ingredient(name="mozzarella", quantity=100, unit="g", raw="100g mozzarella"),
            ],
        )
        recommender = RecipeRecommender(profile)
        score = recommender._score_cuisine(recipe)
        assert score > 0.5

    def test_no_cuisine_preferences_returns_neutral(self) -> None:
        profile = UserProfile(cuisine_preferences=[])
        recipe = _make_recipe(title="Test")
        recommender = RecipeRecommender(profile)
        assert recommender._score_cuisine(recipe) == 0.5

    def test_cuisine_name_in_title(self) -> None:
        profile = UserProfile(cuisine_preferences=["thai"])
        recipe = _make_recipe(title="Thai Green Curry")
        recommender = RecipeRecommender(profile)
        assert recommender._score_cuisine(recipe) == 1.0


# ------------------------------------------------------------------
# Variety scoring
# ------------------------------------------------------------------


class TestVarietyScoring:
    @patch("autogroceries.recommender.engine.list_plans", return_value=[])
    def test_no_plans_scores_full(self, _mock: object) -> None:
        profile = UserProfile()
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="chicken", quantity=500, unit="g", raw="500g chicken"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_variety(recipe) == 1.0


# ------------------------------------------------------------------
# Nutrition scoring
# ------------------------------------------------------------------


class TestNutritionScoring:
    def test_perfect_match(self) -> None:
        profile = UserProfile(
            daily_calories=2100,
            daily_protein_g=150,
            daily_carbs_g=240,
            daily_fat_g=60,
        )
        recipe = _make_recipe(
            nutrition=Nutrition(
                calories=700, protein_g=50, carbs_g=80, fat_g=20,
            ),
        )
        recommender = RecipeRecommender(profile)
        score = recommender._score_nutrition(recipe)
        assert score > 0.9

    def test_no_nutrition_data_returns_neutral(self) -> None:
        profile = UserProfile(daily_calories=2000)
        recipe = _make_recipe(nutrition=None)
        recommender = RecipeRecommender(profile)
        assert recommender._score_nutrition(recipe) == 0.5

    def test_no_targets_returns_neutral(self) -> None:
        profile = UserProfile()
        recipe = _make_recipe(
            nutrition=Nutrition(calories=500),
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_nutrition(recipe) == 0.5


# ------------------------------------------------------------------
# Pantry scoring
# ------------------------------------------------------------------


class TestPantryScoring:
    def test_pantry_match_boosts_score(self) -> None:
        profile = UserProfile(
            pantry=[PantryItem(name="rice"), PantryItem(name="soy sauce")],
        )
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="rice", quantity=200, unit="g", raw="200g rice"),
                Ingredient(name="soy sauce", quantity=2, unit="tbsp", raw="2 tbsp soy sauce"),
                Ingredient(name="chicken", quantity=300, unit="g", raw="300g chicken"),
            ],
        )
        recommender = RecipeRecommender(profile)
        score = recommender._score_pantry(recipe)
        assert score > 0.5

    def test_empty_pantry_returns_neutral(self) -> None:
        profile = UserProfile(pantry=[])
        recipe = _make_recipe(
            ingredients=[
                Ingredient(name="rice", quantity=200, unit="g", raw="200g rice"),
            ],
        )
        recommender = RecipeRecommender(profile)
        assert recommender._score_pantry(recipe) == 0.5


# ------------------------------------------------------------------
# Overall ranking
# ------------------------------------------------------------------


class TestOverallRanking:
    @patch("autogroceries.recommender.engine.list_plans", return_value=[])
    def test_recommend_returns_correct_count(self, _mock: object) -> None:
        profile = UserProfile()
        recipes = [_make_recipe(id=f"r{i}") for i in range(10)]
        recommender = RecipeRecommender(profile)
        results = recommender.recommend(recipes, count=3)
        assert len(results) == 3

    @patch("autogroceries.recommender.engine.list_plans", return_value=[])
    def test_recommend_sorted_by_total_score(self, _mock: object) -> None:
        profile = UserProfile()
        recipes = [_make_recipe(id=f"r{i}") for i in range(5)]
        recommender = RecipeRecommender(profile)
        results = recommender.recommend(recipes, count=5)
        scores = [sr.score.total for sr in results]
        assert scores == sorted(scores, reverse=True)

    @patch("autogroceries.recommender.engine.list_plans", return_value=[])
    def test_dietary_violation_ranked_last(self, _mock: object) -> None:
        """A recipe that violates dietary restrictions should rank below compatible ones."""
        profile = UserProfile(dietary_restrictions=["vegetarian"])
        veggie = _make_recipe(
            id="veggie",
            title="Veggie Pasta",
            ingredients=[
                Ingredient(name="pasta", quantity=200, unit="g", raw="200g pasta"),
            ],
        )
        meat = _make_recipe(
            id="meat",
            title="Chicken Stir Fry",
            ingredients=[
                Ingredient(name="chicken", quantity=500, unit="g", raw="500g chicken"),
            ],
        )
        recommender = RecipeRecommender(profile)
        results = recommender.recommend([meat, veggie], count=2)
        assert results[0].recipe.id == "veggie"
        assert results[1].recipe.id == "meat"


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------


class TestCloseness:
    def test_exact_match(self) -> None:
        assert _closeness(100.0, 100.0) == 1.0

    def test_double_target(self) -> None:
        assert _closeness(200.0, 100.0) == 0.0

    def test_half_target(self) -> None:
        assert _closeness(50.0, 100.0) == 0.5

    def test_zero_target(self) -> None:
        assert _closeness(50.0, 0.0) == 0.5
