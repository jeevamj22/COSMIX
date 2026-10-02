"""Local storage. Profiles and checks stay in a file on this computer."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("COSMIX_DATA_DIR")
    if override:
        path = Path(override)
    else:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cosmix")
        path = Path(local) / "COSMIX"
    path.mkdir(parents=True, exist_ok=True)
    (path / "uploads").mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    directory = data_dir()
    conn = sqlite3.connect(directory / "cosmix.db")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            product_name TEXT,
            source_url TEXT,
            category TEXT,
            ingredient_text TEXT,
            photo_name TEXT,
            result TEXT NOT NULL
        )
        """
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _profile_row(row: sqlite3.Row) -> dict:
    data = json.loads(row["data"])
    data["id"] = row["id"]
    data["updated_at"] = row["updated_at"]
    return data


def list_profiles() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY updated_at DESC").fetchall()
    return [_profile_row(row) for row in rows]


def get_profile(profile_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    return _profile_row(row) if row else None


def save_profile(data: dict, profile_id: int | None = None) -> dict:
    payload = dict(data)
    payload.pop("id", None)
    payload.pop("updated_at", None)
    name = payload.get("name") or "Profile"
    stamp = _now()
    with connect() as conn:
        if profile_id:
            conn.execute(
                "UPDATE profiles SET name = ?, data = ?, updated_at = ? WHERE id = ?",
                (name, json.dumps(payload), stamp, profile_id),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO profiles (name, data, updated_at) VALUES (?, ?, ?)",
                (name, json.dumps(payload), stamp),
            )
            profile_id = cursor.lastrowid
        conn.commit()
    saved = get_profile(profile_id)
    if not saved:
        raise RuntimeError("Could not save the profile.")
    return saved


def delete_profile(profile_id: int) -> None:
    with connect() as conn:
        photos = conn.execute("SELECT photo_name FROM checks WHERE profile_id = ?", (profile_id,)).fetchall()
        conn.execute("DELETE FROM checks WHERE profile_id = ?", (profile_id,))
        conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
    for row in photos:
        _remove_photo(row["photo_name"])


def save_check(profile_id: int, product_name: str, source_url: str, category: str, ingredient_text: str, photo_name: str | None, result: dict) -> dict:
    stamp = _now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO checks (
                profile_id, created_at, product_name, source_url, category,
                ingredient_text, photo_name, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (profile_id, stamp, product_name, source_url, category, ingredient_text, photo_name, json.dumps(result)),
        )
        conn.commit()
        check_id = cursor.lastrowid
    return get_check(check_id)


def get_check(check_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone()
    return _check_row(row) if row else None


def list_checks(profile_id: int | None = None) -> list[dict]:
    with connect() as conn:
        if profile_id:
            rows = conn.execute(
                "SELECT * FROM checks WHERE profile_id = ? ORDER BY id DESC",
                (profile_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM checks ORDER BY id DESC").fetchall()
    return [_check_row(row) for row in rows]


def delete_check(check_id: int) -> None:
    with connect() as conn:
        row = conn.execute("SELECT photo_name FROM checks WHERE id = ?", (check_id,)).fetchone()
        conn.execute("DELETE FROM checks WHERE id = ?", (check_id,))
        conn.commit()
    if row:
        _remove_photo(row["photo_name"])


def _check_row(row: sqlite3.Row) -> dict:
    result = json.loads(row["result"])
    photo = row["photo_name"]
    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "created_at": row["created_at"],
        "product_name": row["product_name"],
        "source_url": row["source_url"],
        "category": row["category"],
        "ingredient_text": row["ingredient_text"],
        "photo_url": f"/uploads/{photo}" if photo else "",
        "verdict": result.get("verdict"),
        "headline": result.get("headline"),
        "result": result,
    }


def _remove_photo(name: str | None) -> None:
    if not name or "/" in name or "\\" in name or ".." in name:
        return
    path = data_dir() / "uploads" / name
    if path.is_file():
        path.unlink()
