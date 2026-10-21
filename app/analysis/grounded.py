"""Retrieval-grounded analysis. Concerns come from retrieved records, not from a free-form model."""

from __future__ import annotations

from app.ingredients.evidence import LIBRARY, notes_for, public_source
from app.ingredients.normalize import library_record, parse_and_normalize

_BANNED = (
    "guaranteed safe",
    "100% safe",
    "completely safe",
    "cures ",
    "will cure",
    "causes cancer",
    "medically suitable",
    "safe for everyone",
    "clinically proven to cure",
)

LIMITATIONS = [
    "An ingredient list does not show concentration unless the label itself states a percentage, and even then the percentage applies only to that line.",
    "Ingredient order is not a formula percentage.",
    "This result does not say a product is safe, unsafe for every person, able to cause a disease, or able to cure one.",
    "A name that did not match a retrieved record stays unknown. No profile was invented for it.",
    "Library sentences are curated shopping notes. A regulatory sentence is included only when that source is attached.",
]

NEXT_STEPS = [
    "Compare the parsed names with the pack in your hand. If they differ, the pack wins.",
    "Treat a preference match as your own flag, not as a new scientific finding.",
    "If you are pregnant, using a prescription on your skin, or already reacting, ask a dermatologist before you buy or apply the product.",
    "Look up unknown names before you treat them as known ingredients.",
]


def _banned(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in _BANNED)


def _preference_hit(row: dict, preferences: dict[str, list[str]]) -> list[dict]:
    from app.engine import normalize

    names = {normalize(row.get("original_name") or "")}
    if row.get("canonical_name"):
        names.add(normalize(row["canonical_name"]))
    record = library_record(row.get("ingredient_id"))
    if record:
        names.update(normalize(name) for name in record["names"])
    names.discard("")
    hits = []
    for kind in ("avoid", "prefer", "investigate"):
        for wanted in preferences.get(kind) or []:
            if normalize(wanted) and normalize(wanted) in names:
                hits.append(
                    {
                        "ingredient": row.get("canonical_name") or row["original_name"],
                        "preference": kind,
                        "note": (
                            "This matches a name you asked to "
                            + {"avoid": "avoid", "prefer": "prefer", "investigate": "investigate"}[kind]
                            + ". That is your preference, not a new scientific finding, and it is not an allergy test."
                        ),
                    }
                )
                break
    return hits


def _explanation(row: dict, record: dict | None, notes: list[dict]) -> tuple[str, str, list[str]]:
    if row["verification_status"] in {"unknown", "needs_review"}:
        return (
            "This text did not match a retrieved ingredient record. No function, concern, or citation was added for it.",
            "insufficient",
            [],
        )
    if row["verification_status"] == "ambiguous":
        choices = ", ".join(row.get("candidates") or []) or "more than one record"
        return (
            f"This text resembles {choices}. No single identity was chosen, so no concern was attached.",
            "insufficient",
            [],
        )
    assert record is not None
    source_ids = ["cosmix-library"]
    levels = ["limited"]
    regulatory = [note["statement"] for note in notes if note.get("statement")]
    for note in notes:
        levels.append(note["evidence_level"])
        for source_id in note["source_ids"]:
            if source_id not in source_ids:
                source_ids.append(source_id)
    text = (
        f"The library records {record['display']} under the role {record['role']}. {record['summary']} "
        f"Short-term note from that library: {record['short_term']} "
        f"Longer-term note from that library: {record['long_term']}"
    )
    if regulatory:
        text += " Retrieved regulatory context: " + " ".join(regulatory)
    text += " These sentences are not a measurement of this product and not a statement that it is safe or medically suitable."
    if "established" in levels and "conflicting" in levels:
        level = "conflicting"
    elif "established" in levels:
        level = "established"
    elif "conflicting" in levels:
        level = "conflicting"
    else:
        level = "limited"
    return text, level, source_ids


def _concerns(row: dict, record: dict | None, notes: list[dict]) -> list[dict]:
    if not record or row["verification_status"] not in {"matched", "contained_match"}:
        return []
    found = []
    covered_avoid = False
    for note in notes:
        if not note.get("concern_level"):
            continue
        covered_avoid = covered_avoid or note["concern_level"] == "avoid"
        found.append(
            {
                "ingredient": record["display"],
                "ingredient_id": record["id"],
                "nature": note["statement"],
                "concern_level": note["concern_level"],
                "evidence_level": note["evidence_level"],
                "source_ids": list(note["source_ids"]),
                "limitations": note["limitations"],
                "why_it_may_not_apply": "The note describes the substance or the legal category. It does not prove the amount in this package or how your skin will respond.",
            }
        )
    for rule in record["rules"]:
        if rule["if"] != "always" or rule["level"] not in {"avoid", "caution"}:
            continue
        if rule["level"] == "avoid" and covered_avoid:
            continue
        found.append(
            {
                "ingredient": record["display"],
                "ingredient_id": record["id"],
                "nature": rule["reason"],
                "concern_level": rule["level"],
                "evidence_level": "limited",
                "source_ids": ["cosmix-library"],
                "limitations": "This sentence is from the COSMIX curated library. It is not a clinical citation and it does not mean the ingredient harms every person.",
                "why_it_may_not_apply": "A label name does not show the percentage, the product type, or your own history.",
            }
        )
    return found


def _conditional(record: dict | None, row: dict) -> list[str]:
    if not record or row["verification_status"] not in {"matched", "contained_match"}:
        return []
    lines = []
    for rule in record["rules"]:
        if rule["if"] == "always":
            continue
        lines.append(
            f"Only if this applies ({rule['if'].replace('_', ' ')}): {rule['reason']} "
            "This is a conditional library note, not a universal hazard label."
        )
    return lines[:8]


def _overall_level(ingredients: list[dict], concerns: list[dict]) -> str:
    levels = {row["evidence_level"] for row in ingredients}
    levels.update(row["evidence_level"] for row in concerns)
    if not ingredients:
        return "insufficient"
    if any(row["verification_status"] == "unknown" for row in ingredients) and "established" not in levels:
        if levels <= {"insufficient", "none"}:
            return "insufficient"
    if "conflicting" in levels:
        return "conflicting"
    if "established" in levels:
        return "established"
    if "limited" in levels:
        return "limited"
    return "insufficient"


def build_analysis(
    *,
    ingredient_text: str = "",
    ingredients: list[str] | None = None,
    product_name: str = "",
    brand: str = "",
    source_url: str = "",
    input_method: str = "manual",
    preferences: dict | None = None,
) -> dict:
    parsed = parse_and_normalize(ingredient_text, tokens=ingredients)
    preferences = preferences or {}
    rows = []
    concerns = []
    preference_matches = []
    source_ids: list[str] = []
    for row in parsed["normalized_ingredients"]:
        if row["verification_status"] == "needs_review":
            continue
        record = library_record(row.get("ingredient_id"))
        notes = notes_for(row.get("ingredient_id")) if row["verification_status"] in {"matched", "contained_match"} else []
        explanation, level, row_sources = _explanation(row, record, notes)
        for source_id in row_sources:
            if source_id not in source_ids:
                source_ids.append(source_id)
        item_concerns = _concerns(row, record, notes)
        concerns.extend(item_concerns)
        preference_matches.extend(_preference_hit(row, preferences))
        rows.append(
            {
                "original_name": row["original_name"],
                "canonical_name": row.get("canonical_name"),
                "ingredient_id": row.get("ingredient_id"),
                "category": row.get("category"),
                "function": row.get("function"),
                "match_confidence": row["match_confidence"],
                "match_source": row.get("match_source"),
                "verification_status": row["verification_status"],
                "duplicate": row["duplicate"],
                "may_contain": row["may_contain"],
                "explanation": explanation,
                "evidence_level": level,
                "conditional_notes": _conditional(record, row),
                "source_ids": row_sources,
            }
        )
    if "cosing" not in source_ids and any(row.get("ingredient_id") for row in rows):
        source_ids.append("cosing")
    sources = [public_source(source_id) for source_id in source_ids]
    sources = [source for source in sources if source]
    matched = [row for row in rows if row["verification_status"] in {"matched", "contained_match"} and not row["duplicate"]]
    unknown = list(parsed["unknown_ingredients"])
    label = product_name.strip() or "This product"
    if brand.strip():
        label = f"{label} ({brand.strip()})"
    summary = (
        f"{label}: {parsed['ingredient_count']} ingredient names were parsed. "
        f"{len(matched)} matched a retrieved library record. "
        f"{len(unknown)} stayed unverified. "
        f"{len(concerns)} documented concern note(s) were attached from those records. "
        "Ingredient order was not turned into percentages. "
        "This is not a statement that the product is safe, suitable for a person, or able to treat a condition."
    )
    warnings = list(parsed["parsing_warnings"])
    for fragment in parsed["uncertain_fragments"]:
        warnings.append(f"Needs review ({fragment['reason']}): {fragment['text']}")
    if input_method == "url" and source_url:
        warnings.append("The list came from a page fetch. Confirm it against the package.")
    return {
        "product_name": product_name.strip(),
        "brand": brand.strip(),
        "source_url": source_url.strip(),
        "input_method": input_method,
        "product_summary": summary,
        "ingredient_count": parsed["ingredient_count"],
        "matched_count": len(matched),
        "ingredients": rows,
        "concerns": concerns,
        "preference_matches": preference_matches,
        "evidence_level": _overall_level(rows, concerns),
        "sources": sources,
        "unknown_ingredients": unknown,
        "limitations": list(LIMITATIONS),
        "next_steps": list(NEXT_STEPS),
        "analysis_method": "retrieval_grounded",
        "warnings": warnings,
        "saved_id": None,
    }


def apply_model_notes(draft: dict, model: dict) -> list[str]:
    """Keep model text only when every cited source was actually retrieved. Concerns stay retrieved."""
    warnings = []
    if not isinstance(model, dict):
        return ["The model response was discarded because it was not a JSON object."]
    allowed_ids = {row["ingredient_id"] for row in draft["ingredients"] if row.get("ingredient_id")}
    allowed_sources = {source["id"] for source in draft["sources"]}
    notes = model.get("ingredient_notes")
    if notes is None:
        notes = []
    if not isinstance(notes, list):
        return ["The model response did not match the expected structure. Library text was kept."]
    by_id = {row["ingredient_id"]: row for row in draft["ingredients"] if row.get("ingredient_id")}
    used = False
    for note in notes:
        if not isinstance(note, dict):
            warnings.append("A model note was discarded because it was not an object.")
            continue
        ingredient_id = note.get("ingredient_id")
        if ingredient_id not in allowed_ids:
            warnings.append("A model note named an ingredient that was not retrieved, so it was discarded.")
            continue
        source_ids = note.get("source_ids") or []
        if not isinstance(source_ids, list) or not source_ids or not all(isinstance(item, str) for item in source_ids):
            warnings.append(f"A model note for {ingredient_id} cited a source that was not retrieved, so it was discarded.")
            continue
        if not set(source_ids) <= allowed_sources:
            warnings.append(f"A model note for {ingredient_id} cited a source that was not retrieved, so it was discarded.")
            continue
        explanation = note.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip() or _banned(explanation):
            warnings.append(f"A model note for {ingredient_id} was discarded because the wording was empty or overclaimed.")
            continue
        by_id[ingredient_id]["explanation"] = explanation.strip()
        by_id[ingredient_id]["source_ids"] = list(dict.fromkeys([*by_id[ingredient_id]["source_ids"], *source_ids]))
        used = True
    summary = model.get("product_summary")
    if isinstance(summary, str) and summary.strip() and not _banned(summary):
        draft["product_summary"] = summary.strip()
        used = True
    elif isinstance(summary, str) and summary.strip():
        warnings.append("The model summary was discarded because it overclaimed what an ingredient list can show.")
    if used:
        draft["analysis_method"] = "retrieval_grounded_model"
    else:
        draft["analysis_method"] = "retrieval_grounded"
    return warnings


def model_context(draft: dict) -> dict:
    """The only product context sent to a model. No profile notes, photos, or secrets."""
    return {
        "instructions": (
            "Rewrite explanations using only the retrieved records. "
            "Every note must cite source_ids from the supplied list. "
            "Do not add ingredients, concentrations, diseases, cures, or safety guarantees. "
            "If a fact is not in the record, say it was not verified."
        ),
        "allowed_source_ids": [source["id"] for source in draft["sources"]],
        "ingredients": [
            {
                "ingredient_id": row["ingredient_id"],
                "canonical_name": row["canonical_name"],
                "function": row["function"],
                "evidence_level": row["evidence_level"],
                "source_ids": row["source_ids"],
                "library_explanation": row["explanation"],
            }
            for row in draft["ingredients"]
            if row.get("ingredient_id")
        ],
        "library_source_note": LIBRARY["note"],
    }
