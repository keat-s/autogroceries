from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from autogroceries.recommender.history import (
    CookingHistory,
    HistoryEntry,
    load_history,
    record_meal,
    save_history,
)


class TestHistoryEntry:
    def test_round_trip(self) -> None:
        entry = HistoryEntry(recipe_id="pasta-bake-mob", date="2026-03-20", rating=4)
        assert HistoryEntry.from_dict(entry.to_dict()) == entry

    def test_round_trip_no_rating(self) -> None:
        entry = HistoryEntry(recipe_id="pasta-bake-mob", date="2026-03-20")
        data = entry.to_dict()
        assert "rating" not in data
        assert HistoryEntry.from_dict(data) == entry


class TestCookingHistory:
    def test_round_trip(self) -> None:
        history = CookingHistory(
            entries=[
                HistoryEntry(recipe_id="r1", date="2026-03-01", rating=5),
                HistoryEntry(recipe_id="r2", date="2026-03-02"),
            ],
        )
        assert CookingHistory.from_dict(history.to_dict()) == history

    def test_empty_history(self) -> None:
        history = CookingHistory()
        data = history.to_dict()
        assert data == {"entries": []}
        assert CookingHistory.from_dict(data) == history


class TestLoadSaveHistory:
    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "history.json"
        with patch("autogroceries.recommender.history.HISTORY_PATH", fake_path):
            history = load_history()
        assert history.entries == []

    def test_save_and_load(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "history.json"
        history = CookingHistory(
            entries=[
                HistoryEntry(recipe_id="test-recipe", date="2026-03-25", rating=3),
            ],
        )
        with patch("autogroceries.recommender.history.HISTORY_PATH", fake_path):
            save_history(history)
            loaded = load_history()
        assert loaded == history

    def test_record_meal_appends(self, tmp_path: Path) -> None:
        fake_path = tmp_path / "history.json"
        with patch("autogroceries.recommender.history.HISTORY_PATH", fake_path):
            record_meal("recipe-a", "2026-03-20", rating=5)
            record_meal("recipe-b", "2026-03-21")
            history = load_history()
        assert len(history.entries) == 2
        assert history.entries[0].recipe_id == "recipe-a"
        assert history.entries[0].rating == 5
        assert history.entries[1].recipe_id == "recipe-b"
        assert history.entries[1].rating is None
