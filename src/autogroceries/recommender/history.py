from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autogroceries.storage import DATA_DIR

HISTORY_PATH = DATA_DIR / "history.json"


@dataclass
class HistoryEntry:
    """A record of a cooked meal."""

    recipe_id: str
    date: str
    rating: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "recipe_id": self.recipe_id,
            "date": self.date,
        }
        if self.rating is not None:
            result["rating"] = self.rating
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEntry:
        return cls(
            recipe_id=data["recipe_id"],
            date=data["date"],
            rating=data.get("rating"),
        )


@dataclass
class CookingHistory:
    """Full cooking history for the user."""

    entries: list[HistoryEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CookingHistory:
        return cls(
            entries=[HistoryEntry.from_dict(e) for e in data.get("entries", [])],
        )


def load_history() -> CookingHistory:
    """Load cooking history from disk, or return empty history."""
    if not HISTORY_PATH.exists():
        return CookingHistory()
    data = json.loads(HISTORY_PATH.read_text())
    return CookingHistory.from_dict(data)


def save_history(history: CookingHistory) -> None:
    """Save cooking history to disk."""
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history.to_dict(), indent=2))


def record_meal(
    recipe_id: str, date: str, rating: int | None = None
) -> None:
    """Record a cooked meal in the history.

    Args:
        recipe_id: The recipe that was cooked.
        date: ISO date string (YYYY-MM-DD).
        rating: Optional 1-5 rating.
    """
    history = load_history()
    history.entries.append(
        HistoryEntry(recipe_id=recipe_id, date=date, rating=rating)
    )
    save_history(history)
