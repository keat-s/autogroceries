"""Pydantic models for API request/response types."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Ingredients / Nutrition
# ---------------------------------------------------------------------------


class IngredientSchema(BaseModel):
    """A single recipe ingredient."""

    name: str
    quantity: float | None = None
    unit: str | None = None
    raw: str


class NutritionSchema(BaseModel):
    """Nutritional information per serving."""

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fibre_g: float | None = None
    sugar_g: float | None = None
    salt_g: float | None = None


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


class RecipeSchema(BaseModel):
    """Full recipe response."""

    id: str
    title: str
    source: str
    url: str
    servings: int | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    ingredients: list[IngredientSchema] = []
    instructions: list[str] = []
    nutrition: NutritionSchema | None = None


class ScrapeRequest(BaseModel):
    """Request body for scraping a recipe from a URL."""

    url: str
    source: str | None = None


class SearchRequest(BaseModel):
    """Request body for searching recipes."""

    query: str
    source: str


# ---------------------------------------------------------------------------
# Meal Plans
# ---------------------------------------------------------------------------


class MealSchema(BaseModel):
    """A meal entry referencing a recipe."""

    recipe_id: str
    servings: int


class DayPlanSchema(BaseModel):
    """Meals planned for a single day."""

    date: str
    meals: list[MealSchema] = []


class MealPlanSchema(BaseModel):
    """A weekly (or multi-day) meal plan."""

    name: str
    days: list[DayPlanSchema] = []


class CreatePlanRequest(BaseModel):
    """Request body for creating a new plan."""

    name: str
    start_date: str | None = None
    num_days: int = 7


class AddMealRequest(BaseModel):
    """Request body for adding a meal to a plan."""

    date: str
    recipe_id: str
    servings: int = 2


class RemoveMealRequest(BaseModel):
    """Request body for removing a meal from a plan."""

    date: str
    recipe_id: str


class ShoppingListResponse(BaseModel):
    """Shopping list response."""

    plan_name: str
    items: dict[str, int]


class NutritionDaySchema(BaseModel):
    """Nutrition totals for a single day."""

    date: str
    nutrition: NutritionSchema


class PlanNutritionResponse(BaseModel):
    """Nutrition breakdown for a plan."""

    plan_name: str
    days: list[NutritionDaySchema]


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------


class PantryItemSchema(BaseModel):
    """An item in the user's pantry."""

    name: str
    quantity: float | None = None
    unit: str | None = None
    category: str = "other"


class UserProfileSchema(BaseModel):
    """User profile for preferences and diet goals."""

    cuisine_preferences: list[str] = []
    dietary_restrictions: list[str] = []
    disliked_ingredients: list[str] = []
    household_size: int = 2
    daily_calories: int | None = None
    daily_protein_g: int | None = None
    daily_carbs_g: int | None = None
    daily_fat_g: int | None = None
    weight_goal: str | None = None
    pantry: list[PantryItemSchema] = []
    sundries: list[str] = []
    preferred_store: str | None = None


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


class ReminderSettingsSchema(BaseModel):
    """Reminder configuration."""

    enabled: bool = False
    reminder_day: str = "sunday"
    reminder_time: str = "09:00"
    auto_generate_list: bool = False
    notification_method: str = "console"
