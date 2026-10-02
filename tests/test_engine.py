from app.catalog import INGREDIENTS
from app.engine import FLAGS, LEVEL_RANK, analyze, normalize, parse_ingredient_text


def shopper(**overrides):
    profile = {
        "name": "Example",
        "age_group": "adult",
        "skin_type": "combination",
        "skin_tone": "medium",
        "life_stage": "none",
        "concerns": ["acne", "pigmentation"],
        "allergies": ["fragrance"],
        "medicines": [],
        "allergy_notes": "",
        "history_notes": "",
        "medicine_notes": "",
    }
    profile.update(overrides)
    return profile


def test_library_ids_and_aliases_are_unique():
    ids = set()
    aliases = {}
    for item in INGREDIENTS:
        assert item["id"] not in ids
        ids.add(item["id"])
        for name in item["names"]:
            key = normalize(name)
            assert key not in aliases, key
            aliases[key] = item["id"]
        for rule in item["rules"]:
            assert rule["if"] in FLAGS
            assert rule["level"] in LEVEL_RANK


def test_school_sheet_error_is_not_in_the_engine():
    # The classroom PDF calls sodium isethionate "sodium hydroxide". It is not.
    result = analyze(shopper(), "Sodium Cocoyl Isethionate, Aqua, Glycerin", "rinse-off")
    assert "sodium_hydroxide" not in {item["id"] for item in result["findings"]}


def test_fatty_alcohol_is_not_drying_alcohol():
    result = analyze(
        shopper(allergies=[], concerns=[]),
        "Cetyl Alcohol, Cetearyl Alcohol, Glycerin, Aqua",
        "leave-on",
    )
    ids = {item["id"] for item in result["findings"]}
    assert "fatty_alcohol" in ids
    assert "alcohol_denat" not in ids


def test_phenoxyethanol_is_not_alcohol():
    result = analyze(shopper(allergies=[], concerns=[]), "Aqua, Glycerin, Phenoxyethanol", "leave-on")
    assert "alcohol_denat" not in {item["id"] for item in result["findings"]}
    assert result["verdict"] == "looks_compatible"


def test_steroid_cream_is_do_not_use():
    result = analyze(
        shopper(),
        "Water, Glycerin, Stearic Acid, Clobetasol Propionate, Fragrance, Methylparaben",
        "leave-on",
        "Reel fairness cream",
    )
    assert result["verdict"] == "do_not_use"
    assert result["urgent"] is True
    assert any(item["id"] == "clobetasol" for item in result["findings"])


def test_brand_name_catches_a_steroid_without_an_ingredient_list():
    result = analyze(shopper(allergies=[], concerns=[]), "", "leave-on", "Tenovate cream")
    assert result["verdict"] == "do_not_use"
    assert any(item["id"] == "clobetasol" for item in result["findings"])


def test_fragrance_allergy_stops_parfum():
    result = analyze(shopper(), "Aqua, Glycerin, Niacinamide, Parfum, Limonene", "leave-on")
    assert result["verdict"] == "do_not_use"
    assert any(item["id"] == "fragrance" and item["level"] == "avoid" for item in result["findings"])


def test_fragrance_free_name_does_not_invent_fragrance():
    result = analyze(
        shopper(),
        "Aqua, Niacinamide, Glycerin, Pentylene Glycol, Phenoxyethanol",
        "leave-on",
        "Fragrance Free Niacinamide Serum",
    )
    assert "fragrance" not in {item["id"] for item in result["findings"]}
    assert result["verdict"] == "looks_compatible"


def test_plain_serum_can_support_acne_without_promising_a_cure():
    result = analyze(
        shopper(),
        "Aqua, Niacinamide, Glycerin, Zinc PCA, Pentylene Glycol, Phenoxyethanol",
        "leave-on",
    )
    assert result["verdict"] == "looks_compatible"
    assert "will work" in result["headline"].lower()
    niacinamide = next(item for item in result["findings"] if item["id"] == "niacinamide")
    assert niacinamide["level"] == "helpful"


def test_unknown_list_is_not_called_safe():
    result = analyze(shopper(allergies=[], concerns=[]), "Unobtanium ferment, Zorblax polymer, Foo leaf", "leave-on")
    assert result["verdict"] == "not_enough_information"
    assert "safe" not in result["headline"].lower()


def test_pregnancy_blocks_retinol():
    result = analyze(
        shopper(life_stage="pregnant", allergies=[], concerns=["aging"]),
        "Aqua, Retinol, Glycerin, Dimethicone",
        "leave-on",
    )
    assert result["verdict"] == "do_not_use"
    assert any(item["id"] == "retinol" and item["level"] == "avoid" for item in result["findings"])


def test_hydroquinone_is_not_scored_as_whitening_help():
    item = next(row for row in INGREDIENTS if row["id"] == "hydroquinone")
    assert all(rule["level"] != "helpful" for rule in item["rules"])
    assert "whitening" not in item["summary"].lower() or "does not" in item["summary"].lower()


def test_glutathione_is_not_a_whitening_benefit():
    item = next(row for row in INGREDIENTS if row["id"] == "glutathione")
    assert item["rules"] == []
    assert "weak" in item["summary"].lower()


def test_comma_inside_a_chemical_name_stays_one_ingredient():
    parsed = parse_ingredient_text("2-Bromo-2-nitropropane-1,3-diol, Aqua, Glycerin")
    assert any("bromo" in token.lower() for token in parsed["tokens"])
    assert len([token for token in parsed["tokens"] if "bromo" in token.lower()]) == 1


def test_colour_index_is_recognized():
    result = analyze(shopper(allergies=[], concerns=[]), "Aqua, CI 77491, Mica", "leave-on")
    assert result["verdict"] == "looks_compatible"
    assert any(item["id"] == "ci_colorant" for item in result["findings"])


def test_peanut_oil_is_ordinary_until_the_allergy_is_set():
    plain = analyze(shopper(allergies=[], concerns=[]), "Peanut oil, Glycerin, Aqua", "body")
    allergic = analyze(shopper(allergies=["nuts"], concerns=[]), "Peanut oil, Glycerin, Aqua", "body")
    assert plain["verdict"] != "do_not_use"
    assert allergic["verdict"] == "do_not_use"


def test_aging_goal_marks_bakuchiol_as_helpful():
    result = analyze(
        shopper(life_stage="none", allergies=[], concerns=["aging"], skin_type="normal"),
        "Aqua, Bakuchiol, Glycerin",
        "leave-on",
    )
    assert any(item["id"] == "bakuchiol" and item["level"] == "helpful" for item in result["findings"])


def test_vitamin_c_in_the_product_name_is_not_treated_as_an_ingredient():
    result = analyze(
        shopper(allergies=[], concerns=["pigmentation"]),
        "Water, Glycerin, Stearic Acid, Fragrance",
        "rinse-off",
        "Garnier Bright Complete Vitamin C Face Wash",
    )
    assert "ascorbic" not in {item["id"] for item in result["findings"]}


def test_high_alcohol_on_a_leave_on_is_a_caution():
    result = analyze(
        shopper(allergies=[], concerns=[], skin_type="normal"),
        "Alcohol Denat., Aqua, Glycerin, Phenoxyethanol",
        "leave-on",
    )
    alcohol = next(item for item in result["findings"] if item["id"] == "alcohol_denat")
    assert alcohol["level"] == "caution"
    assert result["verdict"] == "use_with_caution"


WASH = (
    "936183 31 - INGREDIENTS: WATER, GLYCERIN, MYRISTIC ACID, PALMITIC ACID, STEARIC ACID, "
    "POTASSIUM HYDROXIDE, LAURIC ACID, GLYCERYL DISTEARATE, GLYCERYL STEARATE, KAOLIN, PEG-14M, "
    "LINALOOL, SALICYLIC ACID, PHENOXYETHANOL, LIMONENE, ASCORBYL GLUCOSIDE, TETRASODIUM EDTA, "
    "LEMON FRUIT EXTRACT, CITRUS JUNOS FRUIT EXTRACT, MALTODEXTRIN, BENZYL SALICYLATE, "
    "BENZYL ALCOHOL, FRAGRANCE. (F.I.L.: C277222/1)."
)


def test_factory_codes_are_not_ingredients():
    tokens = parse_ingredient_text(WASH)["tokens"]
    blob = " ".join(tokens).lower()
    assert "936183" not in blob
    assert "c277222" not in blob
    assert "f.i.l" not in blob
    assert any(token.lower() == "water" for token in tokens)


def test_soap_wash_chemicals_are_known_and_potassium_hydroxide_is_not_lye_on_skin():
    result = analyze(shopper(), WASH, "rinse-off", "Garnier Bright Complete Vitamin C Face Wash")
    unknown = {item.lower() for item in result["unknown"]}
    for name in [
        "myristic acid",
        "palmitic acid",
        "potassium hydroxide",
        "lauric acid",
        "glyceryl distearate",
        "kaolin",
        "peg-14m",
        "lemon fruit extract",
        "citrus junos fruit extract",
        "maltodextrin",
    ]:
        assert name not in unknown
    ids = {item["id"] for item in result["findings"]}
    assert "potassium_hydroxide" in ids
    assert "ascorbyl_glucoside" in ids
    assert "citrus_extract" in ids
    assert "ascorbic" not in ids
    hydroxide = next(item for item in result["findings"] if item["id"] == "potassium_hydroxide")
    assert hydroxide["level"] == "info"
    assert result["verdict"] == "do_not_use"
