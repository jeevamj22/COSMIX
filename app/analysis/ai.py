"""Optional language-model rewrite. The app still returns a result when this is unconfigured or down."""

from __future__ import annotations

import json
import logging

import httpx

from app.analysis.grounded import apply_model_notes, model_context
from app.config import Settings

logger = logging.getLogger("cosmix.ai")


def _parse_json(content: str) -> dict | None:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


async def _complete(settings: Settings, context: dict) -> dict | None:
    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": settings.ai_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You explain cosmetic ingredients from supplied records only. "
                    "Return JSON with keys product_summary and ingredient_notes. "
                    "ingredient_notes is a list of objects with ingredient_id, explanation, and source_ids. "
                    "source_ids must be chosen from allowed_source_ids. "
                    "Never invent a citation, a concentration, a cure, or a guarantee of safety."
                ),
            },
            {"role": "user", "content": json.dumps(context)},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(settings.ai_timeout_seconds, connect=5.0)
    last_error = "The language model did not return a usable response."
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=body)
            if response.status_code in {429, 500, 502, 503, 504} and attempt == 1:
                last_error = "The language model was busy."
                continue
            if response.status_code >= 400:
                logger.info("ai provider status=%s", response.status_code)
                return None
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return _parse_json(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            logger.info("ai provider failed attempt=%s", attempt)
            if attempt == 2:
                return None
            last_error = "The language model did not answer in time."
    logger.info("ai provider gave up: %s", last_error)
    return None


async def maybe_rewrite(draft: dict, settings: Settings, use_model: bool) -> dict:
    if not use_model or not settings.ai_enabled:
        draft["analysis_method"] = "retrieval_grounded"
        if use_model and not settings.ai_enabled:
            draft["warnings"].append("No AI key is configured. The explanation uses retrieved library records only.")
        return draft
    model = await _complete(settings, model_context(draft))
    if model is None:
        draft["warnings"].append("The language model was unavailable. Retrieved library text was kept, and no citation was added by the model.")
        draft["analysis_method"] = "retrieval_grounded"
        return draft
    draft["warnings"].extend(apply_model_notes(draft, model))
    return draft
