from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from autogroceries.models import MealPlan, Nutrition, UserProfile
from autogroceries.storage import load_recipe


def generate_shopping_list(
    plan: MealPlan,
    profile: UserProfile | None = None,
) -> dict[str, int]:
    """Generate a consolidated shopping list from a meal plan.

    Loads each recipe, deduplicates by normalised ingredient name,
    subtracts items already in the pantry, and adds sundries that
    need restocking.

    Args:
        plan: A meal plan with recipes assigned to days.
        profile: Optional user profile for pantry/sundries awareness.

    Returns:
        Dict mapping ingredient names to the number of items to add to basket.
    """
    ingredient_count: defaultdict[str, int] = defaultdict(int)

    for day in plan.days:
        for meal in day.meals:
            recipe = load_recipe(meal.recipe_id)
            for ingredient in recipe.ingredients:
                normalised = _normalise_name(ingredient.name)
                if normalised:
                    ingredient_count[normalised] += 1

    # Subtract pantry items the user already has
    if profile:
        pantry_names = {_normalise_name(p.name) for p in profile.pantry}
        for pantry_item in pantry_names:
            ingredient_count.pop(pantry_item, None)

        # Add sundries that aren't already in the list or pantry
        for sundry in profile.sundries:
            normalised = _normalise_name(sundry)
            if normalised not in ingredient_count and normalised not in pantry_names:
                ingredient_count[normalised] = 1

    return dict(ingredient_count)


def calculate_plan_nutrition(plan: MealPlan) -> dict[str, Nutrition]:
    """Calculate daily nutrition totals for a meal plan.

    Args:
        plan: A meal plan.

    Returns:
        Dict mapping date strings to aggregated Nutrition for that day.
    """
    daily: dict[str, Nutrition] = {}

    for day in plan.days:
        totals = Nutrition()
        for meal in day.meals:
            recipe = load_recipe(meal.recipe_id)
            if not recipe.nutrition:
                continue
            scale = meal.servings / (recipe.servings or meal.servings)
            n = recipe.nutrition
            totals.calories = (totals.calories or 0) + (n.calories or 0) * scale
            totals.protein_g = (totals.protein_g or 0) + (n.protein_g or 0) * scale
            totals.carbs_g = (totals.carbs_g or 0) + (n.carbs_g or 0) * scale
            totals.fat_g = (totals.fat_g or 0) + (n.fat_g or 0) * scale
            totals.fibre_g = (totals.fibre_g or 0) + (n.fibre_g or 0) * scale
        daily[day.date] = totals

    return daily


def write_shopping_csv(shopping_list: dict[str, int], path: Path) -> None:
    """Write a shopping list as CSV compatible with autogroceries shop.

    Args:
        shopping_list: Dict of ingredient name to quantity.
        path: Output CSV path.
    """
    with open(path, "w") as f:
        for ingredient, quantity in sorted(shopping_list.items()):
            f.write(f"{ingredient},{quantity}\n")


def _normalise_name(name: str) -> str:
    """Normalise an ingredient name for deduplication.

    Lowercases, strips common adjectives, removes trailing 's' for
    basic plural handling.
    """
    text = name.lower().strip()

    # Remove common adjectives that don't affect shopping
    remove_words = {
        "fresh", "dried", "ground", "large", "small", "medium",
        "finely", "roughly", "thinly", "chopped", "diced", "minced",
        "sliced", "grated", "crushed", "frozen", "organic", "free-range",
        "boneless", "skinless", "ripe", "raw", "cooked", "warm", "cold",
        "hot", "extra", "virgin", "whole", "half", "flat-leaf",
    }
    words = text.split()
    words = [w for w in words if w not in remove_words]
    text = " ".join(words)

    # Strip trailing 's' for simple plural handling (but not 'ss' like 'grass')
    if text.endswith("s") and not text.endswith("ss"):
        text = text[:-1]

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text
