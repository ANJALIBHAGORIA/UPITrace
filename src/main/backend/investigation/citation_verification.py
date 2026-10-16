"""Citation verification (spec section 8, steps 10-11 / section 3.8).

"Never accept an invented evidence ID from Gemini." This module is the single
place that enforces it: any citation_id not present in the context's allowed
set is stripped before the report reaches the caller, and the stripped IDs
are reported back (never silently dropped) so they can be counted as an
"unsupported factual claims" metric (spec section 10).
"""
from __future__ import annotations


def verify_and_strip_citations(
    citation_ids: list[str], allowed_ids: set[str]
) -> tuple[list[str], list[str]]:
    """Returns (valid_ids, removed_ids). Order of valid_ids is preserved;
    duplicates are removed."""
    seen: set[str] = set()
    valid: list[str] = []
    removed: list[str] = []
    for cid in citation_ids:
        if cid in seen:
            continue
        seen.add(cid)
        if cid in allowed_ids:
            valid.append(cid)
        else:
            removed.append(cid)
    return valid, removed
