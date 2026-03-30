from datetime import date

from autogroceries.models import Meal
from autogroceries.planner.planner import add_meal, create_plan, remove_meal


class TestCreatePlan:
    def test_default_7_days(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30))
        assert len(plan.days) == 7
        assert plan.days[0].date == "2026-03-30"
        assert plan.days[6].date == "2026-04-05"

    def test_custom_days(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30), num_days=3)
        assert len(plan.days) == 3

    def test_empty_days(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30))
        for day in plan.days:
            assert day.meals == []


class TestAddMeal:
    def test_add_to_existing_day(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30))
        add_meal(plan, "2026-03-30", "chicken-tikka-mobkitchen", servings=4)
        assert len(plan.days[0].meals) == 1
        assert plan.days[0].meals[0].recipe_id == "chicken-tikka-mobkitchen"
        assert plan.days[0].meals[0].servings == 4

    def test_add_to_new_day(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30), num_days=1)
        add_meal(plan, "2026-04-10", "recipe-x", servings=2)
        assert len(plan.days) == 2
        assert plan.days[1].date == "2026-04-10"

    def test_multiple_meals_per_day(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30))
        add_meal(plan, "2026-03-30", "recipe-a")
        add_meal(plan, "2026-03-30", "recipe-b")
        assert len(plan.days[0].meals) == 2


class TestRemoveMeal:
    def test_remove_existing(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30))
        add_meal(plan, "2026-03-30", "recipe-a")
        add_meal(plan, "2026-03-30", "recipe-b")
        remove_meal(plan, "2026-03-30", "recipe-a")
        assert len(plan.days[0].meals) == 1
        assert plan.days[0].meals[0].recipe_id == "recipe-b"

    def test_remove_nonexistent_is_noop(self) -> None:
        plan = create_plan("test", start_date=date(2026, 3, 30))
        remove_meal(plan, "2026-03-30", "nonexistent")
        assert plan.days[0].meals == []
