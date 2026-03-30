from __future__ import annotations

from datetime import date, timedelta

from autogroceries.models import DayPlan, Meal, MealPlan


def create_plan(name: str, start_date: date | None = None, num_days: int = 7) -> MealPlan:
    """Create an empty meal plan.

    Args:
        name: Name for the plan (e.g. "week-14").
        start_date: First day of the plan. Defaults to today.
        num_days: Number of days to plan. Defaults to 7.

    Returns:
        A new MealPlan with empty days.
    """
    start = start_date or date.today()
    days = [
        DayPlan(date=(start + timedelta(days=i)).isoformat())
        for i in range(num_days)
    ]
    return MealPlan(name=name, days=days)


def add_meal(plan: MealPlan, target_date: str, recipe_id: str, servings: int = 2) -> MealPlan:
    """Add a meal to a specific day in the plan.

    Args:
        plan: The meal plan to modify.
        target_date: ISO date string (YYYY-MM-DD).
        recipe_id: ID of the recipe to add.
        servings: Number of servings to prepare.

    Returns:
        The modified plan.
    """
    for day in plan.days:
        if day.date == target_date:
            day.meals.append(Meal(recipe_id=recipe_id, servings=servings))
            return plan

    # Date not in plan — add a new day
    plan.days.append(
        DayPlan(date=target_date, meals=[Meal(recipe_id=recipe_id, servings=servings)])
    )
    plan.days.sort(key=lambda d: d.date)
    return plan


def remove_meal(plan: MealPlan, target_date: str, recipe_id: str) -> MealPlan:
    """Remove a meal from a specific day in the plan.

    Args:
        plan: The meal plan to modify.
        target_date: ISO date string (YYYY-MM-DD).
        recipe_id: ID of the recipe to remove.

    Returns:
        The modified plan.
    """
    for day in plan.days:
        if day.date == target_date:
            day.meals = [m for m in day.meals if m.recipe_id != recipe_id]
            break
    return plan
