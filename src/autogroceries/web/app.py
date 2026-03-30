"""Main FastAPI application wrapping existing autogroceries functionality."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException

from autogroceries.exceptions import PlanNotFoundError, RecipeNotFoundError
from autogroceries.models import (
    DayPlan,
    Ingredient,
    Meal,
    MealPlan,
    PantryItem,
    Recipe,
    UserProfile,
)
from autogroceries.planner.consolidator import calculate_plan_nutrition, generate_shopping_list
from autogroceries.planner.planner import add_meal, create_plan, remove_meal
from autogroceries.scheduler.reminders import ReminderSettings, load_reminders, save_reminders
from autogroceries.scheduler.scheduler import configure_scheduler, get_scheduler
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
from autogroceries.web.schemas import (
    AddMealRequest,
    CreatePlanRequest,
    DayPlanSchema,
    IngredientSchema,
    MealPlanSchema,
    MealSchema,
    NutritionDaySchema,
    NutritionSchema,
    PantryItemSchema,
    PlanNutritionResponse,
    RecipeSchema,
    ReminderSettingsSchema,
    RemoveMealRequest,
    ScrapeRequest,
    SearchRequest,
    ShoppingListResponse,
    UserProfileSchema,
)

# Domain-to-source mapping (mirrors cli.py)
SOURCE_DOMAINS = {
    "mob.co.uk": "mobkitchen",
    "mobkitchen.co.uk": "mobkitchen",
    "waitrose.com": "waitrose",
    "sainsburys.co.uk": "sainsburys",
}


def _detect_source(url: str) -> str | None:
    """Detect the recipe source from a URL's domain."""
    for domain, src in SOURCE_DOMAINS.items():
        if domain in url:
            return src
    return None


def _recipe_to_schema(recipe: Recipe) -> RecipeSchema:
    """Convert a Recipe dataclass to a Pydantic response schema."""
    nutrition = None
    if recipe.nutrition:
        nutrition = NutritionSchema(**recipe.nutrition.to_dict())
    return RecipeSchema(
        id=recipe.id,
        title=recipe.title,
        source=recipe.source,
        url=recipe.url,
        servings=recipe.servings,
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        ingredients=[
            IngredientSchema(
                name=i.name, quantity=i.quantity, unit=i.unit, raw=i.raw,
            )
            for i in recipe.ingredients
        ],
        instructions=recipe.instructions,
        nutrition=nutrition,
    )


def _plan_to_schema(plan: MealPlan) -> MealPlanSchema:
    """Convert a MealPlan dataclass to a Pydantic response schema."""
    return MealPlanSchema(
        name=plan.name,
        days=[
            DayPlanSchema(
                date=d.date,
                meals=[MealSchema(recipe_id=m.recipe_id, servings=m.servings) for m in d.meals],
            )
            for d in plan.days
        ],
    )


def _profile_to_schema(profile: UserProfile) -> UserProfileSchema:
    """Convert a UserProfile dataclass to a Pydantic response schema."""
    return UserProfileSchema(
        cuisine_preferences=profile.cuisine_preferences,
        dietary_restrictions=profile.dietary_restrictions,
        disliked_ingredients=profile.disliked_ingredients,
        household_size=profile.household_size,
        daily_calories=profile.daily_calories,
        daily_protein_g=profile.daily_protein_g,
        daily_carbs_g=profile.daily_carbs_g,
        daily_fat_g=profile.daily_fat_g,
        weight_goal=profile.weight_goal,
        pantry=[
            PantryItemSchema(
                name=p.name, quantity=p.quantity, unit=p.unit, category=p.category,
            )
            for p in profile.pantry
        ],
        sundries=profile.sundries,
        preferred_store=profile.preferred_store,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the background scheduler with the app."""
    scheduler = configure_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="autogroceries",
    description="REST API for recipe planning and grocery automation.",
    version="2.2.4",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


@app.get("/api/recipes", response_model=list[RecipeSchema])
def api_list_recipes() -> list[RecipeSchema]:
    """List all saved recipes."""
    return [_recipe_to_schema(r) for r in list_recipes()]


@app.get("/api/recipes/{recipe_id}", response_model=RecipeSchema)
def api_get_recipe(recipe_id: str) -> RecipeSchema:
    """Get a single recipe by ID."""
    try:
        from autogroceries.storage import load_recipe

        recipe = load_recipe(recipe_id)
    except RecipeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Recipe '{recipe_id}' not found.")
    return _recipe_to_schema(recipe)


@app.post("/api/recipes/scrape", response_model=RecipeSchema)
def api_scrape_recipe(body: ScrapeRequest) -> RecipeSchema:
    """Scrape a recipe from a URL and save it."""
    from autogroceries.scraper.mobkitchen import MobKitchenScraper
    from autogroceries.scraper.sainsburys_recipes import SainsburysScraper
    from autogroceries.scraper.waitrose_recipes import WaitroseScraper

    scrapers = {
        "mobkitchen": MobKitchenScraper,
        "waitrose": WaitroseScraper,
        "sainsburys": SainsburysScraper,
    }

    source = body.source or _detect_source(body.url)
    if not source or source not in scrapers:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect source for URL: {body.url}. "
            "Specify 'source' as mobkitchen, waitrose, or sainsburys.",
        )

    scraper = scrapers[source]()
    try:
        recipe = scraper.scrape(body.url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {exc}")

    save_recipe(recipe)
    return _recipe_to_schema(recipe)


@app.post("/api/recipes/search")
def api_search_recipes(body: SearchRequest) -> list[dict]:
    """Search for recipes on a source site."""
    from autogroceries.scraper.mobkitchen import MobKitchenScraper
    from autogroceries.scraper.sainsburys_recipes import SainsburysScraper
    from autogroceries.scraper.waitrose_recipes import WaitroseScraper

    scrapers = {
        "mobkitchen": MobKitchenScraper,
        "waitrose": WaitroseScraper,
        "sainsburys": SainsburysScraper,
    }

    if body.source not in scrapers:
        raise HTTPException(status_code=400, detail=f"Unknown source: {body.source}")

    scraper = scrapers[body.source]()
    try:
        results = scraper.search(body.query)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}")
    return results


@app.delete("/api/recipes/{recipe_id}")
def api_delete_recipe(recipe_id: str) -> dict:
    """Delete a saved recipe by ID."""
    try:
        delete_recipe(recipe_id)
    except RecipeNotFoundError:
        raise HTTPException(status_code=404, detail=f"Recipe '{recipe_id}' not found.")
    return {"deleted": recipe_id}


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@app.get("/api/plans", response_model=list[MealPlanSchema])
def api_list_plans() -> list[MealPlanSchema]:
    """List all saved meal plans."""
    return [_plan_to_schema(p) for p in list_plans()]


@app.get("/api/plans/{name}", response_model=MealPlanSchema)
def api_get_plan(name: str) -> MealPlanSchema:
    """Get a meal plan by name."""
    try:
        plan = load_plan(name)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan '{name}' not found.")
    return _plan_to_schema(plan)


@app.post("/api/plans", response_model=MealPlanSchema)
def api_create_plan(body: CreatePlanRequest) -> MealPlanSchema:
    """Create a new meal plan."""
    start = None
    if body.start_date:
        start = date.fromisoformat(body.start_date)
    plan = create_plan(body.name, start_date=start, num_days=body.num_days)
    save_plan(plan)
    return _plan_to_schema(plan)


@app.post("/api/plans/{name}/meals", response_model=MealPlanSchema)
def api_add_meal(name: str, body: AddMealRequest) -> MealPlanSchema:
    """Add a meal to a plan."""
    try:
        plan = load_plan(name)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan '{name}' not found.")
    add_meal(plan, body.date, body.recipe_id, body.servings)
    save_plan(plan)
    return _plan_to_schema(plan)


@app.delete("/api/plans/{name}/meals", response_model=MealPlanSchema)
def api_remove_meal(name: str, body: RemoveMealRequest) -> MealPlanSchema:
    """Remove a meal from a plan."""
    try:
        plan = load_plan(name)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan '{name}' not found.")
    remove_meal(plan, body.date, body.recipe_id)
    save_plan(plan)
    return _plan_to_schema(plan)


@app.get("/api/plans/{name}/shopping-list", response_model=ShoppingListResponse)
def api_shopping_list(name: str) -> ShoppingListResponse:
    """Generate a shopping list from a plan."""
    try:
        plan = load_plan(name)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan '{name}' not found.")
    profile = load_profile()
    items = generate_shopping_list(plan, profile=profile)
    return ShoppingListResponse(plan_name=name, items=items)


@app.get("/api/plans/{name}/nutrition", response_model=PlanNutritionResponse)
def api_plan_nutrition(name: str) -> PlanNutritionResponse:
    """Get daily nutrition breakdown for a plan."""
    try:
        plan = load_plan(name)
    except PlanNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plan '{name}' not found.")
    daily = calculate_plan_nutrition(plan)
    days = [
        NutritionDaySchema(
            date=d,
            nutrition=NutritionSchema(
                calories=n.calories,
                protein_g=n.protein_g,
                carbs_g=n.carbs_g,
                fat_g=n.fat_g,
                fibre_g=n.fibre_g,
            ),
        )
        for d, n in sorted(daily.items())
    ]
    return PlanNutritionResponse(plan_name=name, days=days)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@app.get("/api/profile", response_model=UserProfileSchema)
def api_get_profile() -> UserProfileSchema:
    """Get the user profile."""
    return _profile_to_schema(load_profile())


@app.put("/api/profile", response_model=UserProfileSchema)
def api_update_profile(body: UserProfileSchema) -> UserProfileSchema:
    """Update the user profile."""
    profile = UserProfile(
        cuisine_preferences=body.cuisine_preferences,
        dietary_restrictions=body.dietary_restrictions,
        disliked_ingredients=body.disliked_ingredients,
        household_size=body.household_size,
        daily_calories=body.daily_calories,
        daily_protein_g=body.daily_protein_g,
        daily_carbs_g=body.daily_carbs_g,
        daily_fat_g=body.daily_fat_g,
        weight_goal=body.weight_goal,
        pantry=[
            PantryItem(name=p.name, quantity=p.quantity, unit=p.unit, category=p.category)
            for p in body.pantry
        ],
        sundries=body.sundries,
        preferred_store=body.preferred_store,
    )
    save_profile(profile)
    return _profile_to_schema(profile)


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


@app.get("/api/reminders", response_model=ReminderSettingsSchema)
def api_get_reminders() -> ReminderSettingsSchema:
    """Get the current reminder settings."""
    settings = load_reminders()
    return ReminderSettingsSchema(**settings.to_dict())


@app.put("/api/reminders", response_model=ReminderSettingsSchema)
def api_update_reminders(body: ReminderSettingsSchema) -> ReminderSettingsSchema:
    """Update reminder settings and reconfigure the scheduler."""
    settings = ReminderSettings(
        enabled=body.enabled,
        reminder_day=body.reminder_day,
        reminder_time=body.reminder_time,
        auto_generate_list=body.auto_generate_list,
        notification_method=body.notification_method,
    )
    save_reminders(settings)
    configure_scheduler(settings)
    return body
