"""Amount parsing/formatting helpers."""
from __future__ import annotations

import math
import re
from typing import Any, Optional

_NULLS = {"", "nan", "none", "null", "-", "--", "n/a", "na", "nil"}
_DRCR = re.compile(r"(?i)\s*\b(dr|cr)\b\.?\s*$")
_STRIP = re.compile(r"(?i)(₹|rs\.?|inr|usd|eur|gbp|\$|€|£)")
_NUM = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def parse_amount(value: Any) -> Optional[float]:
    """Parse '₹5,000', '5,000.00', '-5000', '(5000)', '5000 Dr' -> float. None when blank.

    Raises ValueError for non-numeric input.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return round(float(value), 2)
    s = str(value).strip().replace("\u2212", "-").replace("\xa0", " ")
    if s.lower() in _NULLS:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    m = _DRCR.search(s)
    if m:
        neg = neg or m.group(1).lower() == "dr"
        s = s[: m.start()]
    s = _STRIP.sub("", s)
    s = s.replace(",", "").replace(" ", "")
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if not _NUM.fullmatch(s):
        raise ValueError(f"Invalid amount: {value!r}")
    num = float(s)
    if neg:
        num = -abs(num)
    return round(num, 2)


def format_money(amount: Optional[float], currency: str = "INR") -> str:
    """Format using Indian digit grouping, e.g. 125000.5 -> ₹1,25,000.50."""
    if amount is None:
        return "n/a"
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    symbol = "₹" if (currency or "INR").upper() == "INR" else (currency.upper() + " ")
    return f"{sign}{symbol}{whole}.{frac}"
