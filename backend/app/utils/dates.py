"""Date parsing helpers (tolerant of many bank/ERP formats)."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional, Tuple

_FORMATS = [
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d", "%Y.%m.%d",
    "%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %b %y", "%d-%B-%Y", "%d %B %Y", "%d %B, %Y", "%d %b, %Y",
    "%b %d, %Y", "%b %d %Y", "%B %d, %Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M",
]
_MONTH_FIRST = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]
_ORD = re.compile(r"(?i)(\d)(st|nd|rd|th)\b")
_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
DATE_RE = re.compile(
    rf"(?:\d{{4}}-\d{{2}}-\d{{2}}"
    rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}"
    rf"|\d{{1,2}}[ -]{_MON}\.?,?[ -]*\d{{2,4}}"
    rf"|{_MON}\.? \d{{1,2}},? \d{{4}})",
    re.IGNORECASE,
)


def parse_date(value: Any, dayfirst: bool = True) -> date:
    """Parse many date formats to datetime.date. Raises ValueError if unparseable.

    Ambiguous numeric dates (03/04/2025) are read day-first unless dayfirst=False;
    impossible day-first values (e.g. 04/13/2025) fall back to month-first.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().date()
    if value is None:
        raise ValueError("Missing date")
    s = _ORD.sub(r"\1", str(value).strip())
    if not s or s.lower() in {"nan", "nat", "none", "null"}:
        raise ValueError("Missing date")
    fmts = _FORMATS + _MONTH_FIRST
    if not dayfirst:
        fmts = _MONTH_FIRST[:1] + fmts
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value!r}")


def match_date_at_start(line: str) -> Optional[Tuple[date, int]]:
    """If a line begins with (optional serial no. +) a date, return (date, end_index)."""
    m = re.match(r"\s*(?:\d{1,3}\s+)?(" + DATE_RE.pattern + r")", line, re.IGNORECASE)
    if not m:
        return None
    try:
        return parse_date(m.group(1)), m.end()
    except ValueError:
        return None
