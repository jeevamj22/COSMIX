"""Versioned HTTP API. Routes validate input and call services."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app import db
from app.analysis.ai import maybe_rewrite
from app.analysis.compare import compare_products
from app.analysis.grounded import build_analysis
from app.config import load_settings
from app.extraction.adapters import platform_catalog
from app.extraction.service import extract_product
from app.ingredients.evidence import notes_for, public_source
from app.ingredients.normalize import parse_and_normalize, relationship_view
from app.schemas import (
    AnalysisIn,
    AnalysisOut,
    CompareIn,
    CompareOut,
    ExtractIn,
    ExtractOut,
    FeedbackIn,
    ParseIn,
    ParseOut,
    PreferencesIn,
)

router = APIRouter(prefix="/api/v1")
_HITS: dict[str, deque] = defaultdict(deque)
FEEDBACK_CATEGORIES = {
    "extraction",
    "identification",
    "missing_source",
    "confusing_explanation",
    "outdated_product",
    "other",
}


def _limit(request: Request) -> None:
    settings = load_settings()
    now = time.monotonic()
    key = request.client.host if request.client else "local"
    bucket = _HITS[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail={"error_code": "rate_limited", "message": "Too many requests. Wait a minute and try again."},
        )
    bucket.append(now)


def _preferences(body_preferences: PreferencesIn | None, use_saved: bool) -> dict:
    if body_preferences is not None:
        return body_preferences.model_dump()
    if use_saved:
        return db.get_preferences()
    return {"avoid": [], "prefer": [], "investigate": []}


@router.get("/products/platforms")
def platforms():
    return {"platforms": platform_catalog()}


@router.post("/products/extract", response_model=ExtractOut)
async def extract(body: ExtractIn, request: Request):
    _limit(request)
    return await extract_product(body.product_url)


@router.post("/ingredients/parse", response_model=ParseOut)
def parse(body: ParseIn, request: Request):
    _limit(request)
    try:
        return parse_and_normalize(body.raw_ingredients)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ingredients/{ingredient_id}")
def ingredient(ingredient_id: str):
    record = relationship_view(ingredient_id)
    if not record:
        raise HTTPException(status_code=404, detail="That ingredient is not in the COSMIX library.")
    source_ids = ["cosmix-library"]
    for note in notes_for(ingredient_id):
        for source_id in note["source_ids"]:
            if source_id not in source_ids:
                source_ids.append(source_id)
    sources = [public_source(source_id) for source_id in source_ids]
    return {
        "ingredient": record,
        "regulatory_notes": notes_for(ingredient_id),
        "sources": [source for source in sources if source],
        "verification_status": "curated",
        "limitations": [
            "This is the retrieved library record plus any regulatory note stored for this id.",
            "It is not a personal safety clearance and it does not include a concentration.",
        ],
    }


@router.post("/analysis", response_model=AnalysisOut)
async def analysis(body: AnalysisIn, request: Request):
    _limit(request)
    if body.input_method not in {"manual", "url"}:
        raise HTTPException(status_code=400, detail="Input method must be manual or url.")
    tokens = None
    if body.ingredients is not None:
        tokens = [item.strip() for item in body.ingredients if item and item.strip()]
    if not body.ingredient_text.strip() and not tokens:
        raise HTTPException(status_code=400, detail="Paste an ingredient list.")
    try:
        draft = build_analysis(
            ingredient_text=body.ingredient_text,
            ingredients=tokens,
            product_name=body.product_name,
            brand=body.brand,
            source_url=body.source_url,
            input_method=body.input_method,
            preferences=_preferences(body.preferences, body.use_saved_preferences),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    draft = await maybe_rewrite(draft, load_settings(), body.use_model)
    if body.save:
        text = body.ingredient_text.strip() or ", ".join(tokens or [])
        saved = db.save_analysis(draft, text)
        draft["saved_id"] = saved["saved_id"]
    return draft


@router.post("/products/compare", response_model=CompareOut)
def compare(body: CompareIn, request: Request):
    _limit(request)
    try:
        return compare_products(
            [product.model_dump() for product in body.products],
            _preferences(body.preferences, False),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/analyses")
def analyses(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return db.list_analyses(limit, offset)


@router.get("/analyses/{analysis_id}")
def analysis_detail(analysis_id: int):
    row = db.get_analysis(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail="That analysis is not on this computer.")
    return row


@router.delete("/analyses/{analysis_id}")
def remove_analysis(analysis_id: int):
    if not db.delete_analysis(analysis_id):
        raise HTTPException(status_code=404, detail="That analysis is not on this computer.")
    return {"ok": True}


@router.get("/preferences")
def read_preferences():
    return db.get_preferences()


@router.put("/preferences")
def write_preferences(body: PreferencesIn):
    return db.replace_preferences(body.model_dump())


@router.post("/feedback")
def feedback(body: FeedbackIn):
    if body.category not in FEEDBACK_CATEGORIES:
        raise HTTPException(status_code=400, detail="Choose a feedback category.")
    return db.save_feedback(
        body.category,
        body.message.strip(),
        body.product_url.strip(),
        body.ingredient_text.strip(),
        body.context.strip(),
    )


@router.get("/feedback")
def review_feedback(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    x_cosmix_admin_token: str | None = Header(default=None),
):
    settings = load_settings()
    if not settings.admin_token or not x_cosmix_admin_token or x_cosmix_admin_token != settings.admin_token:
        raise HTTPException(status_code=404, detail="Not found.")
    return db.list_feedback(limit, offset)
