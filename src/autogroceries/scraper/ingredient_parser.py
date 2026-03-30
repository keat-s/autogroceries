from __future__ import annotations

import re

from autogroceries.models import Ingredient

UNITS = (
    "kg",
    "g",
    "mg",
    "l",
    "litre",
    "litres",
    "ml",
    "tbsp",
    "tsp",
    "cup",
    "cups",
    "oz",
    "lb",
    "lbs",
    "clove",
    "cloves",
    "bunch",
    "bunches",
    "handful",
    "handfuls",
    "pinch",
    "slice",
    "slices",
    "piece",
    "pieces",
    "sprig",
    "sprigs",
    "can",
    "cans",
    "tin",
    "tins",
    "packet",
    "pack",
    "cm",
    "inch",
    "inches",
)

# Build unit set including plural forms for matching
_ALL_UNITS = set(UNITS)
for _u in list(UNITS):
    _ALL_UNITS.add(_u + "s")
_UNIT_PATTERN = "|".join(re.escape(u) for u in sorted(_ALL_UNITS, key=len, reverse=True))

_FRACTION_MAP = {
    "½": 0.5,
    "⅓": 1 / 3,
    "⅔": 2 / 3,
    "¼": 0.25,
    "¾": 0.75,
    "⅕": 0.2,
    "⅛": 0.125,
}

_QUANTITY_RE = re.compile(
    r"^(\d+\s*/\s*\d+|\d+\.?\d*)\s*"  # number or fraction
)

_UNICODE_FRAC_RE = re.compile(
    r"^(\d*)\s*([½⅓⅔¼¾⅕⅛])\s*"
)

_UNIT_RE = re.compile(
    rf"^({_UNIT_PATTERN})\b\.?\s*(?:of\s+)?",
    re.IGNORECASE,
)

# Map all unit forms to their canonical singular
_UNIT_SINGULAR: dict[str, str] = {}
_UNITS_SET = set(UNITS)
for _u in UNITS:
    # If this unit ends with 's' and the form without 's' also exists, it's a plural
    if _u.endswith("s") and _u[:-1] in _UNITS_SET:
        _UNIT_SINGULAR[_u] = _u[:-1]
    elif _u.endswith("es") and _u[:-2] in _UNITS_SET:
        _UNIT_SINGULAR[_u] = _u[:-2]
    else:
        _UNIT_SINGULAR[_u] = _u
    # Also map the "unit + s" form if not already present
    plural = _u + "s"
    if plural not in _UNIT_SINGULAR:
        _UNIT_SINGULAR[plural] = _u


def parse_ingredient(raw: str) -> Ingredient:
    """Parse a raw ingredient string into structured components.

    Args:
        raw: Raw ingredient string, e.g. "2 tbsp olive oil".

    Returns:
        An Ingredient with parsed name, quantity, and unit.
    """
    text = raw.strip()
    quantity: float | None = None
    unit: str | None = None

    # Try unicode fraction first (e.g. "1½ cups" or "½ tsp")
    m = _UNICODE_FRAC_RE.match(text)
    if m:
        whole = int(m.group(1)) if m.group(1) else 0
        quantity = whole + _FRACTION_MAP.get(m.group(2), 0)
        text = text[m.end():]
    else:
        # Try numeric quantity (e.g. "2", "1.5", "1/2")
        m = _QUANTITY_RE.match(text)
        if m:
            q_str = m.group(1)
            if "/" in q_str:
                num, den = q_str.split("/")
                quantity = float(num.strip()) / float(den.strip())
            else:
                quantity = float(q_str)
            text = text[m.end():]

    # Try unit
    m = _UNIT_RE.match(text)
    if m:
        matched_unit = m.group(1).lower()
        unit = _UNIT_SINGULAR.get(matched_unit, matched_unit)
        text = text[m.end():]

    # Clean up name
    name = re.sub(r"\s*\(.*?\)\s*", " ", text)  # remove parenthetical notes
    name = re.sub(r",.*$", "", name)  # remove trailing comma clauses
    name = name.strip(" ,-.")

    return Ingredient(name=name, quantity=quantity, unit=unit, raw=raw)
