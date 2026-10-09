"""Configurable tolerances (strict first pass, relaxed agent retry)."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.domain import Txn


@dataclass(frozen=True)
class Tolerance:
    date_days: int
    amount_pct: float  # percent of the larger amount
    amount_abs: float = 0.01

    def amount_ok(self, a: float, b: float) -> bool:
        diff = abs(a - b)
        return diff <= self.amount_abs or (self.amount_pct > 0 and diff <= max(a, b) * self.amount_pct / 100.0)

    def date_ok(self, a, b) -> bool:
        return abs((a - b).days) <= self.date_days


def strict_tolerance(s: Settings) -> Tolerance:
    return Tolerance(s.strict_date_tolerance_days, s.strict_amount_tolerance_pct, s.amount_epsilon)


def relaxed_tolerance(s: Settings) -> Tolerance:
    return Tolerance(s.relaxed_date_tolerance_days, s.relaxed_amount_tolerance_pct, s.amount_epsilon)


def date_diff_days(a: Txn, b: Txn) -> int:
    return abs((a.date - b.date).days)


def amount_diff(a: Txn, b: Txn) -> float:
    return round(abs(a.amount - b.amount), 2)
