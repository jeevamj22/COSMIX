import pytest

from app.engine import analyze
from app.ingredients.official import STATEMENTS, import_official_csv, list_status


SAMPLE = """chemical name,annex,reference,health_claim
Mercury,II,Annex II,This product will clear acne.
Hydroquinone,Annex II,31,This will brighten skin.
Methylisothiazolinone,III,57,Safe for babies.
Not a row,, ,
"""


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("COSMIX_DATA_DIR", str(tmp_path))


def test_import_keeps_only_the_official_status(isolated):
    result = import_official_csv(SAMPLE)
    assert result == {"imported": 3, "skipped": 1}
    assert list_status("mercury") == "banned"
    assert list_status("Hydroquinone") == "banned"
    assert list_status("methylisothiazolinone") == "restricted"
    assert list_status("glycerin") == "not_on_the_list"

    from app.db import connect

    with connect() as conn:
        rows = conn.execute("SELECT statement, review_status FROM draft_cards").fetchall()
    texts = " ".join(row["statement"] for row in rows)
    assert "clear acne" not in texts
    assert "brighten" not in texts
    assert "Safe for babies" not in texts
    assert all(row["review_status"] == "from official list" for row in rows)
    assert STATEMENTS["banned"] in texts
    assert STATEMENTS["restricted"] in texts


def test_a_second_import_does_not_duplicate(isolated):
    import_official_csv(SAMPLE)
    import_official_csv(SAMPLE)
    from app.ingredients.official import draft_count

    assert draft_count() == 3


def test_draft_cards_do_not_change_a_product_check(isolated):
    import_official_csv("chemical name,annex\nUnobtanium chloride,II\n")
    profile = {
        "name": "Example",
        "age_group": "adult",
        "skin_type": "combination",
        "skin_tone": "medium",
        "life_stage": "none",
        "concerns": [],
        "allergies": [],
        "medicines": [],
        "allergy_notes": "",
        "history_notes": "",
        "medicine_notes": "",
    }
    result = analyze(profile, "Unobtanium chloride, Aqua", "leave-on")
    assert result["verdict"] != "do_not_use"
    assert "unobtanium chloride" in {name.lower() for name in result["unknown"]}
