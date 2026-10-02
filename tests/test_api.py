import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COSMIX_DATA_DIR", str(tmp_path))
    with TestClient(app) as test_client:
        yield test_client


def _profile(name="Asha"):
    return {
        "name": name,
        "age_group": "adult",
        "skin_type": "combination",
        "skin_tone": "medium",
        "life_stage": "none",
        "concerns": ["acne"],
        "allergies": ["fragrance"],
        "medicines": [],
        "allergy_notes": "",
        "history_notes": "",
        "medicine_notes": "",
    }


def test_health_and_home_page(client):
    assert client.get("/api/health").json()["ok"] is True
    page = client.get("/")
    assert page.status_code == 200
    assert "COSMIX" in page.text


def test_check_flow_and_private_link(client):
    created = client.post("/api/profiles", json=_profile())
    assert created.status_code == 200
    profile_id = created.json()["id"]

    blocked = client.post("/api/extract", json={"url": "http://127.0.0.1/secret"})
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False

    check = client.post(
        "/api/checks",
        data={
            "profile_id": str(profile_id),
            "product_name": "Reel fairness cream",
            "category": "leave-on",
            "ingredient_text": "Water, Glycerin, Clobetasol Propionate, Fragrance",
        },
    )
    assert check.status_code == 200
    body = check.json()
    assert body["result"]["verdict"] == "do_not_use"
    assert body["photo_url"] == ""

    png = b"\x89PNG\r\n\x1a\n" + b"not-a-real-body"
    photo = client.post(
        "/api/checks",
        data={
            "profile_id": str(profile_id),
            "product_name": "Plain serum",
            "category": "leave-on",
            "ingredient_text": "Aqua, Niacinamide, Glycerin, Phenoxyethanol",
        },
        files={"photo": ("skin.png", png, "image/png")},
    )
    assert photo.status_code == 200
    assert photo.json()["photo_url"].endswith(".png")
    assert client.get(photo.json()["photo_url"]).status_code == 200

    listed = client.get("/api/checks").json()
    assert len(listed) == 2
    client.delete(f"/api/checks/{body['id']}")
    assert len(client.get("/api/checks").json()) == 1
