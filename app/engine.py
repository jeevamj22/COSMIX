"""Turn an ingredient list and a skin profile into a shopping decision.

The same list and the same profile always produce the same result.
Nothing here calls an outside AI, so the answer cannot drift into a guess.
"""

from __future__ import annotations

import re

from app.catalog import INGREDIENTS

FLAGS = {
    "always",
    "pregnancy",
    "sensitive",
    "eczema",
    "rosacea",
    "acne",
    "dry",
    "oily",
    "pigmentation",
    "aging",
    "barrier",
    "dandruff",
    "hair",
    "fragrance_allergy",
    "paraben_allergy",
    "lanolin_allergy",
    "nut_allergy",
    "salicylate_allergy",
    "sunscreen_allergy",
    "coconut_allergy",
    "tea_tree_allergy",
    "retinoid_med",
    "isotretinoin",
    "steroid_med",
    "child",
    "teen",
    "leave_on",
    "rinse_off",
    "high_on_list",
    "deeper_tone",
}

LEVEL_RANK = {"info": 0, "helpful": 1, "caution": 2, "avoid": 3}

LEAVE_ON = {"leave-on", "hair-leave", "lip", "sunscreen", "body"}

DISCLAIMER = (
    "COSMIX compares an ingredient list with the profile you typed. "
    "It is not a doctor, not a diagnosis, and not a promise that a product will work or is safe for you. "
    "Labels often hide percentages. If you are pregnant, treating a skin disease, or already reacting, "
    "ask a dermatologist before you buy or apply the product."
)

URGENT_IDS = {
    "clobetasol",
    "betamethasone",
    "mometasone",
    "fluocinolone",
    "hydrocortisone",
    "mercury",
    "hydroquinone",
}

MEDICINE_WORDS = (
    ("isotretinoin", "isotretinoin"),
    ("accutane", "isotretinoin"),
    ("tretiva", "isotretinoin"),
    ("isotroin", "isotretinoin"),
    ("accufine", "isotretinoin"),
    ("tretinoin", "retinoid_med"),
    ("adapalene", "retinoid_med"),
    ("retino-a", "retinoid_med"),
    ("retin-a", "retinoid_med"),
    ("clobetasol", "steroid_med"),
    ("betnovate", "steroid_med"),
    ("betamethasone", "steroid_med"),
    ("mometasone", "steroid_med"),
    ("steroid", "steroid_med"),
)

_SENTINEL = "\u00a7"
_DROP_KEYS = {
    "and",
    "or",
    "with",
    "the",
    "of",
    "ingredient",
    "ingredients",
    "list",
    "composition",
    "inci",
    "active",
    "inactive",
}


def normalize(value: str) -> str:
    text = (value or "").lower().replace("’", "'").replace("–", " ").replace("—", " ")
    text = text.replace("-", " ")
    text = text.replace("/", " ")
    text = re.sub(r"[^a-z0-9.+% ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _index():
    exact = {}
    phrases = []
    seen = set()
    for item in INGREDIENTS:
        for name in item["names"]:
            key = normalize(name)
            if not key or key in seen:
                continue
            seen.add(key)
            exact[key] = item
            if len(key) >= 4:
                phrases.append((key, item))
    phrases.sort(key=lambda pair: len(pair[0]), reverse=True)
    return exact, phrases


EXACT, PHRASES = _index()


def _negated(text: str, match: re.Match) -> bool:
    prefix = text[max(0, match.start() - 18) : match.start()]
    suffix = text[match.end() : match.end() + 12]
    if re.search(r"(free of|free from|without|unscented|no|zero|non|sans)\s*$", prefix):
        return True
    if re.match(r"\s*free\b", suffix):
        return True
    return False


def phrase_in(text: str, alias: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
    return any(not _negated(text, match) for match in re.finditer(pattern, text))


def items_in_text(text: str) -> list[dict]:
    """Find library ingredients in a token or a product name.

    Longer names win over shorter ones that sit inside them, so cetyl alcohol
    is not also read as drying alcohol.
    """
    norm = normalize(text)
    if not norm:
        return []
    if norm in EXACT:
        return [EXACT[norm]]
    colorant = next(item for item in INGREDIENTS if item["id"] == "ci_colorant")
    if re.fullmatch(r"ci\s*\d{4,6}", norm):
        return [colorant]
    found = []
    spans = []
    seen = set()
    for alias, item in PHRASES:
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        for match in re.finditer(pattern, norm):
            if _negated(norm, match):
                continue
            span = match.span()
            if any(span[0] < end and span[1] > start for start, end in spans):
                continue
            spans.append(span)
            if item["id"] not in seen:
                seen.add(item["id"])
                found.append(item)
    if re.search(r"(?<![a-z0-9])ci\s*\d{4,6}(?![a-z0-9])", norm) and colorant["id"] not in seen:
        found.append(colorant)
    return found


def lookup(token: str):
    found = items_in_text(token)
    return found[0] if found else None


def split_ingredients(text: str) -> list[str]:
    if not text:
        return []
    cleaned = text.replace("’", "'").replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"(\d),(\d)", rf"\1{_SENTINEL}\2", cleaned)
    cleaned = re.sub(r"\(([^)]*)\)", lambda match: ", " + match.group(1) + ", ", cleaned)
    cleaned = cleaned.replace("•", ",").replace("·", ",").replace(";", ",")
    cleaned = cleaned.replace("|", ",").replace("\n", ",").replace("\t", ",")
    tokens = []
    seen = set()
    for part in cleaned.split(","):
        part = part.replace(_SENTINEL, ",")
        part = re.sub(r"\d+(?:\.\d+)?\s*%", " ", part)
        part = re.sub(r"[*†‡]+", " ", part)
        part = re.sub(r"\s+", " ", part).strip(" .;:-/")
        part = re.sub(
            r"^(and|ingredients?|active ingredients?|inactive ingredients?)\b",
            "",
            part,
            flags=re.I,
        ).strip(" .;:-/")
        if not part or len(part) < 2 or len(part) > 80 or len(part.split()) > 8:
            continue
        if not re.search(r"[A-Za-z]", part):
            continue
        key = normalize(part)
        if not key or key in seen or key in _DROP_KEYS:
            continue
        if key.startswith("f i l") or re.fullmatch(r"[a-z]?\d[\d ]*", key):
            continue
        seen.add(key)
        tokens.append(part.strip())
    return tokens


_FACTORY_FIL = re.compile(r"\(\s*f\s*\.?\s*i\s*\.?\s*l\s*\.?\s*:?[^)]*\)", re.I)
_FACTORY_FIL_BARE = re.compile(r"\bf\s*\.?\s*i\s*\.?\s*l\s*\.?\s*:?\s*[A-Za-z]?\d[\w./-]*", re.I)
_BATCH_PREFIX = re.compile(r"^\s*\d{3,}\s+\d{1,4}\s*[-–:]\s*", re.I)


def parse_ingredient_text(text: str) -> dict:
    raw = (text or "").strip()
    raw = _FACTORY_FIL.sub(" ", raw)
    raw = _FACTORY_FIL_BARE.sub(" ", raw)
    raw = _BATCH_PREFIX.sub("", raw)
    raw = re.sub(r"^\s*ingredients?\s*[:\-–]\s*", "", raw, flags=re.I)
    raw = re.sub(r"^\s*ingredients?\s*[:\-–]\s*", "", raw, flags=re.I)
    parts = re.split(r"\bmay contain\b\s*[:\-–]?", raw, maxsplit=1, flags=re.I)
    return {
        "tokens": split_ingredients(parts[0]),
        "may_contain": split_ingredients(parts[1]) if len(parts) > 1 else [],
    }


def flags_for(profile: dict, category: str, position: int | None) -> set[str]:
    profile = profile or {}
    flags = {"always"}
    skin = (profile.get("skin_type") or "").lower()
    tone = (profile.get("skin_tone") or "").lower()
    concerns = set(profile.get("concerns") or [])
    allergies = set(profile.get("allergies") or [])
    medicines = set(profile.get("medicines") or [])
    life = (profile.get("life_stage") or "none").lower()
    age = (profile.get("age_group") or "adult").lower()

    if skin == "sensitive" or "sensitive" in concerns:
        flags.add("sensitive")
    if skin == "dry" or "dryness" in concerns:
        flags.add("dry")
    if skin == "oily" or "oiliness" in concerns:
        flags.add("oily")
    if "acne" in concerns:
        flags.add("acne")
    if "pigmentation" in concerns:
        flags.add("pigmentation")
    if "aging" in concerns:
        flags.add("aging")
    if "eczema" in concerns:
        flags.add("eczema")
    if "rosacea" in concerns:
        flags.add("rosacea")
    if "barrier" in concerns:
        flags.add("barrier")
    if "dandruff" in concerns:
        flags.add("dandruff")
    if "hair" in concerns or category in {"hair-leave", "hair-rinse"}:
        flags.add("hair")
    if "fragrance" in allergies:
        flags.add("fragrance_allergy")
    if "parabens" in allergies:
        flags.add("paraben_allergy")
    if "lanolin" in allergies:
        flags.add("lanolin_allergy")
    if "nuts" in allergies:
        flags.add("nut_allergy")
    if "salicylates" in allergies:
        flags.add("salicylate_allergy")
    if "sunscreen" in allergies:
        flags.add("sunscreen_allergy")
    if "coconut" in allergies:
        flags.add("coconut_allergy")
    if "tea_tree" in allergies:
        flags.add("tea_tree_allergy")
    if "retinoid" in medicines:
        flags.add("retinoid_med")
    if "isotretinoin" in medicines:
        flags.add("isotretinoin")
    if "steroid" in medicines:
        flags.add("steroid_med")
    if life in {"pregnant", "breastfeeding", "trying"}:
        flags.add("pregnancy")
    if age == "under_13":
        flags.add("child")
    if age == "teen":
        flags.add("teen")
    if tone in {"medium", "deep"}:
        flags.add("deeper_tone")
    if category in LEAVE_ON:
        flags.add("leave_on")
    else:
        flags.add("rinse_off")
    if position is not None and position <= 5 and "leave_on" in flags:
        flags.add("high_on_list")

    notes = normalize(" ".join([profile.get("medicine_notes") or "", profile.get("history_notes") or ""]))
    for word, flag in MEDICINE_WORDS:
        if phrase_in(notes, word):
            flags.add(flag)
    return flags


def _allergy_note_hit(profile: dict, item: dict, token: str) -> str | None:
    notes = normalize(profile.get("allergy_notes") or "")
    if len(notes) < 4:
        return None
    keys = [normalize(token), normalize(item["display"]), *[normalize(name) for name in item["names"]]]
    for key in keys:
        if len(key) >= 5 and (phrase_in(notes, key) or phrase_in(notes, key + "s")):
            return item["display"]
    return None


def _evaluate(item: dict, flags: set[str], profile: dict, token: str, from_name: bool, may_contain: bool):
    reasons = []
    level = "info"
    for rule in item["rules"]:
        if rule["if"] not in flags:
            continue
        reasons.append({"level": rule["level"], "text": rule["reason"]})
        if LEVEL_RANK[rule["level"]] > LEVEL_RANK[level]:
            level = rule["level"]
    note_hit = _allergy_note_hit(profile, item, token)
    if note_hit:
        reasons.append(
            {
                "level": "avoid",
                "text": f"Your allergy notes mention {note_hit}. Do not use this unless a doctor has already cleared it.",
            }
        )
        level = "avoid"
    if from_name:
        reasons.insert(
            0,
            {
                "level": "info",
                "text": "This was read from the product name, not from a confirmed ingredient line. Confirm it on the pack.",
            },
        )
    if may_contain:
        reasons.append(
            {
                "level": "info",
                "text": "The label says this may be present in trace amounts.",
            }
        )
    return {
        "id": item["id"],
        "display": item["display"],
        "role": item["role"],
        "level": level,
        "reasons": reasons,
        "summary": item["summary"],
        "short_term": item["short_term"],
        "long_term": item["long_term"],
        "from_name": from_name,
        "may_contain": may_contain,
    }


def _findings_for_item(item: dict, profile: dict, category: str, position: int | None, may_contain: bool, from_name: bool, matched_text: str):
    flags = flags_for(profile, category, None if (may_contain or from_name) else position)
    found = _evaluate(item, flags, profile, matched_text, from_name, may_contain)
    found["matched_text"] = matched_text
    found["position"] = position
    return found


def analyze(profile: dict, ingredient_text: str, category: str = "leave-on", product_name: str = "") -> dict:
    parsed = parse_ingredient_text(ingredient_text)
    findings = []
    seen_ids = set()
    unknown = []
    recognized_tokens = 0

    def add(finding):
        if not finding or finding["id"] in seen_ids:
            return
        seen_ids.add(finding["id"])
        findings.append(finding)

    for index, token in enumerate(parsed["tokens"], start=1):
        matched = items_in_text(token)
        if matched:
            recognized_tokens += 1
            for item in matched:
                add(_findings_for_item(item, profile, category, index, False, False, token))
        else:
            unknown.append(token)

    for token in parsed["may_contain"]:
        matched = items_in_text(token)
        if matched:
            for item in matched:
                add(_findings_for_item(item, profile, category, None, True, False, token))
        else:
            unknown.append(token + " (may contain)")

    if product_name:
        listed = bool(parsed["tokens"])
        for item in items_in_text(product_name):
            # A full ingredient list beats marketing words in the title.
            # The title still counts when it names a drug such as a steroid.
            always_avoid = any(rule["if"] == "always" and rule["level"] == "avoid" for rule in item["rules"])
            if listed and item["id"] not in URGENT_IDS and not always_avoid:
                continue
            add(_findings_for_item(item, profile, category, None, False, True, product_name))

    findings.sort(key=lambda row: (-LEVEL_RANK[row["level"]], row.get("position") or 99))
    unknown_main = [token for token in unknown if "may contain" not in token]
    total = recognized_tokens + len(unknown_main)
    known_count = recognized_tokens
    coverage = (known_count / total) if total else 0.0
    levels = {item["level"] for item in findings}
    urgent = any(item["id"] in URGENT_IDS and item["level"] == "avoid" for item in findings)

    if total == 0 and not findings:
        verdict = "need_list"
    elif "avoid" in levels:
        verdict = "do_not_use"
    elif coverage < 0.5 and "caution" not in levels:
        verdict = "not_enough_information"
    elif "caution" in levels:
        verdict = "use_with_caution"
    else:
        verdict = "looks_compatible"

    headline, detail = _headline(verdict, findings, unknown, known_count, total)
    short_term, long_term = _timeline(verdict, findings)
    return {
        "verdict": verdict,
        "headline": headline,
        "detail": detail,
        "short_term": short_term,
        "long_term": long_term,
        "findings": findings,
        "unknown": unknown,
        "coverage": round(coverage, 2),
        "recognized": known_count,
        "total": total,
        "urgent": urgent,
        "disclaimer": DISCLAIMER,
        "category": category,
    }


def _headline(verdict: str, findings: list, unknown: list, known: int, total: int) -> tuple[str, str]:
    detail = f"Recognized {known} of {total} ingredient names." if total else "No ingredient list was provided."
    if unknown:
        detail += f" {len(unknown)} names are outside the COSMIX library, so they were not judged."
    if verdict == "need_list":
        return (
            "Paste the ingredient list before COSMIX can answer.",
            "A product link alone is not enough when the shop hides the list.",
        )
    if verdict == "do_not_use":
        return (
            "Do not buy this from the profile you entered.",
            detail,
        )
    if verdict == "use_with_caution":
        extra = " This check is incomplete because some names were not recognized." if total and known / total < 0.5 else ""
        return (
            "Part of this list conflicts with your profile.",
            detail + extra,
        )
    if verdict == "not_enough_information":
        return (
            "Too much of this list is unknown, so COSMIX will not call it suitable.",
            detail,
        )
    return (
        "Nothing in the recognized list directly conflicts with your profile. That is not a promise the product will work.",
        detail,
    )


def _timeline(verdict: str, findings: list) -> tuple[list[str], list[str]]:
    short, long = [], []
    for finding in findings:
        if finding["level"] not in {"avoid", "caution", "helpful"}:
            continue
        if finding["short_term"]:
            short.append(f"{finding['display']}: {finding['short_term']}")
        if finding["long_term"]:
            long.append(f"{finding['display']}: {finding['long_term']}")
    short = short[:7]
    long = long[:7]
    if verdict == "need_list":
        return (
            ["There is no short-term answer until the ingredient list is here."],
            ["There is no long-term answer until the ingredient list is here."],
        )
    if verdict == "not_enough_information" and not short:
        return (
            ["There is no honest short-term prediction while most of the list is unrecognized."],
            ["Add the missing names to the library, or ask a dermatologist to read the full list, before you trust a long-term answer."],
        )
    if not short:
        short.append(
            "The ingredients we recognized do not clash with the boxes you ticked. In the first week, stop if you get stinging, itching, or a new rash."
        )
    if not long:
        long.append(
            "Whether it helps over months depends on the percentages, which many labels hide, and on the rest of your routine."
        )
    return short, long


def search_ingredients(query: str = "") -> list[dict]:
    needle = normalize(query)
    rows = []
    for item in INGREDIENTS:
        blob = normalize(" ".join([item["display"], item["role"], item["summary"], *item["names"]]))
        if needle and needle not in blob:
            continue
        rows.append(
            {
                "id": item["id"],
                "display": item["display"],
                "role": item["role"],
                "names": item["names"],
                "summary": item["summary"],
                "short_term": item["short_term"],
                "long_term": item["long_term"],
            }
        )
    rows.sort(key=lambda row: (row["role"], row["display"]))
    return rows
