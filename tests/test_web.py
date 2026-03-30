"""Tests for the FastAPI web application."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from autogroceries.models import (
    DayPlan,
    Ingredient,
    Meal,
    MealPlan,
    Nutrition,
    Recipe,
)
from autogroceries.storage import save_plan, save_recipe
from autogroceries.web.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    """Redirect all storage directories to tmp_path for test isolation."""
    monkeypatch.setattr("autogroceries.storage.DATA_DIR", tmp_path)
    monkeypatch.setattr("autogroceries.storage.RECIPES_DIR", tmp_path / "recipes")
    monkeypatch.setattr("autogroceries.storage.PLANS_DIR", tmp_path / "plans")
    monkeypatch.setattr("autogroceries.storage.PROFILE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(
        "autogroceries.scheduler.reminders.REMINDERS_PATH",
        tmp_path / "reminders.json",
    )
    monkeypatch.setattr(
        "autogroceries.scheduler.reminders.DATA_DIR",
        tmp_path,
    )


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
            Ingredient(name="rice", quantity=300.0, unit="g", raw="300g rice"),
        ],
        instructions=["Step 1", "Step 2"],
        nutrition=Nutrition(calories=450, protein_g=35, carbs_g=50, fat_g=12),
    )


# ---------------------------------------------------------------------------
# Recipe endpoints
# ---------------------------------------------------------------------------


class TestRecipeEndpoints:
    def test_list_recipes_empty(self) -> None:
        resp = client.get("/api/recipes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_recipes(self) -> None:
        save_recipe(_make_recipe("a-recipe"))
        save_recipe(_make_recipe("b-recipe"))
        resp = client.get("/api/recipes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "a-recipe"

    def test_get_recipe(self) -> None:
        save_recipe(_make_recipe())
        resp = client.get("/api/recipes/test-recipe-mob")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Recipe"
        assert len(data["ingredients"]) == 2
        assert data["nutrition"]["calories"] == 450

    def test_get_recipe_not_found(self) -> None:
        resp = client.get("/api/recipes/nonexistent")
        assert resp.status_code == 404

    def test_delete_recipe(self) -> None:
        save_recipe(_make_recipe())
        resp = client.delete("/api/recipes/test-recipe-mob")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "test-recipe-mob"

        # Confirm it is gone
        resp = client.get("/api/recipes/test-recipe-mob")
        assert resp.status_code == 404

    def test_delete_recipe_not_found(self) -> None:
        resp = client.delete("/api/recipes/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Plan endpoints
# ---------------------------------------------------------------------------


class TestPlanEndpoints:
    def test_list_plans_empty(self) -> None:
        resp = client.get("/api/plans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_plan(self) -> None:
        resp = client.post(
            "/api/plans",
            json={"name": "week-14", "start_date": "2026-03-30", "num_days": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "week-14"
        assert len(data["days"]) == 3
        assert data["days"][0]["date"] == "2026-03-30"

    def test_get_plan(self) -> None:
        save_plan(MealPlan(name="my-plan", days=[DayPlan(date="2026-03-30")]))
        resp = client.get("/api/plans/my-plan")
        assert resp.status_code == 200
        assert resp.json()["name"] == "my-plan"

    def test_get_plan_not_found(self) -> None:
        resp = client.get("/api/plans/nonexistent")
        assert resp.status_code == 404

    def test_add_meal(self) -> None:
        save_plan(MealPlan(name="p1", days=[DayPlan(date="2026-03-30")]))
        resp = client.post(
            "/api/plans/p1/meals",
            json={"date": "2026-03-30", "recipe_id": "test-recipe", "servings": 4},
        )
        assert resp.status_code == 200
        meals = resp.json()["days"][0]["meals"]
        assert len(meals) == 1
        assert meals[0]["recipe_id"] == "test-recipe"

    def test_remove_meal(self) -> None:
        save_plan(
            MealPlan(
                name="p2",
                days=[DayPlan(date="2026-03-30", meals=[Meal(recipe_id="r1", servings=2)])],
            )
        )
        resp = client.request(
            "DELETE",
            "/api/plans/p2/meals",
            json={"date": "2026-03-30", "recipe_id": "r1"},
        )
        assert resp.status_code == 200
        assert resp.json()["days"][0]["meals"] == []

    def test_shopping_list(self) -> None:
        save_recipe(_make_recipe("r1"))
        save_plan(
            MealPlan(
                name="shop-plan",
                days=[DayPlan(date="2026-03-30", meals=[Meal(recipe_id="r1", servings=4)])],
            )
        )
        resp = client.get("/api/plans/shop-plan/shopping-list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_name"] == "shop-plan"
        assert len(data["items"]) > 0

    def test_nutrition(self) -> None:
        save_recipe(_make_recipe("r1"))
        save_plan(
            MealPlan(
                name="nut-plan",
                days=[DayPlan(date="2026-03-30", meals=[Meal(recipe_id="r1", servings=4)])],
            )
        )
        resp = client.get("/api/plans/nut-plan/nutrition")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_name"] == "nut-plan"
        assert len(data["days"]) == 1
        assert data["days"][0]["nutrition"]["calories"] == 450


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------


class TestProfileEndpoints:
    def test_get_default_profile(self) -> None:
        resp = client.get("/api/profile")
        assert resp.status_code == 200
        assert resp.json()["household_size"] == 2

    def test_update_profile(self) -> None:
        resp = client.put(
            "/api/profile",
            json={
                "household_size": 4,
                "preferred_store": "waitrose",
                "cuisine_preferences": ["italian", "thai"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["household_size"] == 4
        assert data["preferred_store"] == "waitrose"

        # Verify persistence
        resp2 = client.get("/api/profile")
        assert resp2.json()["household_size"] == 4


# ---------------------------------------------------------------------------
# Reminder endpoints
# ---------------------------------------------------------------------------


class TestReminderEndpoints:
    def test_get_default_reminders(self) -> None:
        resp = client.get("/api/reminders")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["reminder_day"] == "sunday"

    def test_update_reminders(self) -> None:
        resp = client.put(
            "/api/reminders",
            json={
                "enabled": True,
                "reminder_day": "saturday",
                "reminder_time": "10:30",
                "auto_generate_list": True,
                "notification_method": "console",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["reminder_day"] == "saturday"

        # Verify persistence
        resp2 = client.get("/api/reminders")
        assert resp2.json()["enabled"] is True
