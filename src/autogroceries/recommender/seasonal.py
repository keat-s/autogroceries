from __future__ import annotations

from datetime import date

SEASONAL_INGREDIENTS: dict[str, list[str]] = {
    "spring": [
        "asparagus", "rhubarb", "new potatoes", "lamb", "peas",
        "radish", "watercress", "spinach", "spring onion", "mint",
        "sorrel", "purple sprouting broccoli", "jersey royals",
    ],
    "summer": [
        "tomatoes", "courgette", "strawberries", "corn", "runner beans",
        "cucumber", "aubergine", "peppers", "broad beans", "raspberries",
        "blueberries", "cherries", "basil", "new potatoes", "lettuce",
    ],
    "autumn": [
        "pumpkin", "squash", "mushrooms", "apple", "blackberries",
        "pear", "plum", "sweetcorn", "beetroot", "kale",
        "celeriac", "parsnip", "fig", "damson", "chestnut",
    ],
    "winter": [
        "parsnip", "swede", "sprouts", "leek", "cabbage",
        "cauliflower", "turnip", "kale", "beetroot", "celery",
        "red cabbage", "brussels sprouts", "clementine", "cranberry",
    ],
}


def get_current_season(today: date | None = None) -> str:
    """Return the UK season for the given date (or today).

    Spring: March-May, Summer: June-August,
    Autumn: September-November, Winter: December-February.
    """
    month = (today or date.today()).month
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def get_seasonal_ingredients(today: date | None = None) -> list[str]:
    """Return seasonal ingredients for the current UK season."""
    season = get_current_season(today)
    return SEASONAL_INGREDIENTS[season]
