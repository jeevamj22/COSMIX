import asyncio

import pytest

from app.analysis.grounded import apply_model_notes, build_analysis
from app.extraction.fetcher import FetchResult, content_type_error, enforce_size
from app.extraction.service import extract_product
from app.extraction.validator import resolve_redirect
from app.ingredients.normalize import parse_and_normalize


SERUM = """
<html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Night cream","brand":{"name":"House"},"image":"https://cdn.example.com/cream.jpg","ingredients":"Aqua, Glycerin, Niacinamide, Phenoxyethanol"}
</script>
</head><body><h1>Night cream</h1></body></html>
""".encode()


def test_private_redirect_is_rejected():
    with pytest.raises(ValueError):
        resolve_redirect("https://shop.example/item", "http://169.254.169.254/latest/meta-data")
    with pytest.raises(ValueError):
        resolve_redirect("https://shop.example/item", "http://127.0.0.1/admin")
    with pytest.raises(ValueError):
        resolve_redirect("https://shop.example/item", "http://10.1.1.1/secret")


def test_oversized_and_unexpected_types_are_rejected():
    with pytest.raises(ValueError):
        enforce_size(str(2_000_000), b"short")
    with pytest.raises(ValueError):
        enforce_size(None, b"x" * 1_500_001)
    assert content_type_error("image/jpeg")
    assert content_type_error("application/pdf")
    assert content_type_error("text/html") is None


def test_fixture_page_extracts_without_calling_the_network():
    async def fake(url: str):
        return FetchResult(final_url=url, status_code=200, headers={"content-type": "text/html"}, body=SERUM)

    result = asyncio.run(extract_product("https://shop.example/serum", fetch=fake))
    assert result["extraction_status"] == "success"
    assert result["product_name"] == "Night cream"
    assert result["brand"] == "House"
    assert result["product_image"].startswith("https://cdn.example.com/")
    assert "Niacinamide" in result["ingredients"]
    assert result["error_code"] is None


def test_script_shell_is_not_a_successful_extraction():
    html = b"<html><body><div id='root'>Please enable javascript</div></body></html>"

    async def fake(url: str):
        return FetchResult(final_url=url, status_code=200, headers={"content-type": "text/html"}, body=html)

    result = asyncio.run(extract_product("https://shop.example/app", fetch=fake))
    assert result["extraction_status"] == "javascript_required"
    assert result["ingredients"] == []
    assert "manually" in result["message"].lower()


def test_blocked_page_does_not_invent_ingredients():
    async def fake(url: str):
        return FetchResult(final_url=url, status_code=403, headers={"content-type": "text/html"}, body=b"denied")

    result = asyncio.run(extract_product("https://shop.example/locked", fetch=fake))
    assert result["extraction_status"] == "login_required"
    assert result["ingredients"] == []


def test_parser_keeps_uncertain_text_and_duplicates():
    parsed = parse_and_normalize("Aqua, Glycerin, Glycerin, 12345, " + ("Verylongname " * 12))
    names = [row["original_name"].lower() for row in parsed["normalized_ingredients"]]
    assert names.count("glycerin") == 2
    assert any(row["duplicate"] for row in parsed["normalized_ingredients"])
    assert parsed["uncertain_fragments"]
    assert any("12345" in item["text"] for item in parsed["uncertain_fragments"])


def test_unknown_name_is_not_assigned_an_identity():
    parsed = parse_and_normalize("Unobtanium ferment")
    row = parsed["normalized_ingredients"][0]
    assert row["canonical_name"] is None
    assert row["verification_status"] == "unknown"
    assert "Unobtanium ferment" in parsed["unknown_ingredients"]


def test_niacinamide_matches_the_library_alias():
    parsed = parse_and_normalize("Niacinamide")
    row = parsed["normalized_ingredients"][0]
    assert row["ingredient_id"] == "niacinamide"
    assert row["match_confidence"] == "high"
    assert row["match_source"] == "cosmix-library"


def test_analysis_does_not_call_a_plain_serum_safe_or_invent_a_paper():
    result = build_analysis(ingredient_text="Aqua, Glycerin, Niacinamide, Phenoxyethanol", product_name="Plain serum")
    blob = result["product_summary"].lower() + " ".join(row["explanation"].lower() for row in result["ingredients"])
    assert "guaranteed safe" not in blob
    assert "cure" not in blob
    assert all(source["id"] in {"cosmix-library", "cosing"} for source in result["sources"])
    assert all(row["canonical_name"] for row in result["ingredients"])


def test_unknown_analysis_stays_unverified():
    result = build_analysis(ingredient_text="Unobtanium ferment, Zorblax polymer")
    assert result["evidence_level"] == "insufficient"
    assert result["concerns"] == []
    assert result["matched_count"] == 0
    assert "did not match" in result["ingredients"][0]["explanation"].lower()


def test_mercury_concern_cites_only_retrieved_sources():
    result = build_analysis(ingredient_text="Aqua, Glycerin, Mercury")
    mercury = next(row for row in result["concerns"] if row["ingredient_id"] == "mercury")
    assert mercury["evidence_level"] == "established"
    assert "eu-cosmetics-regulation" in mercury["source_ids"]
    assert "fda-mercury-skin" in mercury["source_ids"]
    assert all(not source_id.startswith("pmid") for source_id in mercury["source_ids"])


def test_preference_match_is_not_described_as_a_scientific_finding():
    result = build_analysis(
        ingredient_text="Aqua, Glycerin, Parfum",
        preferences={"avoid": ["fragrance"], "prefer": [], "investigate": []},
    )
    assert result["preference_matches"]
    assert "not a new scientific finding" in result["preference_matches"][0]["note"]
    assert result["preference_matches"][0]["preference"] == "avoid"


def test_model_cannot_add_a_fake_citation_or_a_new_ingredient():
    draft = build_analysis(ingredient_text="Aqua, Niacinamide")
    warnings = apply_model_notes(
        draft,
        {
            "product_summary": "This product is guaranteed safe and cures acne.",
            "ingredient_notes": [
                {
                    "ingredient_id": "niacinamide",
                    "explanation": "See the invented trial.",
                    "source_ids": ["pmid-000"],
                },
                {
                    "ingredient_id": "not-in-the-list",
                    "explanation": "Secret steroid.",
                    "source_ids": ["cosmix-library"],
                },
            ],
        },
    )
    niacinamide = next(row for row in draft["ingredients"] if row["ingredient_id"] == "niacinamide")
    assert "pmid-000" not in niacinamide["source_ids"]
    assert "invented trial" not in niacinamide["explanation"]
    assert "guaranteed safe" not in draft["product_summary"].lower()
    assert any("not retrieved" in warning for warning in warnings)
    assert draft["analysis_method"] == "retrieval_grounded"


def test_model_text_is_kept_when_the_citation_was_retrieved():
    draft = build_analysis(ingredient_text="Aqua, Niacinamide")
    apply_model_notes(
        draft,
        {
            "ingredient_notes": [
                {
                    "ingredient_id": "niacinamide",
                    "explanation": "The retrieved library calls this a vitamin B3 ingredient. The concentration in this bottle was not verified.",
                    "source_ids": ["cosmix-library"],
                }
            ]
        },
    )
    niacinamide = next(row for row in draft["ingredients"] if row["ingredient_id"] == "niacinamide")
    assert "not verified" in niacinamide["explanation"]
    assert draft["analysis_method"] == "retrieval_grounded_model"
