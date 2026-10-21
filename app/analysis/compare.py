"""Compare ingredient lists without ranking one product as the winner."""

from __future__ import annotations

from app.analysis.grounded import build_analysis
from app.engine import normalize


def _identity(row: dict) -> str | None:
    if row.get("ingredient_id"):
        return f"id:{row['ingredient_id']}"
    if row["verification_status"] == "unknown":
        return f"unknown:{normalize(row['original_name'])}"
    return None


def compare_products(products: list[dict], preferences: dict | None = None) -> dict:
    if len(products) < 2:
        raise ValueError("Add at least two products to compare.")
    if len(products) > 4:
        raise ValueError("Compare up to four products at a time.")
    analyzed = []
    for index, product in enumerate(products, start=1):
        tokens = product.get("ingredients")
        text = (product.get("ingredient_text") or "").strip()
        if tokens:
            token_list = [str(item).strip() for item in tokens if str(item).strip()]
        else:
            token_list = None
        if not text and not token_list:
            raise ValueError(f"Product {index} needs an ingredient list.")
        result = build_analysis(
            ingredient_text=text,
            ingredients=token_list,
            product_name=(product.get("product_name") or "").strip() or f"Product {index}",
            brand=(product.get("brand") or "").strip(),
            source_url=(product.get("source_url") or "").strip(),
            input_method=product.get("input_method") or "manual",
            preferences=preferences,
        )
        analyzed.append(result)

    identities = []
    for result in analyzed:
        keys = {}
        for row in result["ingredients"]:
            if row["duplicate"]:
                continue
            key = _identity(row)
            if key:
                keys[key] = row
        identities.append(keys)

    shared_keys = set(identities[0])
    for keys in identities[1:]:
        shared_keys &= set(keys)
    shared = []
    for key in shared_keys:
        row = identities[0][key]
        shared.append(
            {
                "name": row.get("canonical_name") or row["original_name"],
                "verification_status": row["verification_status"],
                "function": row.get("function"),
                "unverified": key.startswith("unknown:"),
            }
        )
    shared.sort(key=lambda item: (item["unverified"], item["name"].lower()))

    unique = []
    for result, keys in zip(analyzed, identities):
        only = []
        for key, row in keys.items():
            if key in shared_keys:
                continue
            only.append(
                {
                    "name": row.get("canonical_name") or row["original_name"],
                    "verification_status": row["verification_status"],
                    "function": row.get("function"),
                    "unverified": row["verification_status"] not in {"matched", "contained_match"},
                }
            )
        only.sort(key=lambda item: item["name"].lower())
        unique.append({"product_name": result["product_name"], "ingredients": only})

    functions = []
    concerns = []
    preference_matches = []
    completeness = []
    for result in analyzed:
        seen_functions = []
        for row in result["ingredients"]:
            if row.get("function") and row["function"] not in seen_functions and row["verification_status"] in {"matched", "contained_match"}:
                seen_functions.append(row["function"])
        functions.append({"product_name": result["product_name"], "functions": seen_functions})
        concerns.append(
            {
                "product_name": result["product_name"],
                "concerns": result["concerns"],
                "unknown_ingredients": result["unknown_ingredients"],
            }
        )
        preference_matches.append({"product_name": result["product_name"], "matches": result["preference_matches"]})
        total = result["ingredient_count"] or 0
        completeness.append(
            {
                "product_name": result["product_name"],
                "ingredient_count": total,
                "matched_count": result["matched_count"],
                "unknown_count": len(result["unknown_ingredients"]),
                "incomplete": total == 0 or result["matched_count"] < total,
            }
        )

    return {
        "products": [
            {
                "product_name": result["product_name"],
                "brand": result["brand"],
                "source_url": result["source_url"],
                "ingredient_count": result["ingredient_count"],
                "evidence_level": result["evidence_level"],
            }
            for result in analyzed
        ],
        "shared_ingredients": shared,
        "unique_ingredients": unique,
        "functions": functions,
        "preference_matches": preference_matches,
        "concerns": concerns,
        "source_completeness": completeness,
        "limitations": [
            "A longer ingredient list is not a better product, and a shorter one is not a safer product.",
            "Shared names are not shared concentrations.",
            "If one product is missing names, the comparison is incomplete and neither side is declared better.",
            "Preference matches are the names you flagged. They are not a scientific ranking.",
            "No overall winner is calculated.",
        ],
    }
