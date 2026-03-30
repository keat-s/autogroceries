class TwoFactorAuthenticationRequiredError(Exception):
    pass


class MissingCredentialsError(Exception):
    pass


class RecipeScrapeError(Exception):
    pass


class RecipeNotFoundError(Exception):
    pass


class PlanNotFoundError(Exception):
    pass
