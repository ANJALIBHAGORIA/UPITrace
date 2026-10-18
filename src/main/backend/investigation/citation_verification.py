"""Citation verification (spec section 8, steps 10-11 / section 3.8).

"Never accept an invented evidence ID from Gemini." This module is the single
place that enforces it: any citation_id not present in the context's allowed
set is stripped before the report reaches the caller, and the stripped IDs
are reported back (never silently dropped) so they can be counted as an
"unsupported factual claims" metric (spec section 10).
"""
from __future__ import annotations


def _coerce_citation_id(entry: object) -> str:
    """Gemini's JSON mode has no typed schema for these list fields, so an
    entry is sometimes an object (e.g. {"id": "EVD-001"}) instead of a plain
    ID string (observed live). Pull out a plausible ID key; anything else
    falls back to its string form, which won't match allowed_ids and is
    correctly stripped as unsupported rather than crashing on an unhashable
    dict."""
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        for key in ("id", "citation_id", "evidence_id", "ref_id"):
            value = entry.get(key)
            if isinstance(value, str):
                return value
    return str(entry)


def verify_and_strip_citations(
    citation_ids: list, allowed_ids: set[str]
) -> tuple[list[str], list[str]]:
    """Returns (valid_ids, removed_ids). Order of valid_ids is preserved;
    duplicates are removed."""
    seen: set[str] = set()
    valid: list[str] = []
    removed: list[str] = []
    for raw_entry in citation_ids:
        cid = _coerce_citation_id(raw_entry)
        if cid in seen:
            continue
        seen.add(cid)
        if cid in allowed_ids:
            valid.append(cid)
        else:
            removed.append(cid)
    return valid, removed
