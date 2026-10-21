"""Split and match ingredient text without inventing an identity."""

from __future__ import annotations

import re

from app.catalog import INGREDIENTS
from app.engine import _BATCH_PREFIX, _DROP_KEYS, _FACTORY_FIL, _FACTORY_FIL_BARE, _SENTINEL, EXACT, items_in_text, normalize

MAX_TEXT = 20_000
_BY_ID = {item["id"]: item for item in INGREDIENTS}


def library_record(ingredient_id: str) -> dict | None:
    return _BY_ID.get(ingredient_id)


def relationship_view(ingredient_id: str) -> dict | None:
    item = _BY_ID.get(ingredient_id)
    if not item:
        return None
    return {
        "id": item["id"],
        "canonical_name": item["display"],
        "synonyms": list(item["names"]),
        "function": item["role"],
        "category": item["role"],
        "summary": item["summary"],
        "short_term": item["short_term"],
        "long_term": item["long_term"],
        "rules": item["rules"],
    }


def _clean_fragment(part: str) -> str:
    text = part.replace(_SENTINEL, ",")
    text = re.sub(r"\d+(?:\.\d+)?\s*%", " ", text)
    text = re.sub(r"[*†‡]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .;:-/")
    text = re.sub(
        r"^(and|ingredients?|active ingredients?|inactive ingredients?)\b",
        "",
        text,
        flags=re.I,
    ).strip(" .;:-/")
    return text.strip()


def _fragments(text: str) -> list[dict]:
    cleaned = text.replace("’", "'").replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"(\d),(\d)", rf"\1{_SENTINEL}\2", cleaned)
    cleaned = re.sub(r"\(([^)]*)\)", lambda match: ", " + match.group(1) + ", ", cleaned)
    for mark in ("•", "·", ";", "|", "\n", "\t"):
        cleaned = cleaned.replace(mark, ",")
    rows = []
    seen: set[str] = set()
    for part in cleaned.split(","):
        original = _clean_fragment(part)
        if not original:
            continue
        key = normalize(original)
        if not key or key in _DROP_KEYS or key.startswith("f i l"):
            continue
        reason = None
        if not re.search(r"[A-Za-z]", original):
            reason = "no_letters"
        elif len(original) > 80 or len(original.split()) > 8:
            reason = "too_long"
        elif re.fullmatch(r"[a-z]?\d[\d ]*", key):
            reason = "not_a_name"
        duplicate = key in seen
        seen.add(key)
        rows.append({"text": original, "key": key, "reason": reason, "duplicate": duplicate})
    return rows


def _prepare(text: str) -> tuple[str, list[str]]:
    raw = (text or "").strip()
    warnings = []
    if _FACTORY_FIL.search(raw) or _FACTORY_FIL_BARE.search(raw) or _BATCH_PREFIX.search(raw):
        warnings.append("Factory or batch codes were removed before the names were split.")
    raw = _FACTORY_FIL.sub(" ", raw)
    raw = _FACTORY_FIL_BARE.sub(" ", raw)
    raw = _BATCH_PREFIX.sub("", raw)
    raw = re.sub(r"^\s*ingredients?\s*[:\-–]\s*", "", raw, flags=re.I)
    return raw, warnings


def _one(row: dict, may_contain: bool) -> dict:
    base = {
        "original_name": row["text"],
        "canonical_name": None,
        "ingredient_id": None,
        "synonyms": [],
        "category": None,
        "function": None,
        "match_confidence": "none",
        "match_source": None,
        "verification_status": "unverified",
        "duplicate": row["duplicate"],
        "may_contain": may_contain,
        "candidates": [],
    }
    if row["reason"]:
        base["verification_status"] = "needs_review"
        base["match_confidence"] = "none"
        base["review_reason"] = row["reason"]
        return base
    matched = items_in_text(row["text"])
    exact = EXACT.get(row["key"])
    if len(matched) > 1 and exact is None:
        base["verification_status"] = "ambiguous"
        base["match_confidence"] = "low"
        base["candidates"] = [item["display"] for item in matched]
        return base
    item = exact or (matched[0] if len(matched) == 1 else None)
    if item is None:
        base["verification_status"] = "unknown"
        return base
    synonyms = [name for name in item["names"] if normalize(name) != row["key"]]
    color_index = item["id"] == "ci_colorant" and re.fullmatch(r"ci\s*\d{4,6}", row["key"]) is not None
    exact_hit = exact is not None or bool(color_index)
    base.update(
        {
            "canonical_name": item["display"],
            "ingredient_id": item["id"],
            "synonyms": synonyms[:12],
            "category": item["role"],
            "function": item["role"],
            "match_confidence": "high" if exact_hit else "review",
            "match_source": "cosmix-library",
            "verification_status": "matched" if exact_hit else "contained_match",
            "candidates": [],
        }
    )
    return base


def parse_and_normalize(text: str, tokens: list[str] | None = None) -> dict:
    if tokens is not None:
        raw = (text or "").strip()
        warnings: list[str] = []
        rows = [{"text": token.strip(), "key": normalize(token), "reason": None, "duplicate": False} for token in tokens if token and token.strip()]
        seen: set[str] = set()
        for row in rows:
            if not row["key"]:
                row["reason"] = "no_letters"
                continue
            if row["key"] in seen:
                row["duplicate"] = True
            seen.add(row["key"])
        may_rows: list[dict] = []
        original = raw or ", ".join(row["text"] for row in rows)
    else:
        raw = (text or "").strip()
        if not raw:
            raise ValueError("Paste an ingredient list.")
        if len(raw) > MAX_TEXT:
            raise ValueError("That ingredient list is too long. Paste only the ingredient section.")
        prepared, warnings = _prepare(raw)
        parts = re.split(r"\bmay contain\b\s*[:\-–]?", prepared, maxsplit=1, flags=re.I)
        rows = _fragments(parts[0])
        may_rows = _fragments(parts[1]) if len(parts) > 1 else []
        original = text.strip()

    if len(rows) + len(may_rows) > 400:
        raise ValueError("That list has too many entries to check in one pass.")

    normalized = [_one(row, False) for row in rows]
    normalized.extend(_one(row, True) for row in may_rows)
    uncertain = [
        {"text": row["original_name"], "reason": row.get("review_reason", "needs_review")}
        for row in normalized
        if row["verification_status"] == "needs_review"
    ]
    unknown = [
        row["original_name"] + (" (may contain)" if row["may_contain"] else "")
        for row in normalized
        if row["verification_status"] in {"unknown", "ambiguous"}
    ]
    if any(row["verification_status"] == "ambiguous" for row in normalized):
        warnings.append("At least one entry matched more than one ingredient. It was not assigned a single identity.")
    if unknown:
        warnings.append("Some names did not match the library. They are listed as unknown rather than guessed.")
    counted = [row for row in normalized if row["verification_status"] != "needs_review" and not row["duplicate"]]
    return {
        "original_text": original,
        "normalized_ingredients": normalized,
        "ingredient_count": len(counted),
        "unknown_ingredients": unknown,
        "uncertain_fragments": uncertain,
        "parsing_warnings": warnings,
    }
