"""Text normalisation helpers used by parsing, matching and fuzzy search."""
from __future__ import annotations

import re
from typing import Optional, Set

_NULL_REFS = {"", "nan", "none", "null", "-", "--", "n/a", "na", "nil", "0"}

CHANNEL_TOKENS = {
    "neft", "imps", "rtgs", "upi", "ach", "ecs", "nach", "pos", "ib", "inb", "mmt", "tpt", "trf", "transfer",
    "payment", "pmt", "paid", "to", "from", "by", "towards", "for", "the", "and", "of", "inv", "invoice", "ref",
    "utr", "no", "chq", "cheque", "dep", "txn", "bill", "a", "c", "ac",
}
SUFFIX_TOKENS = {"pvt", "ltd", "limited", "private", "llp", "inc", "corp", "corporation", "co", "company", "plc", "llc"}


def clean_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def normalize_description(s: Optional[str]) -> str:
    """lowercase, drop punctuation/separators, collapse spaces."""
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9&\s]", " ", s)
    return clean_whitespace(s)


def normalize_reference(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = re.sub(r"[\s\-_/]+", "", str(s).strip().lower())
    return None if s in _NULL_REFS else s


def _stem(tok: str) -> str:
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok


def vendor_key(normalized_description: str) -> str:
    """Reduce a narration to its vendor-like core for fuzzy comparison."""
    out = []
    for tok in (normalized_description or "").split():
        if tok in CHANNEL_TOKENS or tok in SUFFIX_TOKENS or tok == "&":
            continue
        if any(c.isdigit() for c in tok) and len(tok) >= 5:  # reference / invoice numbers
            continue
        if tok.isdigit():
            continue
        out.append(_stem(tok))
    return " ".join(out)


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-/_][A-Za-z0-9]+)*")


def reference_keys(raw_description: Optional[str], normalized_reference: Optional[str]) -> Set[str]:
    """Reference-like tokens (explicit reference + id-looking tokens inside narration)."""
    keys: Set[str] = set()
    if normalized_reference:
        keys.add(normalized_reference)
    for tok in _TOKEN_RE.findall(raw_description or ""):
        for piece in [tok] + re.split(r"[-/_]", tok):  # also index parts of hyphenated narrations (e.g. LTD-INV1001)
            n = normalize_reference(piece)
            if not n or len(n) < 6 or not any(c.isdigit() for c in n):
                continue
            if n.isdigit() and len(n) < 8:
                continue
            keys.add(n)
    return keys


def safe_filename(name: str) -> str:
    name = (name or "upload").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._") or "upload"
    return name[:100]
