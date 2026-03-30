import pytest

from autogroceries.scraper.ingredient_parser import parse_ingredient


class TestParseIngredient:
    def test_quantity_unit_name(self) -> None:
        result = parse_ingredient("2 tbsp olive oil")
        assert result.quantity == 2.0
        assert result.unit == "tbsp"
        assert result.name == "olive oil"
        assert result.raw == "2 tbsp olive oil"

    def test_grams(self) -> None:
        result = parse_ingredient("200g chicken breast")
        assert result.quantity == 200.0
        assert result.unit == "g"
        assert result.name == "chicken breast"

    def test_fraction(self) -> None:
        result = parse_ingredient("1/2 tsp salt")
        assert result.quantity == 0.5
        assert result.unit == "tsp"
        assert result.name == "salt"

    def test_unicode_fraction(self) -> None:
        result = parse_ingredient("½ tsp salt")
        assert result.quantity == 0.5
        assert result.unit == "tsp"
        assert result.name == "salt"

    def test_unicode_fraction_with_whole(self) -> None:
        result = parse_ingredient("1½ cups flour")
        assert result.quantity == 1.5
        assert result.unit == "cup"
        assert result.name == "flour"

    def test_no_quantity(self) -> None:
        result = parse_ingredient("salt and pepper")
        assert result.quantity is None
        assert result.unit is None
        assert result.name == "salt and pepper"

    def test_quantity_no_unit(self) -> None:
        result = parse_ingredient("3 eggs")
        assert result.quantity == 3.0
        assert result.unit is None
        assert result.name == "eggs"

    def test_parenthetical_removed(self) -> None:
        result = parse_ingredient("200g butter (softened)")
        assert result.name == "butter"

    def test_comma_clause_removed(self) -> None:
        result = parse_ingredient("1 onion, finely diced")
        assert result.quantity == 1.0
        assert result.name == "onion"

    def test_cloves(self) -> None:
        result = parse_ingredient("3 cloves garlic")
        assert result.quantity == 3.0
        assert result.unit == "clove"
        assert result.name == "garlic"

    def test_decimal(self) -> None:
        result = parse_ingredient("1.5 kg lamb shoulder")
        assert result.quantity == 1.5
        assert result.unit == "kg"
        assert result.name == "lamb shoulder"

    def test_can(self) -> None:
        result = parse_ingredient("1 can chopped tomatoes")
        assert result.quantity == 1.0
        assert result.unit == "can"
        assert result.name == "chopped tomatoes"

    def test_of_keyword(self) -> None:
        result = parse_ingredient("1 bunch of coriander")
        assert result.quantity == 1.0
        assert result.unit == "bunch"
        assert result.name == "coriander"
