"""COSMIX web app."""

from __future__ import annotations

import os
import threading
import uuid
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import db
from app.engine import analyze, search_ingredients
from app.fetch_page import extract_from_url

STATIC = Path(__file__).resolve().parent / "static"

AGES = {"under_13", "teen", "adult"}
SKIN_TYPES = {"normal", "dry", "oily", "combination", "sensitive"}
TONES = {"fair", "light-medium", "medium", "deep"}
LIVES = {"none", "pregnant", "breastfeeding", "trying"}
CONCERNS = {"acne", "pigmentation", "dryness", "oiliness", "eczema", "rosacea", "aging", "barrier", "dandruff", "hair", "sensitive"}
ALLERGIES = {"fragrance", "parabens", "lanolin", "nuts", "salicylates", "sunscreen", "coconut", "tea_tree"}
MEDICINES = {"retinoid", "isotretinoin", "steroid"}
CATEGORIES = {"leave-on", "rinse-off", "hair-leave", "hair-rinse", "lip", "sunscreen", "body"}


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    age_group: str = "adult"
    skin_type: str = "combination"
    skin_tone: str = "medium"
    life_stage: str = "none"
    concerns: list[str] = []
    allergies: list[str] = []
    medicines: list[str] = []
    allergy_notes: str = ""
    history_notes: str = ""
    medicine_notes: str = ""


class ExtractIn(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


def _clean_profile(body: ProfileIn) -> dict:
    if body.age_group not in AGES:
        raise HTTPException(400, "Choose an age group.")
    if body.skin_type not in SKIN_TYPES:
        raise HTTPException(400, "Choose a skin type.")
    if body.skin_tone not in TONES:
        raise HTTPException(400, "Choose a skin tone.")
    if body.life_stage not in LIVES:
        raise HTTPException(400, "Choose a life stage.")
    concerns = [item for item in body.concerns if item in CONCERNS]
    allergies = [item for item in body.allergies if item in ALLERGIES]
    medicines = [item for item in body.medicines if item in MEDICINES]
    return {
        "name": body.name.strip(),
        "age_group": body.age_group,
        "skin_type": body.skin_type,
        "skin_tone": body.skin_tone,
        "life_stage": body.life_stage,
        "concerns": concerns,
        "allergies": allergies,
        "medicines": medicines,
        "allergy_notes": body.allergy_notes.strip()[:2000],
        "history_notes": body.history_notes.strip()[:4000],
        "medicine_notes": body.medicine_notes.strip()[:2000],
    }


def _sniff_image(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.data_dir()
    if os.getenv("COSMIX_OPEN_BROWSER") == "1":
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    yield


app = FastAPI(title="COSMIX", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"ok": True, "name": "COSMIX"}


@app.get("/api/ingredients")
def ingredients(q: str = ""):
    return search_ingredients(q)


@app.get("/api/profiles")
def profiles():
    return db.list_profiles()


@app.post("/api/profiles")
def create_profile(body: ProfileIn):
    return db.save_profile(_clean_profile(body))


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, body: ProfileIn):
    if not db.get_profile(profile_id):
        raise HTTPException(404, "That profile is not on this computer.")
    return db.save_profile(_clean_profile(body), profile_id)


@app.delete("/api/profiles/{profile_id}")
def remove_profile(profile_id: int):
    db.delete_profile(profile_id)
    return {"ok": True}


@app.post("/api/extract")
async def extract(body: ExtractIn):
    return await extract_from_url(body.url)


@app.post("/api/checks")
async def create_check(
    profile_id: int = Form(...),
    product_name: str = Form(""),
    source_url: str = Form(""),
    category: str = Form("leave-on"),
    ingredient_text: str = Form(""),
    photo: UploadFile | None = File(None),
):
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(400, "Save a profile first.")
    if category not in CATEGORIES:
        raise HTTPException(400, "Choose what kind of product this is.")
    ingredient_text = ingredient_text.strip()[:20000]
    product_name = product_name.strip()[:180]
    source_url = source_url.strip()[:2000]
    if not ingredient_text and not product_name:
        raise HTTPException(400, "Paste an ingredient list or a product name.")

    photo_name = None
    if photo is not None and photo.filename:
        raw = await photo.read()
        if len(raw) > 6_000_000:
            raise HTTPException(400, "That photo is larger than 6 MB.")
        suffix = _sniff_image(raw)
        if not suffix:
            raise HTTPException(400, "Use a JPG, PNG, WEBP, or GIF photo.")
        photo_name = f"{uuid.uuid4().hex}{suffix}"
        (db.data_dir() / "uploads" / photo_name).write_bytes(raw)

    result = analyze(profile, ingredient_text, category, product_name)
    return db.save_check(profile_id, product_name, source_url, category, ingredient_text, photo_name, result)


@app.get("/api/checks")
def checks(profile_id: int | None = None):
    return db.list_checks(profile_id)


@app.delete("/api/checks/{check_id}")
def remove_check(check_id: int):
    db.delete_check(check_id)
    return {"ok": True}


@app.get("/uploads/{name}")
def upload(name: str):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(404)
    path = db.data_dir() / "uploads" / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


ASSET_DIR = Path(__file__).resolve().parents[1] / "asset"
if ASSET_DIR.is_dir():
    app.mount("/media", StaticFiles(directory=ASSET_DIR), name="media")
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
