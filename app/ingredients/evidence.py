"""Retrieved sources. Statements are attached only where the source supports that statement."""

from __future__ import annotations

LIBRARY = {
    "id": "cosmix-library",
    "title": "COSMIX curated ingredient library",
    "url": "",
    "publisher": "COSMIX",
    "kind": "curated_library",
    "accessed_on": "2026-10-21",
    "note": "Shopping explanations maintained with this application. Not a clinical guideline and not a peer-reviewed paper.",
}

COSING = {
    "id": "cosing",
    "title": "European Commission CosIng ingredient inventory",
    "url": "https://ec.europa.eu/growth/tools-databases/cosing/",
    "publisher": "European Commission",
    "kind": "ingredient_inventory",
    "accessed_on": "2026-10-21",
    "note": "Public inventory of cosmetic ingredient names. It is a place to cross-check spelling, not the source of the sentences in this app.",
}

EU_COSMETICS = {
    "id": "eu-cosmetics-regulation",
    "title": "Regulation (EC) No 1223/2009 on cosmetic products",
    "url": "https://eur-lex.europa.eu/eli/reg/2009/1223/oj",
    "publisher": "European Union",
    "kind": "regulation",
    "accessed_on": "2026-10-21",
    "note": "Base act of the EU cosmetics rules. Later amendments change the annexes, so a percentage or a ban should be checked against the current consolidated text. A label name is not a laboratory measurement.",
}

FDA_MERCURY = {
    "id": "fda-mercury-skin",
    "title": "Mercury poisoning linked to skin products",
    "url": "https://www.fda.gov/consumers/consumer-updates/mercury-poisoning-linked-skin-products",
    "publisher": "U.S. Food and Drug Administration",
    "kind": "regulator_notice",
    "accessed_on": "2026-10-21",
    "note": "Consumer notice about mercury in some skin products. It does not test the jar in front of you.",
}

FDA_ISOTRETINOIN = {
    "id": "fda-isotretinoin",
    "title": "Isotretinoin information",
    "url": "https://www.fda.gov/drugs/postmarket-drug-safety-information-patients-and-providers/isotretinoin",
    "publisher": "U.S. Food and Drug Administration",
    "kind": "regulator_notice",
    "accessed_on": "2026-10-21",
    "note": "This page is about the medicine. It is not a review of a cosmetic cream.",
}

SOURCES = {row["id"]: row for row in (LIBRARY, COSING, EU_COSMETICS, FDA_MERCURY, FDA_ISOTRETINOIN)}


def _steroid(display: str) -> dict:
    return {
        "statement": (
            f"{display} is a corticosteroid medicine. Glucocorticoids are not permitted as cosmetic ingredients "
            "under EU cosmetics law. A shop or a video is the wrong place to start one."
        ),
        "evidence_level": "established",
        "concern_level": "avoid",
        "source_ids": ["eu-cosmetics-regulation", "cosmix-library"],
        "limitations": "This is a classification of the substance, not a measurement of how much is in a tube and not a diagnosis of a face.",
    }


# Regulatory notes are intentionally few. If a sentence is not in this table, the app does not
# present it as an established regulatory fact.
REGULATORY_NOTES: dict[str, list[dict]] = {
    "mercury": [
        {
            "statement": "Mercury compounds do not belong in a cosmetic. EU cosmetics law prohibits them, and the U.S. FDA has warned that mercury in skin products can poison the person using them.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["eu-cosmetics-regulation", "fda-mercury-skin"],
            "limitations": "A regulation and a regulator warning are not a lab test of this package. They are a reason not to buy a product whose label names mercury.",
        }
    ],
    "hydroquinone": [
        {
            "statement": "Hydroquinone is not an ordinary cosmetic ingredient. EU cosmetics law prohibits it in cosmetic products, with a narrow exception for professional nail systems. This library does not treat skin lightening as a benefit.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["eu-cosmetics-regulation"],
            "limitations": "The exception for professional nail systems does not make a face cream a cosmetic hydroquinone product. This is not a personal prescription decision.",
        }
    ],
    "clobetasol": [_steroid("Clobetasol propionate")],
    "betamethasone": [_steroid("Betamethasone")],
    "mometasone": [_steroid("Mometasone")],
    "fluocinolone": [_steroid("Fluocinolone acetonide")],
    "hydrocortisone": [_steroid("Hydrocortisone")],
    "formaldehyde": [
        {
            "statement": "Formaldehyde is restricted in cosmetics under EU cosmetics law and is a known skin sensitiser.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["eu-cosmetics-regulation"],
            "limitations": "This record does not measure the amount in a product and does not say that every person will react.",
        }
    ],
    "mit": [
        {
            "statement": "Methylisothiazolinone is a documented contact allergen. EU cosmetics rules restrict it and do not permit it in leave-on cosmetic products.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["eu-cosmetics-regulation"],
            "limitations": "A rinse-off product is a different exposure from a leave-on product. The name on a label is not a measurement of the dose, and it is not proof that you personally will react.",
        }
    ],
    "mci": [
        {
            "statement": "Methylchloroisothiazolinone, used with methylisothiazolinone, is a documented contact allergen and is restricted in EU cosmetics, including a ban on leave-on use of the mixture.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["eu-cosmetics-regulation"],
            "limitations": "This is a regulatory and allergy record. It does not measure the amount in one product.",
        }
    ],
    "mdbgn": [
        {
            "statement": "Methyldibromo glutaronitrile is prohibited in cosmetic products under EU cosmetics law because of the rate of contact allergy.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["eu-cosmetics-regulation"],
            "limitations": "Older or non-EU packages may still list it. The legal status is not a diagnosis.",
        }
    ],
    "isotretinoin_ingredient": [
        {
            "statement": "Oral isotretinoin is a prescription medicine. The U.S. FDA describes a program to prevent pregnancy exposure because the medicine can cause severe birth defects. It is not a cosmetic ingredient.",
            "evidence_level": "established",
            "concern_level": "avoid",
            "source_ids": ["fda-isotretinoin"],
            "limitations": "This warning is about the medicine. A cosmetic label that names it is a reason to stop and ask a pharmacist or doctor, not a chemical assay of the jar.",
        }
    ],
    "parabens": [
        {
            "statement": "Parabens are cosmetic preservatives. A widespread online claim links them to cancer. That claim is not an established conclusion in the sources this application retrieves. Allergy to parabens is a separate, individual issue.",
            "evidence_level": "conflicting",
            "concern_level": None,
            "source_ids": ["cosmix-library"],
            "limitations": "Absence of an established cancer conclusion is not proof that a product suits a person who already reacts to parabens.",
        }
    ],
}


def notes_for(ingredient_id: str | None) -> list[dict]:
    if not ingredient_id:
        return []
    return list(REGULATORY_NOTES.get(ingredient_id) or [])


def source_by_id(source_id: str) -> dict | None:
    row = SOURCES.get(source_id)
    return dict(row) if row else None


def public_source(source_id: str) -> dict | None:
    row = source_by_id(source_id)
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "url": row.get("url") or "",
        "publisher": row["publisher"],
        "kind": row["kind"],
        "accessed_on": row.get("accessed_on") or "",
    }
