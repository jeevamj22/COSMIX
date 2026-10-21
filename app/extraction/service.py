"""Turn a product URL into a normalized extraction result. Business rules stay out of the route."""

from __future__ import annotations

from urllib.parse import urlparse

from app.engine import parse_ingredient_text
from app.extraction.fetcher import FetchResult, fetch_public
from app.extraction.html_extractor import (
    ingredients_from_html,
    looks_like_script_shell,
    manual_fallback,
    platform_method,
    safe_image_url,
    shop_wall_message,
)
from app.extraction.validator import page_host

_SUCCESS_SCORE = 3


def _empty(status: str, message: str, error_code: str | None, **extra) -> dict:
    result = {
        "extraction_status": status,
        "product_name": "",
        "brand": "",
        "product_image": "",
        "canonical_product_url": "",
        "ingredients": [],
        "ingredient_text": "",
        "source_url": "",
        "extraction_method": "",
        "warnings": [],
        "error_code": error_code,
        "message": manual_fallback(message),
    }
    result.update(extra)
    return result


def _status_from_http(fetched: FetchResult) -> dict | None:
    if fetched.error_code == "invalid_url":
        return _empty("invalid_url", fetched.message, "invalid_url")
    if fetched.error_code == "unavailable":
        return _empty("unavailable", fetched.message, "unavailable", canonical_product_url=fetched.final_url, source_url=fetched.final_url)
    if fetched.error_code == "response_too_large":
        return _empty("inaccessible", fetched.message, "response_too_large", canonical_product_url=fetched.final_url, source_url=fetched.final_url)
    if fetched.error_code == "unsupported_content":
        return _empty("unsupported", fetched.message, "unsupported_content", canonical_product_url=fetched.final_url, source_url=fetched.final_url)
    if fetched.status_code in {401, 403}:
        return _empty(
            "login_required",
            "This page restricts access. COSMIX does not log in or bypass a wall.",
            "access_restricted",
            canonical_product_url=fetched.final_url,
            source_url=fetched.final_url,
        )
    if fetched.status_code == 429:
        return _empty("unavailable", "The site asked us to slow down. Paste the ingredient list.", "rate_limited")
    if fetched.status_code >= 400:
        return _empty(
            "inaccessible",
            f"The page returned an error ({fetched.status_code}).",
            "http_error",
            canonical_product_url=fetched.final_url,
            source_url=fetched.final_url,
        )
    return None


async def extract_product(url: str, *, fetch=None) -> dict:
    fetcher = fetch or fetch_public
    fetched = await fetcher(url)
    if not isinstance(fetched, FetchResult):
        raise TypeError("Fetcher returned an unexpected result.")
    failed = _status_from_http(fetched)
    if failed:
        return failed

    html = fetched.body[:1_500_000].decode("utf-8", errors="replace")
    parsed = ingredients_from_html(html)
    host = page_host(fetched.final_url or url)
    method = platform_method(host, parsed.get("methods") or [])
    image = safe_image_url(parsed.get("image") or "", fetched.final_url or url)
    name = parsed.get("product_name") or ""
    brand = parsed.get("brand") or ""
    score = int(parsed.get("ingredient_score") or 0)
    text = parsed.get("ingredients") or ""
    tokens = parse_ingredient_text(text)["tokens"] if text else []

    if looks_like_script_shell(html, parsed) and score < _SUCCESS_SCORE:
        return _empty(
            "javascript_required",
            "This page needs a browser script before the ingredient list is in the HTML. COSMIX does not run page scripts.",
            "javascript_required",
            product_name=name,
            brand=brand,
            product_image=image,
            canonical_product_url=fetched.final_url,
            source_url=fetched.final_url,
            extraction_method=method,
        )

    wall = shop_wall_message(html, fetched.final_url or url)
    if wall and score < _SUCCESS_SCORE:
        return _empty(
            "inaccessible",
            wall,
            "shopping_wall",
            product_name=name,
            brand=brand,
            canonical_product_url=fetched.final_url,
            source_url=fetched.final_url,
            extraction_method=method,
        )

    if score < _SUCCESS_SCORE:
        warnings = []
        if tokens:
            warnings.append("A short fragment mentioned ingredients, but it was not enough to treat the extraction as successful.")
        return _empty(
            "ingredients_not_found",
            "The page opened, but COSMIX could not find a reliable ingredient list. Many shops hide it behind a button.",
            "ingredients_not_found",
            product_name=name,
            brand=brand,
            product_image=image,
            canonical_product_url=fetched.final_url,
            ingredients=tokens,
            ingredient_text=text,
            source_url=fetched.final_url,
            extraction_method=method,
            warnings=warnings,
        )

    source = name or (urlparse(fetched.final_url).hostname or "this page")
    return {
        "extraction_status": "success",
        "product_name": name,
        "brand": brand,
        "product_image": image,
        "canonical_product_url": fetched.final_url,
        "ingredients": tokens,
        "ingredient_text": text,
        "source_url": fetched.final_url,
        "extraction_method": method,
        "warnings": [
            "Check the words below against the pack. Automatic reading can miss a folded section or a different shade."
        ],
        "error_code": None,
        "message": (
            f"Read {source}. Check the words below before you run the analysis. "
            "If the tube in your hand says something else, the tube wins."
        ),
    }


async def extract_from_url(url: str) -> dict:
    """Legacy shape used by the original profile check screen."""
    result = await extract_product(url)
    if result["extraction_status"] != "success":
        return {
            "ok": False,
            "ingredients": result.get("ingredient_text") or "",
            "product_name": result.get("product_name") or "",
            "message": result.get("message") or "",
        }
    return {
        "ok": True,
        "ingredients": result.get("ingredient_text") or "",
        "product_name": result.get("product_name") or "",
        "source_url": result.get("source_url") or "",
        "message": result.get("message") or "",
    }
