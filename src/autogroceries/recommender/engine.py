from __future__ import annotations

from datetime import date

from autogroceries.models import Recipe, UserProfile
from autogroceries.planner.consolidator import _normalise_name
from autogroceries.recommender.history import load_history
from autogroceries.recommender.scoring import RecipeScore, ScoredRecipe
from autogroceries.recommender.seasonal import get_seasonal_ingredients
from autogroceries.storage import list_plans

DEFAULT_WEIGHTS: dict[str, float] = {
    "dietary": 5.0,
    "dislikes": 5.0,
    "cuisine": 1.5,
    "nutrition": 2.0,
    "variety": 1.5,
    "seasonal": 1.0,
    "pantry": 1.0,
}

# Keywords that indicate a cuisine from recipe title / ingredient names.
CUISINE_KEYWORDS: dict[str, list[str]] = {
    "italian": [
        "pasta", "risotto", "mozzarella", "parmesan", "pesto",
        "lasagne", "lasagna", "gnocchi", "bruschetta", "prosciutto",
        "bolognese", "carbonara", "pizza", "focaccia", "ciabatta",
    ],
    "indian": [
        "curry", "tikka", "masala", "naan", "paneer", "dal",
        "biryani", "samosa", "chutney", "turmeric", "garam masala",
        "korma", "tandoori", "chapati", "rogan josh",
    ],
    "thai": [
        "pad thai", "coconut milk", "fish sauce", "thai basil",
        "lemongrass", "galangal", "red curry", "green curry",
        "satay", "tom yum", "sriracha", "thai",
    ],
    "mexican": [
        "taco", "burrito", "salsa", "enchilada", "quesadilla",
        "guacamole", "jalape", "chipotle", "tortilla", "fajita",
        "nacho", "refried beans", "cilantro",
    ],
    "chinese": [
        "stir fry", "soy sauce", "wok", "noodles", "dumpling",
        "spring roll", "szechuan", "hoisin", "dim sum", "bok choy",
        "tofu", "chow mein", "kung pao",
    ],
    "japanese": [
        "sushi", "miso", "ramen", "tempura", "teriyaki",
        "edamame", "wasabi", "sashimi", "udon", "katsu",
    ],
    "mediterranean": [
        "hummus", "falafel", "tabbouleh", "halloumi", "pitta",
        "olive oil", "couscous", "za'atar", "tahini",
    ],
}

# Ingredients that violate specific dietary restrictions.
DIETARY_RESTRICTED: dict[str, list[str]] = {
    "vegetarian": [
        "chicken", "beef", "pork", "lamb", "steak", "bacon",
        "mince", "sausage", "ham", "turkey", "duck", "venison",
        "salmon", "tuna", "cod", "prawn", "shrimp", "fish",
        "anchovy", "anchovies", "mackerel", "crab", "lobster",
        "squid", "mussel", "clam", "oyster",
    ],
    "vegan": [
        "chicken", "beef", "pork", "lamb", "steak", "bacon",
        "mince", "sausage", "ham", "turkey", "duck", "venison",
        "salmon", "tuna", "cod", "prawn", "shrimp", "fish",
        "anchovy", "anchovies", "mackerel", "crab", "lobster",
        "squid", "mussel", "clam", "oyster",
        "milk", "cheese", "butter", "cream", "yoghurt", "yogurt",
        "egg", "eggs", "honey", "ghee", "mozzarella", "parmesan",
        "cheddar", "brie", "feta", "halloumi", "mascarpone",
        "ricotta", "creme fraiche",
    ],
    "gluten-free": [
        "wheat", "flour", "bread", "pasta", "noodle", "couscous",
        "breadcrumb", "soy sauce", "barley", "rye", "semolina",
        "tortilla", "wrap", "pitta", "naan", "ciabatta", "focaccia",
        "crouton", "panko",
    ],
    "dairy-free": [
        "milk", "cheese", "butter", "cream", "yoghurt", "yogurt",
        "ghee", "mozzarella", "parmesan", "cheddar", "brie",
        "feta", "halloumi", "mascarpone", "ricotta",
        "creme fraiche",
    ],
}


class RecipeRecommender:
    """Recommends recipes based on user preferences and history."""

    def __init__(
        self,
        profile: UserProfile,
        weights: dict[str, float] | None = None,
        today: date | None = None,
    ):
        self.profile = profile
        self.weights = weights or DEFAULT_WEIGHTS
        self._today = today or date.today()

    def recommend(
        self,
        candidates: list[Recipe],
        count: int = 7,
    ) -> list[ScoredRecipe]:
        """Score and rank recipes, return top *count*.

        Args:
            candidates: Recipes to evaluate.
            count: Number of recommendations to return.

        Returns:
            Top-scoring recipes with full score breakdowns.
        """
        scored = [
            ScoredRecipe(recipe=r, score=self._score_recipe(r))
            for r in candidates
        ]
        scored.sort(key=lambda sr: sr.score.total, reverse=True)
        return scored[:count]

    # ------------------------------------------------------------------
    # Aggregate scoring
    # ------------------------------------------------------------------

    def _score_recipe(self, recipe: Recipe) -> RecipeScore:
        """Score a single recipe across all dimensions."""
        scores = {
            "dietary": self._score_dietary(recipe),
            "dislikes": self._score_dislikes(recipe),
            "cuisine": self._score_cuisine(recipe),
            "nutrition": self._score_nutrition(recipe),
            "variety": self._score_variety(recipe),
            "seasonal": self._score_seasonal(recipe),
            "pantry": self._score_pantry(recipe),
        }

        total = sum(
            scores[dim] * self.weights.get(dim, 0.0) for dim in scores
        )
        max_total = sum(self.weights.values())
        normalised = total / max_total if max_total > 0 else 0.0

        return RecipeScore(
            recipe_id=recipe.id,
            total=normalised,
            **scores,
        )

    # ------------------------------------------------------------------
    # Individual scoring dimensions (each returns 0.0 – 1.0)
    # ------------------------------------------------------------------

    def _ingredient_names(self, recipe: Recipe) -> list[str]:
        """Return normalised ingredient names for a recipe."""
        return [_normalise_name(i.name) for i in recipe.ingredients]

    def _score_dietary(self, recipe: Recipe) -> float:
        """0.0 if the recipe violates any dietary restriction, else 1.0."""
        if not self.profile.dietary_restrictions:
            return 1.0

        names = self._ingredient_names(recipe)
        for restriction in self.profile.dietary_restrictions:
            restricted = DIETARY_RESTRICTED.get(restriction.lower(), [])
            for bad in restricted:
                normalised_bad = _normalise_name(bad)
                for name in names:
                    if normalised_bad in name or name in normalised_bad:
                        return 0.0
        return 1.0

    def _score_dislikes(self, recipe: Recipe) -> float:
        """0.0 if the recipe contains a disliked ingredient, else 1.0."""
        if not self.profile.disliked_ingredients:
            return 1.0

        names = self._ingredient_names(recipe)
        for disliked in self.profile.disliked_ingredients:
            normalised_disliked = _normalise_name(disliked)
            for name in names:
                if normalised_disliked in name or name in normalised_disliked:
                    return 0.0
        return 1.0

    def _score_cuisine(self, recipe: Recipe) -> float:
        """Higher score if the recipe matches a preferred cuisine."""
        if not self.profile.cuisine_preferences:
            return 0.5  # neutral

        title_lower = recipe.title.lower()
        names = self._ingredient_names(recipe)
        searchable = title_lower + " " + " ".join(names)

        best_score = 0.0
        for pref in self.profile.cuisine_preferences:
            pref_lower = pref.lower()
            keywords = CUISINE_KEYWORDS.get(pref_lower, [])

            # Direct cuisine name match in title
            if pref_lower in title_lower:
                best_score = max(best_score, 1.0)
                continue

            # Keyword matching
            matches = sum(1 for kw in keywords if kw in searchable)
            if keywords:
                ratio = min(matches / 2.0, 1.0)  # 2+ keyword hits = full score
                best_score = max(best_score, ratio)

        return best_score

    def _score_nutrition(self, recipe: Recipe) -> float:
        """Score how closely per-serving nutrition matches daily targets / 3."""
        if not recipe.nutrition:
            return 0.5  # neutral when no data

        profile = self.profile
        if not any([
            profile.daily_calories,
            profile.daily_protein_g,
            profile.daily_carbs_g,
            profile.daily_fat_g,
        ]):
            return 0.5  # neutral when no targets

        comparisons: list[float] = []
        n = recipe.nutrition

        if profile.daily_calories and n.calories:
            target = profile.daily_calories / 3.0
            comparisons.append(_closeness(n.calories, target))

        if profile.daily_protein_g and n.protein_g:
            target = profile.daily_protein_g / 3.0
            comparisons.append(_closeness(n.protein_g, target))

        if profile.daily_carbs_g and n.carbs_g:
            target = profile.daily_carbs_g / 3.0
            comparisons.append(_closeness(n.carbs_g, target))

        if profile.daily_fat_g and n.fat_g:
            target = profile.daily_fat_g / 3.0
            comparisons.append(_closeness(n.fat_g, target))

        if not comparisons:
            return 0.5

        return sum(comparisons) / len(comparisons)

    def _score_variety(self, recipe: Recipe) -> float:
        """Penalise recipes whose ingredients overlap with recent plans."""
        try:
            plans = list_plans()
        except Exception:
            return 1.0

        if not plans:
            return 1.0

        # Collect ingredient names from the most recent plan
        recent_ingredients: set[str] = set()
        for plan in plans[-2:]:  # last 2 plans
            for day in plan.days:
                for meal in day.meals:
                    try:
                        from autogroceries.storage import load_recipe

                        r = load_recipe(meal.recipe_id)
                        for ing in r.ingredients:
                            recent_ingredients.add(_normalise_name(ing.name))
                    except Exception:
                        continue

        if not recent_ingredients:
            return 1.0

        recipe_ingredients = set(self._ingredient_names(recipe))
        if not recipe_ingredients:
            return 1.0

        overlap = recipe_ingredients & recent_ingredients
        overlap_ratio = len(overlap) / len(recipe_ingredients)
        return 1.0 - overlap_ratio

    def _score_seasonal(self, recipe: Recipe) -> float:
        """Boost recipes that use seasonal ingredients."""
        seasonal = get_seasonal_ingredients(self._today)
        if not seasonal:
            return 0.5

        names = self._ingredient_names(recipe)
        if not names:
            return 0.5

        seasonal_normalised = [_normalise_name(s) for s in seasonal]
        matches = 0
        for name in names:
            for s in seasonal_normalised:
                if s in name or name in s:
                    matches += 1
                    break

        # 3+ seasonal ingredients = full score
        return min(matches / 3.0, 1.0)

    def _score_pantry(self, recipe: Recipe) -> float:
        """Boost recipes that use ingredients already in the pantry."""
        if not self.profile.pantry:
            return 0.5

        pantry_names = {_normalise_name(p.name) for p in self.profile.pantry}
        names = self._ingredient_names(recipe)
        if not names:
            return 0.5

        matches = 0
        for name in names:
            for p in pantry_names:
                if p in name or name in p:
                    matches += 1
                    break

        return min(matches / max(len(names) * 0.5, 1.0), 1.0)


def _closeness(actual: float, target: float) -> float:
    """Return 0.0–1.0 representing how close actual is to target.

    Uses a simple ratio-based approach: the score drops linearly as
    the actual value deviates from the target, reaching 0 when it is
    more than double or less than half the target.
    """
    if target <= 0:
        return 0.5
    ratio = actual / target
    # Perfect = 1.0, 0.5x or 2x = 0.0
    return max(0.0, 1.0 - abs(ratio - 1.0))
