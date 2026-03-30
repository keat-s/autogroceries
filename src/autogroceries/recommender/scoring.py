from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autogroceries.models import Recipe


@dataclass
class RecipeScore:
    """Score breakdown for a single recipe across all dimensions."""

    recipe_id: str
    dietary: float
    dislikes: float
    cuisine: float
    nutrition: float
    variety: float
    seasonal: float
    pantry: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "dietary": self.dietary,
            "dislikes": self.dislikes,
            "cuisine": self.cuisine,
            "nutrition": self.nutrition,
            "variety": self.variety,
            "seasonal": self.seasonal,
            "pantry": self.pantry,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecipeScore:
        return cls(
            recipe_id=data["recipe_id"],
            dietary=data["dietary"],
            dislikes=data["dislikes"],
            cuisine=data["cuisine"],
            nutrition=data["nutrition"],
            variety=data["variety"],
            seasonal=data["seasonal"],
            pantry=data["pantry"],
            total=data["total"],
        )


@dataclass
class ScoredRecipe:
    """A recipe paired with its score breakdown."""

    recipe: Recipe
    score: RecipeScore

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe": self.recipe.to_dict(),
            "score": self.score.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoredRecipe:
        return cls(
            recipe=Recipe.from_dict(data["recipe"]),
            score=RecipeScore.from_dict(data["score"]),
        )
