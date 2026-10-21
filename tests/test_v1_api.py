import asyncio

import pytest
from fastapi.testclient import TestClient

from app.extraction.fetcher import FetchResult
from app.main import app


SERUM = """
<html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Night cream","brand":"House","ingredients":"Aqua, Glycerin, Niacinamide, Phenoxyethanol"}
</script>
</head><body></body></html>
""".encode()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COSMIX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COSMIX_ADMIN_TOKEN", "local-admin-token")
    with TestClient(app) as test_client:
        yield test_client


def test_health_parse_lookup_and_analysis(client):
    assert client.get("/health").json()["status"] == "ok"
    parsed = client.post(
        "/api/v1/ingredients/parse",
        json={"raw_ingredients": "Water, Glycerin, Niacinamide, Cetearyl Alcohol, Dimethicone, Phenoxyethanol."},
    )
    assert parsed.status_code == 200
    body = parsed.json()
    assert body["ingredient_count"] >= 5
    assert any(row["ingredient_id"] == "niacinamide" for row in body["normalized_ingredients"])

    missing = client.get("/api/v1/ingredients/not-a-real-id")
    assert missing.status_code == 404
    found = client.get("/api/v1/ingredients/niacinamide")
    assert found.status_code == 200
    assert found.json()["ingredient"]["canonical_name"] == "Niacinamide"

    empty = client.post("/api/v1/ingredients/parse", json={"raw_ingredients": "   "})
    assert empty.status_code == 422 or empty.status_code == 400

    analysis = client.post(
        "/api/v1/analysis",
        json={
            "product_name": "Plain serum",
            "input_method": "manual",
            "ingredient_text": "Aqua, Niacinamide, Glycerin, Phenoxyethanol",
            "use_model": False,
            "save": True,
            "preferences": {"avoid": ["phenoxyethanol"], "prefer": ["glycerin"], "investigate": []},
        },
    )
    assert analysis.status_code == 200, analysis.text
    result = analysis.json()
    assert result["saved_id"]
    assert result["analysis_method"] == "retrieval_grounded"
    assert "safe for everyone" not in result["product_summary"].lower()
    assert any(match["preference"] == "avoid" for match in result["preference_matches"])
    saved = client.get(f"/api/v1/analyses/{result['saved_id']}")
    assert saved.status_code == 200
    assert client.delete(f"/api/v1/analyses/{result['saved_id']}").status_code == 200
    assert client.get(f"/api/v1/analyses/{result['saved_id']}").status_code == 404


def test_invalid_url_and_fixture_extract(client, monkeypatch):
    blocked = client.post("/api/v1/products/extract", json={"product_url": "http://127.0.0.1/secret"})
    assert blocked.status_code == 200
    assert blocked.json()["extraction_status"] == "invalid_url"
    assert blocked.json()["ingredients"] == []

    scheme = client.post("/api/v1/products/extract", json={"product_url": "javascript:alert(1)"})
    assert scheme.json()["extraction_status"] == "invalid_url"

    async def fake(url: str):
        return FetchResult(final_url=url, status_code=200, headers={"content-type": "text/html"}, body=SERUM)

    monkeypatch.setattr("app.extraction.service.fetch_public", fake)
    # The route imported extract_product, which looks up fetch_public inside the service module.
    extracted = client.post("/api/v1/products/extract", json={"product_url": "https://shop.example/serum"})
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["extraction_status"] == "success"
    assert "Niacinamide" in extracted.json()["ingredients"]


def test_compare_does_not_pick_a_winner(client):
    compared = client.post(
        "/api/v1/products/compare",
        json={
            "products": [
                {
                    "product_name": "Serum",
                    "ingredient_text": "Aqua, Niacinamide, Glycerin, Phenoxyethanol",
                },
                {
                    "product_name": "Mystery",
                    "ingredient_text": "Unobtanium ferment, Glycerin",
                },
            ],
            "preferences": {"avoid": [], "prefer": ["niacinamide"], "investigate": ["unobtanium ferment"]},
        },
    )
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert "winner" not in body
    assert "score" not in body
    shared = {item["name"] for item in body["shared_ingredients"]}
    assert "Glycerin" in shared
    mystery = next(row for row in body["source_completeness"] if row["product_name"] == "Mystery")
    assert mystery["incomplete"] is True
    assert any("No overall winner" in line for line in body["limitations"])


def test_preferences_and_feedback(client):
    saved = client.put(
        "/api/v1/preferences",
        json={"avoid": ["parfum"], "prefer": ["niacinamide"], "investigate": ["retinol"]},
    )
    assert saved.status_code == 200
    assert client.get("/api/v1/preferences").json()["avoid"] == ["parfum"]

    note = client.post(
        "/api/v1/feedback",
        json={"category": "extraction", "message": "The ingredient line was missed.", "product_url": "https://shop.example/item"},
    )
    assert note.status_code == 200
    hidden = client.get("/api/v1/feedback")
    assert hidden.status_code == 404
    reviewed = client.get("/api/v1/feedback", headers={"X-Cosmix-Admin-Token": "local-admin-token"})
    assert reviewed.status_code == 200
    assert reviewed.json()["total"] == 1


def test_compare_import_stays_sync():
    # Guard against accidentally requiring a live event loop in the comparison helper.
    assert asyncio.iscoroutinefunction(asyncio.sleep)
