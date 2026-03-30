from __future__ import annotations

import json
from pathlib import Path

from autogroceries.exceptions import PlanNotFoundError, RecipeNotFoundError
from autogroceries.models import MealPlan, Recipe, UserProfile

DATA_DIR = Path.home() / ".autogroceries"
RECIPES_DIR = DATA_DIR / "recipes"
PLANS_DIR = DATA_DIR / "plans"


def _ensure_dirs() -> None:
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)


def save_recipe(recipe: Recipe) -> Path:
    """Save a recipe to disk as JSON."""
    _ensure_dirs()
    path = RECIPES_DIR / f"{recipe.id}.json"
    path.write_text(json.dumps(recipe.to_dict(), indent=2))
    return path


def load_recipe(recipe_id: str) -> Recipe:
    """Load a recipe by its ID."""
    path = RECIPES_DIR / f"{recipe_id}.json"
    if not path.exists():
        raise RecipeNotFoundError(f"Recipe '{recipe_id}' not found.")
    data = json.loads(path.read_text())
    return Recipe.from_dict(data)


def list_recipes() -> list[Recipe]:
    """List all saved recipes."""
    _ensure_dirs()
    recipes = []
    for path in sorted(RECIPES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        recipes.append(Recipe.from_dict(data))
    return recipes


def delete_recipe(recipe_id: str) -> None:
    """Delete a recipe by its ID."""
    path = RECIPES_DIR / f"{recipe_id}.json"
    if not path.exists():
        raise RecipeNotFoundError(f"Recipe '{recipe_id}' not found.")
    path.unlink()


def save_plan(plan: MealPlan) -> Path:
    """Save a meal plan to disk as JSON."""
    _ensure_dirs()
    path = PLANS_DIR / f"{plan.name}.json"
    path.write_text(json.dumps(plan.to_dict(), indent=2))
    return path


def load_plan(name: str) -> MealPlan:
    """Load a meal plan by name."""
    path = PLANS_DIR / f"{name}.json"
    if not path.exists():
        raise PlanNotFoundError(f"Plan '{name}' not found.")
    data = json.loads(path.read_text())
    return MealPlan.from_dict(data)


def list_plans() -> list[MealPlan]:
    """List all saved meal plans."""
    _ensure_dirs()
    plans = []
    for path in sorted(PLANS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        plans.append(MealPlan.from_dict(data))
    return plans


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

PROFILE_PATH = DATA_DIR / "profile.json"


def save_profile(profile: UserProfile) -> Path:
    """Save user profile to disk."""
    _ensure_dirs()
    PROFILE_PATH.write_text(json.dumps(profile.to_dict(), indent=2))
    return PROFILE_PATH


def load_profile() -> UserProfile:
    """Load user profile, or return defaults if none exists."""
    if not PROFILE_PATH.exists():
        return UserProfile()
    data = json.loads(PROFILE_PATH.read_text())
    return UserProfile.from_dict(data)
