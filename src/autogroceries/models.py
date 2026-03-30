from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Ingredient:
    """A single recipe ingredient with parsed components."""

    name: str
    quantity: float | None
    unit: str | None
    raw: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Ingredient:
        return cls(
            name=data["name"],
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            raw=data["raw"],
        )


@dataclass
class Recipe:
    """A scraped recipe."""

    id: str
    title: str
    source: str
    url: str
    servings: int | None
    prep_time: int | None
    cook_time: int | None
    ingredients: list[Ingredient]
    instructions: list[str]
    nutrition: Nutrition | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "servings": self.servings,
            "prep_time": self.prep_time,
            "cook_time": self.cook_time,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "instructions": self.instructions,
        }
        if self.nutrition:
            result["nutrition"] = self.nutrition.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        nutrition = None
        if "nutrition" in data:
            nutrition = Nutrition.from_dict(data["nutrition"])
        return cls(
            id=data["id"],
            title=data["title"],
            source=data["source"],
            url=data["url"],
            servings=data.get("servings"),
            prep_time=data.get("prep_time"),
            cook_time=data.get("cook_time"),
            ingredients=[Ingredient.from_dict(i) for i in data["ingredients"]],
            instructions=data["instructions"],
            nutrition=nutrition,
        )

    @staticmethod
    def make_id(title: str, source: str) -> str:
        """Generate a slug ID from title and source."""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return f"{slug}-{source}"


@dataclass
class Nutrition:
    """Nutritional information per serving."""

    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fibre_g: float | None = None
    sugar_g: float | None = None
    salt_g: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Nutrition:
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})


@dataclass
class PantryItem:
    """An item currently in the user's pantry/cupboard."""

    name: str
    quantity: float | None = None
    unit: str | None = None
    category: str = "other"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "unit": self.unit,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PantryItem:
        return cls(
            name=data["name"],
            quantity=data.get("quantity"),
            unit=data.get("unit"),
            category=data.get("category", "other"),
        )


@dataclass
class UserProfile:
    """User preferences, diet goals, and pantry state."""

    # Cuisine preferences (e.g. ["italian", "indian", "thai"])
    cuisine_preferences: list[str] = field(default_factory=list)
    # Dietary restrictions (e.g. ["vegetarian", "gluten-free", "dairy-free"])
    dietary_restrictions: list[str] = field(default_factory=list)
    # Disliked ingredients (e.g. ["mushrooms", "anchovies"])
    disliked_ingredients: list[str] = field(default_factory=list)
    # Household size for default servings
    household_size: int = 2
    # Daily macro/nutrition targets
    daily_calories: int | None = None
    daily_protein_g: int | None = None
    daily_carbs_g: int | None = None
    daily_fat_g: int | None = None
    # Weight goal: "lose", "maintain", or "gain"
    weight_goal: str | None = None
    # Pantry inventory
    pantry: list[PantryItem] = field(default_factory=list)
    # Sundries — staples to keep stocked (e.g. coffee, sugar, spices)
    sundries: list[str] = field(default_factory=list)
    # Preferred stores
    preferred_store: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cuisine_preferences": self.cuisine_preferences,
            "dietary_restrictions": self.dietary_restrictions,
            "disliked_ingredients": self.disliked_ingredients,
            "household_size": self.household_size,
            "daily_calories": self.daily_calories,
            "daily_protein_g": self.daily_protein_g,
            "daily_carbs_g": self.daily_carbs_g,
            "daily_fat_g": self.daily_fat_g,
            "weight_goal": self.weight_goal,
            "pantry": [p.to_dict() for p in self.pantry],
            "sundries": self.sundries,
            "preferred_store": self.preferred_store,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        return cls(
            cuisine_preferences=data.get("cuisine_preferences", []),
            dietary_restrictions=data.get("dietary_restrictions", []),
            disliked_ingredients=data.get("disliked_ingredients", []),
            household_size=data.get("household_size", 2),
            daily_calories=data.get("daily_calories"),
            daily_protein_g=data.get("daily_protein_g"),
            daily_carbs_g=data.get("daily_carbs_g"),
            daily_fat_g=data.get("daily_fat_g"),
            weight_goal=data.get("weight_goal"),
            pantry=[PantryItem.from_dict(p) for p in data.get("pantry", [])],
            sundries=data.get("sundries", []),
            preferred_store=data.get("preferred_store"),
        )


@dataclass
class Meal:
    """A meal entry in a plan, referencing a recipe."""

    recipe_id: str
    servings: int

    def to_dict(self) -> dict[str, Any]:
        return {"recipe_id": self.recipe_id, "servings": self.servings}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Meal:
        return cls(recipe_id=data["recipe_id"], servings=data["servings"])


@dataclass
class DayPlan:
    """Meals planned for a single day."""

    date: str
    meals: list[Meal] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "meals": [m.to_dict() for m in self.meals],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DayPlan:
        return cls(
            date=data["date"],
            meals=[Meal.from_dict(m) for m in data["meals"]],
        )


@dataclass
class MealPlan:
    """A weekly (or multi-day) meal plan."""

    name: str
    days: list[DayPlan] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "days": [d.to_dict() for d in self.days],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MealPlan:
        return cls(
            name=data["name"],
            days=[DayPlan.from_dict(d) for d in data["days"]],
        )
