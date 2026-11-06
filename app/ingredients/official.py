"""Draft cards copied from an official EU cosmetics annex list.

A card may say only that a name is banned, restricted, or not on the list.
Extra sentences in a file are ignored. Draft cards do not change a product check.
"""

from __future__ import annotations

import csv
import io

from app.db import _now, connect
from app.engine import normalize

SOURCE_URL = "https://eur-lex.europa.eu/eli/reg/2009/1223/2026-05-18/eng"
SOURCE_TITLE = "Regulation (EC) No 1223/2009, consolidated text"
REVIEW_STATUS = "from official list"

STATEMENTS = {
    "banned": (
        "This name is on Annex II of Regulation (EC) No 1223/2009, "
        "the list of substances prohibited in cosmetic products."
    ),
    "restricted": (
        "This name is on Annex III of Regulation (EC) No 1223/2009, "
        "the list of substances subject to restrictions in cosmetic products."
    ),
}

_NAME_FIELDS = ("chemical name", "substance name", "inci name", "inci_name", "substance", "name")
_ANNEX_FIELDS = ("annex", "list", "status")
_REFERENCE_FIELDS = ("reference", "ref no", "ref", "entry", "ec no", "cas no")

_ANNEX = {
    "ii": ("II", "banned"),
    "2": ("II", "banned"),
    "annex ii": ("II", "banned"),
    "annex 2": ("II", "banned"),
    "prohibited": ("II", "banned"),
    "banned": ("II", "banned"),
    "iii": ("III", "restricted"),
    "3": ("III", "restricted"),
    "annex iii": ("III", "restricted"),
    "annex 3": ("III", "restricted"),
    "restricted": ("III", "restricted"),
}


def _cell(row: dict, names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(name)
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _rows(text: str) -> list[dict]:
    sample = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(sample))
    if not reader.fieldnames:
        raise ValueError("The official file needs a header row.")
    cleaned = []
    for raw in reader:
        row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
        cleaned.append(row)
    return cleaned


def import_official_csv(text: str) -> dict:
    """Copy annex rows into draft cards. Returns counts. Does not judge products."""
    imported = 0
    skipped = 0
    stamp = _now()
    with connect() as conn:
        for row in _rows(text):
            display = _cell(row, _NAME_FIELDS)
            annex_key = normalize(_cell(row, _ANNEX_FIELDS))
            mapped = _ANNEX.get(annex_key)
            if not display or not mapped:
                skipped += 1
                continue
            annex, status = mapped
            key = normalize(display)
            if not key:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO draft_cards (
                    name_key, display_name, annex, list_status, reference_code,
                    statement, source_url, source_title, review_status, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name_key, annex) DO UPDATE SET
                    display_name = excluded.display_name,
                    list_status = excluded.list_status,
                    reference_code = excluded.reference_code,
                    statement = excluded.statement,
                    source_url = excluded.source_url,
                    source_title = excluded.source_title,
                    review_status = excluded.review_status,
                    imported_at = excluded.imported_at
                """,
                (
                    key,
                    display[:300],
                    annex,
                    status,
                    _cell(row, _REFERENCE_FIELDS)[:80] or None,
                    STATEMENTS[status],
                    SOURCE_URL,
                    SOURCE_TITLE,
                    REVIEW_STATUS,
                    stamp,
                ),
            )
            imported += 1
    return {"imported": imported, "skipped": skipped}


def list_status(name: str) -> str:
    """banned, restricted, or not_on_the_list. A ban wins if both annexes name it."""
    key = normalize(name)
    if not key:
        return "not_on_the_list"
    with connect() as conn:
        rows = conn.execute(
            "SELECT list_status FROM draft_cards WHERE name_key = ?",
            (key,),
        ).fetchall()
    statuses = {row["list_status"] for row in rows}
    if "banned" in statuses:
        return "banned"
    if "restricted" in statuses:
        return "restricted"
    return "not_on_the_list"


def draft_count() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM draft_cards").fetchone()
    return int(row["n"])
