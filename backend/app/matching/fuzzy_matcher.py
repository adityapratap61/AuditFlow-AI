"""Fuzzy string similarity (RapidFuzz; difflib fallback only if RapidFuzz is not installed)."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, List, Tuple

from app.domain import Txn

try:  # pragma: no cover - exercised implicitly
    from rapidfuzz import fuzz as _fuzz
    HAVE_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _fuzz = None
    HAVE_RAPIDFUZZ = False


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() * 100.0


def token_sort_ratio(a: str, b: str) -> float:
    if _fuzz is not None:
        return float(_fuzz.token_sort_ratio(a, b))
    return _ratio(" ".join(sorted(a.split())), " ".join(sorted(b.split())))


def token_set_ratio(a: str, b: str) -> float:
    if _fuzz is not None:
        return float(_fuzz.token_set_ratio(a, b))
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    inter = " ".join(sorted(ta & tb))
    ra = (inter + " " + " ".join(sorted(ta - tb))).strip()
    rb = (inter + " " + " ".join(sorted(tb - ta))).strip()
    return max(_ratio(inter, ra) if inter else 0.0, _ratio(inter, rb) if inter else 0.0, _ratio(ra, rb))


def text_similarity(a: str, b: str) -> float:
    """0-100 similarity of two (already normalised) strings."""
    if not a or not b:
        return 0.0
    if a == b:
        return 100.0
    return 0.6 * token_sort_ratio(a, b) + 0.4 * token_set_ratio(a, b)


def description_similarity(a: Txn, b: Txn) -> float:
    ka, kb = a.vendor_key, b.vendor_key
    if not ka or not kb:  # fall back to full normalised narration
        ka, kb = a.normalized_description, b.normalized_description
    return round(text_similarity(ka, kb), 2)


def has_description_info(a: Txn, b: Txn) -> bool:
    return bool((a.vendor_key or a.normalized_description) or (b.vendor_key or b.normalized_description))


def fuzzy_rank(txn: Txn, candidates: Iterable[Txn], min_score: float = 0.0) -> List[Tuple[Txn, float]]:
    ranked = [(c, description_similarity(txn, c)) for c in candidates]
    ranked = [(c, s) for c, s in ranked if s >= min_score]
    ranked.sort(key=lambda t: (-t[1], abs((t[0].date - txn.date).days)))
    return ranked
