from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import click
from dotenv import load_dotenv

from autogroceries.exceptions import MissingCredentialsError, RecipeScrapeError
from autogroceries.models import PantryItem, Recipe, UserProfile
from autogroceries.planner.consolidator import (
    calculate_plan_nutrition,
    generate_shopping_list,
    write_shopping_csv,
)
from autogroceries.planner.planner import add_meal, create_plan
from autogroceries.scraper.exa_scraper import ExaScraper
from autogroceries.scraper.firecrawl_scraper import FirecrawlScraper
from autogroceries.scraper.mobkitchen import MobKitchenScraper
from autogroceries.scraper.sainsburys_recipes import SainsburysScraper
from autogroceries.scraper.universal import UniversalScraper
from autogroceries.scraper.waitrose_recipes import WaitroseScraper
from autogroceries.shopper.sainsburys import SainsburysShopper
from autogroceries.shopper.waitrose import WaitroseShopper
from autogroceries.storage import (
    delete_recipe,
    list_plans,
    list_recipes,
    load_plan,
    load_profile,
    save_plan,
    save_profile,
    save_recipe,
)

SHOPPERS = {
    "sainsburys": SainsburysShopper,
    "waitrose": WaitroseShopper,
}

SCRAPERS = {
    "mobkitchen": MobKitchenScraper,
    "waitrose": WaitroseScraper,
    "sainsburys": SainsburysScraper,
    "firecrawl": FirecrawlScraper,
    "exa": ExaScraper,
    "universal": UniversalScraper,
}

SOURCE_DOMAINS = {
    "mob.co.uk": "mobkitchen",
    "mobkitchen.co.uk": "mobkitchen",
    "waitrose.com": "waitrose",
    "sainsburys.co.uk": "sainsburys",
}


@click.group(
    help="""
    Automate your recipe planning and grocery shopping.

    Scrape recipes, plan your weekly meals, generate shopping lists,
    and automate adding items to your online basket.
    """
)
def autogroceries_cli() -> None:
    load_dotenv()


# ---------------------------------------------------------------------------
# shop command (existing functionality)
# ---------------------------------------------------------------------------


@autogroceries_cli.command(
    help="""
    Shop for ingredients using browser automation.

    Set [STORE]_USERNAME and [STORE]_PASSWORD in a .env file.
    """
)
@click.option(
    "--store",
    type=click.Choice(SHOPPERS.keys()),
    required=True,
    help="The store to shop at.",
)
@click.option(
    "--ingredients-path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to csv file (without header) in format 'ingredient,quantity'.",
)
@click.option(
    "--log-path",
    type=click.Path(path_type=Path),
    required=False,
    help="If provided, will output shopping log to this path.",
)
def shop(store: str, ingredients_path: Path, log_path: Path | None) -> None:
    store_username = f"{store.upper()}_USERNAME"
    store_password = f"{store.upper()}_PASSWORD"
    username = os.getenv(store_username)
    password = os.getenv(store_password)

    if not username or not password:
        raise MissingCredentialsError(
            f"{store_username} and {store_password} must be set as environment variables."
        )

    shopper = SHOPPERS[store](
        username=username,
        password=password,
        log_path=log_path,
    )

    shopper.shop(read_ingredients(ingredients_path))


# ---------------------------------------------------------------------------
# scrape command
# ---------------------------------------------------------------------------


@autogroceries_cli.command(
    help="Scrape a recipe from a URL or search for recipes."
)
@click.option("--url", default=None, help="Recipe URL to scrape.")
@click.option(
    "--source",
    type=click.Choice(SCRAPERS.keys()),
    default=None,
    help="Recipe source to search.",
)
@click.option("--search", "search_query", default=None, help="Search for recipes by keyword.")
def scrape(url: str | None, source: str | None, search_query: str | None) -> None:
    if url:
        _scrape_url(url, source)
    elif search_query and source:
        _search_and_pick(search_query, source)
    else:
        click.echo("Provide --url to scrape a recipe, or --search with --source to search.")


def _detect_source(url: str) -> str | None:
    """Detect the recipe source from a URL's domain."""
    for domain, src in SOURCE_DOMAINS.items():
        if domain in url:
            return src
    return None


def _scrape_url(url: str, source: str | None) -> None:
    """Scrape a single recipe URL and save it."""
    detected = source or _detect_source(url)
    if not detected:
        detected = "universal"

    scraper = SCRAPERS[detected]()

    # Login for Mob Kitchen premium
    if detected == "mobkitchen" and isinstance(scraper, MobKitchenScraper):
        scraper.login()

    try:
        recipe = scraper.scrape(url)
    except RecipeScrapeError as e:
        click.echo(f"Error: {e}")
        return

    path = save_recipe(recipe)
    click.echo(f"Saved: {recipe.title} ({recipe.id})")
    click.echo(f"  Source: {recipe.source}")
    click.echo(f"  Ingredients: {len(recipe.ingredients)}")
    click.echo(f"  File: {path}")


def _search_and_pick(query: str, source: str) -> None:
    """Search for recipes and let user pick which to scrape."""
    scraper = SCRAPERS[source]()

    if source == "mobkitchen" and isinstance(scraper, MobKitchenScraper):
        scraper.login()

    click.echo(f"Searching {source} for '{query}'...")
    results = scraper.search(query)

    if not results:
        click.echo("No recipes found.")
        return

    click.echo()
    for i, r in enumerate(results, 1):
        click.echo(f"  {i}. {r['title']}")

    click.echo()
    choices = click.prompt(
        "Enter recipe numbers to save (comma-separated, or 'q' to quit)",
        default="q",
    )
    if choices.lower() == "q":
        return

    for num_str in choices.split(","):
        try:
            idx = int(num_str.strip()) - 1
            if 0 <= idx < len(results):
                result = results[idx]
                click.echo(f"\nScraping: {result['title']}...")
                try:
                    recipe = scraper.scrape(result["url"])
                    save_recipe(recipe)
                    click.echo(f"  Saved: {recipe.id}")
                except RecipeScrapeError as e:
                    click.echo(f"  Error: {e}")
        except ValueError:
            continue


# ---------------------------------------------------------------------------
# recipes command
# ---------------------------------------------------------------------------


@autogroceries_cli.command(help="List or delete saved recipes.")
@click.option("--delete", "delete_id", default=None, help="Delete a recipe by ID.")
def recipes(delete_id: str | None) -> None:
    if delete_id:
        delete_recipe(delete_id)
        click.echo(f"Deleted: {delete_id}")
        return

    saved = list_recipes()
    if not saved:
        click.echo("No saved recipes. Use 'autogroceries scrape' to add some.")
        return

    click.echo(f"\nSaved recipes ({len(saved)}):\n")
    for recipe in saved:
        servings = f" | Serves {recipe.servings}" if recipe.servings else ""
        click.echo(f"  {recipe.id}")
        click.echo(f"    {recipe.title} [{recipe.source}]{servings}")


# ---------------------------------------------------------------------------
# plan command (interactive)
# ---------------------------------------------------------------------------


@autogroceries_cli.command(
    help="""
    Create and manage weekly meal plans.

    Run without options for interactive mode. Use flags for scriptable access.
    """
)
@click.option("--create", "plan_name", default=None, help="Create a new plan with this name.")
@click.option("--show", "show_plan", default=None, help="Show a meal plan.")
@click.option("--list", "list_all", is_flag=True, help="List all plans.")
@click.option(
    "--generate-list",
    "gen_plan",
    default=None,
    help="Generate shopping CSV from a plan.",
)
@click.option(
    "-o", "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output CSV path for generated shopping list.",
)
@click.option(
    "--add",
    nargs=3,
    default=None,
    metavar="PLAN DATE RECIPE_ID",
    help="Add a recipe to a plan: PLAN_NAME DATE RECIPE_ID",
)
def plan(
    plan_name: str | None,
    show_plan: str | None,
    list_all: bool,
    gen_plan: str | None,
    output: Path | None,
    add: tuple[str, str, str] | None,
) -> None:
    if list_all:
        _list_plans()
    elif show_plan:
        _show_plan(show_plan)
    elif gen_plan:
        _generate_list(gen_plan, output)
    elif add:
        _add_to_plan(add[0], add[1], add[2])
    elif plan_name:
        new_plan = create_plan(plan_name)
        save_plan(new_plan)
        click.echo(f"Created plan: {plan_name}")
        for day in new_plan.days:
            click.echo(f"  {day.date}")
    else:
        _interactive_plan()


def _list_plans() -> None:
    plans = list_plans()
    if not plans:
        click.echo("No meal plans. Use 'autogroceries plan' to create one.")
        return
    click.echo(f"\nMeal plans ({len(plans)}):\n")
    for p in plans:
        meal_count = sum(len(d.meals) for d in p.days)
        click.echo(f"  {p.name} — {len(p.days)} days, {meal_count} meals")


def _show_plan(name: str) -> None:
    p = load_plan(name)
    click.echo(f"\n{p.name}\n{'=' * len(p.name)}\n")
    for day in p.days:
        click.echo(f"  {day.date}:")
        if day.meals:
            for meal in day.meals:
                click.echo(f"    - {meal.recipe_id} (serves {meal.servings})")
        else:
            click.echo("    (no meals)")


def _generate_list(plan_name: str, output: Path | None) -> None:
    p = load_plan(plan_name)
    prof = load_profile()
    shopping_list = generate_shopping_list(p, profile=prof)

    if not shopping_list:
        click.echo("No ingredients — plan has no recipes assigned.")
        return

    out = output or Path(f"{plan_name}-shopping.csv")
    write_shopping_csv(shopping_list, out)

    click.echo(f"\nShopping list for '{plan_name}' ({len(shopping_list)} items):\n")
    for item, qty in sorted(shopping_list.items()):
        click.echo(f"  {item} x{qty}")
    click.echo(f"\nSaved to: {out}")

    # Show nutrition summary if available
    _show_nutrition_summary(p, prof)


def _add_to_plan(plan_name: str, target_date: str, recipe_id: str) -> None:
    p = load_plan(plan_name)
    servings = click.prompt("Servings", default=2, type=int)
    add_meal(p, target_date, recipe_id, servings)
    save_plan(p)
    click.echo(f"Added {recipe_id} to {plan_name} on {target_date}.")


def _interactive_plan() -> None:
    """Interactive meal planning flow."""
    click.echo("\n--- Weekly Meal Planner ---\n")

    # Plan name
    today = date.today()
    week_num = today.isocalendar()[1]
    default_name = f"week-{week_num}"
    plan_name = click.prompt("Plan name", default=default_name)

    # Check for existing plan
    try:
        existing = load_plan(plan_name)
        if click.confirm(f"Plan '{plan_name}' already exists. Continue editing it?"):
            meal_plan = existing
        else:
            return
    except Exception:
        meal_plan = create_plan(plan_name, start_date=today)

    # Load saved recipes
    saved = list_recipes()
    if not saved:
        click.echo("\nNo saved recipes! Scrape some first with 'autogroceries scrape'.")
        return

    click.echo(f"\nAvailable recipes ({len(saved)}):\n")
    for i, r in enumerate(saved, 1):
        click.echo(f"  {i}. {r.title} [{r.source}]")

    # Assign recipes to days
    click.echo()
    for day in meal_plan.days:
        day_label = day.date
        existing_meals = ", ".join(m.recipe_id for m in day.meals) if day.meals else "none"
        click.echo(f"{day_label} (current: {existing_meals})")

        choices = click.prompt(
            "  Recipe numbers (comma-separated, or Enter to skip)",
            default="",
            show_default=False,
        )
        if not choices.strip():
            continue

        for num_str in choices.split(","):
            try:
                idx = int(num_str.strip()) - 1
                if 0 <= idx < len(saved):
                    recipe = saved[idx]
                    servings = click.prompt(
                        f"    Servings for {recipe.title}",
                        default=recipe.servings or 2,
                        type=int,
                    )
                    from autogroceries.models import Meal

                    day.meals.append(Meal(recipe_id=recipe.id, servings=servings))
                    click.echo(f"    Added: {recipe.title}")
            except ValueError:
                continue

    save_plan(meal_plan)
    click.echo(f"\nPlan '{plan_name}' saved!")

    # Offer to generate shopping list
    if click.confirm("\nGenerate shopping list now?", default=True):
        prof = load_profile()
        shopping_list = generate_shopping_list(meal_plan, profile=prof)
        if shopping_list:
            out = Path(f"{plan_name}-shopping.csv")
            write_shopping_csv(shopping_list, out)
            click.echo(f"\nShopping list ({len(shopping_list)} items):\n")
            for item, qty in sorted(shopping_list.items()):
                click.echo(f"  {item} x{qty}")
            click.echo(f"\nSaved to: {out}")

            store = prof.preferred_store or "<store>"
            click.echo(
                f"\nRun 'autogroceries shop --store {store} "
                f"--ingredients-path {out}' to shop!"
            )

            _show_nutrition_summary(meal_plan, prof)
        else:
            click.echo("No ingredients to shop for.")


def _show_nutrition_summary(plan: object, prof: UserProfile) -> None:
    """Show daily nutrition vs targets if data is available."""
    from autogroceries.models import MealPlan

    if not isinstance(plan, MealPlan):
        return

    daily_nutrition = calculate_plan_nutrition(plan)
    has_data = any(
        (n.calories or 0) > 0 for n in daily_nutrition.values()
    )
    if not has_data:
        return

    click.echo("\n--- Daily Nutrition ---\n")
    for day_date, n in sorted(daily_nutrition.items()):
        cal = f"{n.calories:.0f}" if n.calories else "?"
        pro = f"{n.protein_g:.0f}g" if n.protein_g else "?"
        carb = f"{n.carbs_g:.0f}g" if n.carbs_g else "?"
        fat = f"{n.fat_g:.0f}g" if n.fat_g else "?"
        click.echo(f"  {day_date}: {cal} kcal | P:{pro} C:{carb} F:{fat}")

    if prof.daily_calories:
        click.echo(f"\n  Your target: {prof.daily_calories} kcal | "
                    f"P:{prof.daily_protein_g or '?'}g "
                    f"C:{prof.daily_carbs_g or '?'}g "
                    f"F:{prof.daily_fat_g or '?'}g")


# ---------------------------------------------------------------------------
# profile command
# ---------------------------------------------------------------------------


@autogroceries_cli.command(
    help="Set up or view your user profile (diet goals, cuisine preferences, pantry)."
)
@click.option("--show", "show_profile", is_flag=True, help="Show current profile.")
@click.option("--add-pantry", default=None, help="Add an item to your pantry.")
@click.option("--remove-pantry", default=None, help="Remove an item from your pantry.")
@click.option("--add-sundry", default=None, help="Add a sundry/staple to track.")
@click.option("--remove-sundry", default=None, help="Remove a sundry.")
def profile(
    show_profile: bool,
    add_pantry: str | None,
    remove_pantry: str | None,
    add_sundry: str | None,
    remove_sundry: str | None,
) -> None:
    prof = load_profile()

    if add_pantry:
        prof.pantry.append(PantryItem(name=add_pantry))
        save_profile(prof)
        click.echo(f"Added '{add_pantry}' to pantry.")
        return

    if remove_pantry:
        prof.pantry = [p for p in prof.pantry if p.name.lower() != remove_pantry.lower()]
        save_profile(prof)
        click.echo(f"Removed '{remove_pantry}' from pantry.")
        return

    if add_sundry:
        if add_sundry not in prof.sundries:
            prof.sundries.append(add_sundry)
            save_profile(prof)
        click.echo(f"Added '{add_sundry}' to sundries.")
        return

    if remove_sundry:
        prof.sundries = [s for s in prof.sundries if s.lower() != remove_sundry.lower()]
        save_profile(prof)
        click.echo(f"Removed '{remove_sundry}' from sundries.")
        return

    if show_profile:
        _display_profile(prof)
        return

    # Interactive setup
    _interactive_profile(prof)


def _display_profile(prof: UserProfile) -> None:
    click.echo("\n--- Your Profile ---\n")
    click.echo(f"  Household size: {prof.household_size}")
    click.echo(f"  Weight goal: {prof.weight_goal or 'not set'}")
    click.echo(f"  Preferred store: {prof.preferred_store or 'not set'}")

    if prof.cuisine_preferences:
        click.echo(f"  Cuisines: {', '.join(prof.cuisine_preferences)}")
    if prof.dietary_restrictions:
        click.echo(f"  Dietary: {', '.join(prof.dietary_restrictions)}")
    if prof.disliked_ingredients:
        click.echo(f"  Dislikes: {', '.join(prof.disliked_ingredients)}")

    if any([prof.daily_calories, prof.daily_protein_g, prof.daily_carbs_g, prof.daily_fat_g]):
        click.echo("\n  Daily targets:")
        if prof.daily_calories:
            click.echo(f"    Calories: {prof.daily_calories} kcal")
        if prof.daily_protein_g:
            click.echo(f"    Protein: {prof.daily_protein_g}g")
        if prof.daily_carbs_g:
            click.echo(f"    Carbs: {prof.daily_carbs_g}g")
        if prof.daily_fat_g:
            click.echo(f"    Fat: {prof.daily_fat_g}g")

    if prof.pantry:
        click.echo(f"\n  Pantry ({len(prof.pantry)} items):")
        for item in prof.pantry:
            click.echo(f"    - {item.name}")

    if prof.sundries:
        click.echo(f"\n  Sundries ({len(prof.sundries)} staples):")
        for s in prof.sundries:
            click.echo(f"    - {s}")


def _interactive_profile(prof: UserProfile) -> None:
    """Interactive profile setup."""
    click.echo("\n--- Profile Setup ---\n")

    prof.household_size = click.prompt(
        "Household size", default=prof.household_size, type=int
    )

    prof.weight_goal = click.prompt(
        "Weight goal (lose/maintain/gain)",
        default=prof.weight_goal or "maintain",
    )

    prof.preferred_store = click.prompt(
        "Preferred store (sainsburys/waitrose)",
        default=prof.preferred_store or "sainsburys",
    )

    cuisines = click.prompt(
        "Cuisine preferences (comma-separated, e.g. italian,indian,thai)",
        default=",".join(prof.cuisine_preferences) if prof.cuisine_preferences else "",
        show_default=False,
    )
    if cuisines.strip():
        prof.cuisine_preferences = [c.strip() for c in cuisines.split(",") if c.strip()]

    dietary = click.prompt(
        "Dietary restrictions (comma-separated, e.g. vegetarian,gluten-free)",
        default=",".join(prof.dietary_restrictions) if prof.dietary_restrictions else "",
        show_default=False,
    )
    if dietary.strip():
        prof.dietary_restrictions = [d.strip() for d in dietary.split(",") if d.strip()]

    dislikes = click.prompt(
        "Disliked ingredients (comma-separated)",
        default=",".join(prof.disliked_ingredients) if prof.disliked_ingredients else "",
        show_default=False,
    )
    if dislikes.strip():
        prof.disliked_ingredients = [d.strip() for d in dislikes.split(",") if d.strip()]

    if click.confirm("Set daily nutrition targets?", default=bool(prof.daily_calories)):
        prof.daily_calories = click.prompt(
            "  Daily calories (kcal)", default=prof.daily_calories or 2000, type=int
        )
        prof.daily_protein_g = click.prompt(
            "  Daily protein (g)", default=prof.daily_protein_g or 50, type=int
        )
        prof.daily_carbs_g = click.prompt(
            "  Daily carbs (g)", default=prof.daily_carbs_g or 250, type=int
        )
        prof.daily_fat_g = click.prompt(
            "  Daily fat (g)", default=prof.daily_fat_g or 70, type=int
        )

    sundries = click.prompt(
        "Sundries/staples to keep stocked (comma-separated, e.g. coffee,sugar,salt,olive oil)",
        default=",".join(prof.sundries) if prof.sundries else "",
        show_default=False,
    )
    if sundries.strip():
        prof.sundries = [s.strip() for s in sundries.split(",") if s.strip()]

    save_profile(prof)
    click.echo("\nProfile saved!")
    _display_profile(prof)


def read_ingredients(ingredients_path: Path) -> dict[str, int]:
    """Read ingredients from a csv file.

    Args:
        ingredients_path: Path to csv file (without header) detailing ingredients. Each
            line should in format 'ingredient,quantity' e.g. 'eggs,2'.

    Returns:
        Keys are the ingredients to add to the basket and values are the desired
        quantity of each ingredient.
    """
    ingredients = {}

    with open(ingredients_path, "r") as ingredients_file:
        for ingredient_quantity in ingredients_file:
            ingredient, quantity = ingredient_quantity.strip().split(",")
            ingredients[ingredient] = int(quantity)

    return ingredients
