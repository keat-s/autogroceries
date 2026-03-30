from __future__ import annotations

import os

import requests
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html

from autogroceries.exceptions import RecipeScrapeError
from autogroceries.models import Nutrition, Recipe
from autogroceries.scraper.base import RecipeScraper
from autogroceries.scraper.ingredient_parser import parse_ingredient

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.6 Safari/605.1.15"
    )
}


class MobKitchenScraper(RecipeScraper):
    """Scraper for Mob Kitchen recipes, with optional premium login."""

    BASE_URL = "https://www.mob.co.uk"
    LOGIN_URL = "https://www.mob.co.uk/log-in"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._logged_in = False

    def login(self, username: str | None = None, password: str | None = None) -> None:
        """Authenticate with Mob Kitchen for premium content.

        Args:
            username: Mob account email. Falls back to MOB_USERNAME env var.
            password: Mob account password. Falls back to MOB_PASSWORD env var.
        """
        username = username or os.getenv("MOB_USERNAME")
        password = password or os.getenv("MOB_PASSWORD")
        if not username or not password:
            return

        login_page = self._session.get(self.LOGIN_URL)
        soup = BeautifulSoup(login_page.text, "html.parser")

        # Look for CSRF token in the login form
        csrf_input = soup.select_one(
            'input[name="csrfmiddlewaretoken"], '
            'input[name="_token"], '
            'input[name="authenticity_token"], '
            'input[name="csrf_token"]'
        )
        csrf_token = csrf_input["value"] if csrf_input else ""

        payload: dict[str, str] = {
            "email": username,
            "password": password,
        }
        if csrf_token:
            # Use the name attribute from whichever input was found
            token_name = csrf_input["name"] if csrf_input else "csrfmiddlewaretoken"
            payload[token_name] = str(csrf_token)

        resp = self._session.post(
            self.LOGIN_URL,
            data=payload,
            allow_redirects=True,
        )
        self._logged_in = resp.ok

    def scrape(self, url: str) -> Recipe:
        """Scrape a Mob Kitchen recipe from its URL."""
        resp = self._session.get(url)
        if not resp.ok:
            raise RecipeScrapeError(
                f"Failed to fetch {url}: HTTP {resp.status_code}"
            )

        scraper = scrape_html(html=resp.text, org_url=url)

        title = scraper.title()
        ingredients = [parse_ingredient(i) for i in scraper.ingredients()]

        try:
            instructions = scraper.instructions_list()
        except Exception:
            instructions = [scraper.instructions()]

        servings_str = scraper.yields()
        servings = _parse_servings(servings_str)

        recipe_id = Recipe.make_id(title, "mobkitchen")

        nutrition = _extract_nutrition(scraper)

        return Recipe(
            id=recipe_id,
            title=title,
            source="mobkitchen",
            url=url,
            servings=servings,
            prep_time=_safe_int(scraper.prep_time),
            cook_time=_safe_int(scraper.cook_time),
            ingredients=ingredients,
            instructions=instructions,
            nutrition=nutrition,
        )

    def search(self, query: str) -> list[dict[str, str]]:
        """Search Mob Kitchen for recipes matching a query."""
        resp = self._session.get(
            f"{self.BASE_URL}/recipes",
            params={"search": query},
        )
        if not resp.ok:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[dict[str, str]] = []

        for link in soup.select("a[href*='/recipes/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or not href:
                continue
            url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            if url not in [r["url"] for r in results]:
                results.append({"title": title, "url": url})

        return results[:20]


def _extract_nutrition(scraper: object) -> Nutrition | None:
    """Extract nutrition data from a recipe-scrapers object."""
    try:
        nutrients = scraper.nutrients()  # type: ignore[attr-defined]
        if not nutrients:
            return None

        def _float(key: str) -> float | None:
            val = nutrients.get(key, "")
            if not val:
                return None
            import re as _re

            m = _re.search(r"[\d.]+", str(val))
            return float(m.group()) if m else None

        return Nutrition(
            calories=_float("calories"),
            protein_g=_float("proteinContent"),
            carbs_g=_float("carbohydrateContent"),
            fat_g=_float("fatContent"),
            fibre_g=_float("fiberContent"),
            sugar_g=_float("sugarContent"),
            salt_g=_float("sodiumContent"),
        )
    except Exception:
        return None


def _parse_servings(yields: str) -> int | None:
    """Extract a number from yields string like '4 servings'."""
    if not yields:
        return None
    import re

    m = re.search(r"\d+", yields)
    return int(m.group()) if m else None


def _safe_int(method: object) -> int | None:
    """Safely call a recipe-scrapers method that may raise."""
    try:
        val = method()  # type: ignore[operator]
        return int(val) if val else None
    except Exception:
        return None
