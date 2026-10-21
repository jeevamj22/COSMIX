"""Read ingredient text from HTML that was already fetched. No JavaScript is executed."""

from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.engine import parse_ingredient_text
from app.extraction.adapters import extra_candidates, match_platform

_MANUAL = (
    "We couldn't retrieve the ingredients from this product page. "
    "Please paste the ingredient list manually to continue."
)


def manual_fallback(detail: str = "") -> str:
    detail = (detail or "").strip()
    if not detail:
        return _MANUAL
    if _MANUAL in detail:
        return detail
    return f"{detail} {_MANUAL}"


def _score(text: str) -> int:
    parsed = parse_ingredient_text(text)
    return len(parsed["tokens"]) + len(parsed["may_contain"])


def _as_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    return ""


def _walk_json(node, names: list[str], brands: list[str], images: list[str], ingredients: list[str]) -> None:
    if isinstance(node, list):
        for child in node:
            _walk_json(child, names, brands, images, ingredients)
        return
    if not isinstance(node, dict):
        return
    kind = str(node.get("@type", "")).lower()
    name = node.get("name")
    if isinstance(name, str) and "product" in kind:
        names.append(name.strip())
    brand = node.get("brand")
    if isinstance(brand, str) and brand.strip():
        brands.append(brand.strip())
    elif isinstance(brand, dict):
        brand_name = brand.get("name")
        if isinstance(brand_name, str) and brand_name.strip():
            brands.append(brand_name.strip())
    image = node.get("image")
    image_text = _as_text(image if not isinstance(image, dict) else image.get("url") or image.get("contentUrl"))
    if image_text:
        images.append(image_text.split(",")[0].strip())
    for key in ("ingredients", "ingredient"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            ingredients.append(value.strip())
        elif isinstance(value, list):
            joined = _as_text(value)
            if joined:
                ingredients.append(joined)
    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_json(value, names, brands, images, ingredients)


def ingredients_from_html(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    names: list[str] = []
    brands: list[str] = []
    images: list[str] = []
    candidates: list[str] = []
    methods: list[str] = []

    for script in soup.find_all("script"):
        kind = (script.get("type") or "").lower()
        if "ld+json" not in kind or not script.string:
            continue
        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        found: list[str] = []
        _walk_json(payload, names, brands, images, found)
        if found:
            methods.append("json_ld")
        candidates.extend(found)

    for element in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b", "summary", "dt", "p", "span", "div"]):
        label = element.get_text(" ", strip=True)
        if not label or len(label) > 48:
            continue
        if not re.fullmatch(r"(full |key |active |inactive )?ingredients?( list)?\s*:?\s*", label, flags=re.I):
            continue
        chunks = []
        for sibling in element.next_siblings:
            name = getattr(sibling, "name", None)
            if name in {"h1", "h2", "h3", "h4"}:
                break
            text = sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
            if text:
                chunks.append(text)
            if len(" ".join(chunks)) > 3000:
                break
        if chunks:
            methods.append("ingredient_heading")
            candidates.append(" ".join(chunks))

    for extra in extra_candidates(soup):
        methods.append("platform_selector")
        candidates.append(extra)

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    flat = soup.get_text("\n", strip=True)
    match = re.search(r"ingredients?\s*[:\-–]\s*(.+)", flat, flags=re.I | re.S)
    if match:
        chunk = match.group(1)
        chunk = re.split(
            r"\n\s*\n|\b(directions|how to use|caution|warning|about the brand)\b",
            chunk,
            maxsplit=1,
            flags=re.I,
        )[0]
        methods.append("visible_text")
        candidates.append(chunk[:3000])

    best = ""
    best_score = 0
    for candidate in candidates:
        score = _score(candidate)
        if score > best_score:
            best = candidate.strip()
            best_score = score

    title = ""
    if names:
        title = names[0]
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()
    og_title = soup.find("meta", property="og:title")
    if not title and og_title and og_title.get("content"):
        title = og_title["content"].strip()
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        images.append(og_image["content"].strip())

    ordered_methods = []
    for method in methods:
        if method not in ordered_methods:
            ordered_methods.append(method)
    return {
        "ingredients": best if best_score >= 1 else "",
        "ingredient_score": best_score,
        "product_name": title[:180],
        "brand": (brands[0][:180] if brands else ""),
        "image": (images[0] if images else ""),
        "methods": ordered_methods,
        "text_length": len(flat),
        "flat_text": flat[:4000],
    }


def shop_wall_message(html: str, url: str) -> str:
    """A short interstitial is a wall. A real product page is not, even if it has a cart link."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    flat = soup.get_text(" ", strip=True)
    lowered = flat.lower()
    host = (urlparse(url).hostname or "This shop").removeprefix("www.")
    blocked = (
        "click the button below to continue shopping" in lowered
        or "sorry, we just need to make sure you're not a robot" in lowered
        or "enter the characters you see" in lowered
        or ("continue shopping" in lowered and len(flat) < 2500)
    )
    if not blocked:
        return ""
    return (
        f"{host} showed a shopping wall, not the ingredient list. "
        "Copy the Ingredients section from your browser and paste it below. "
        "If the tube in your hand says something else, the tube wins."
    )


def looks_like_script_shell(html: str, parsed: dict) -> bool:
    if parsed.get("ingredient_score", 0) >= 3:
        return False
    if parsed.get("text_length", 0) > 800:
        return False
    lowered = (html or "").lower()
    markers = (
        "enable javascript",
        "please turn on javascript",
        'id="__next"',
        'id="root"',
        "requires javascript",
    )
    return any(marker in lowered for marker in markers)


def safe_image_url(image: str, page_url: str) -> str:
    if not image:
        return ""
    absolute = urljoin(page_url or "", image.strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return ""
    host = parsed.hostname or ""
    if not host:
        return ""
    try:
        ip = __import__("ipaddress").ip_address(host)
    except ValueError:
        return absolute[:1000]
    if not ip.is_global:
        return ""
    return absolute[:1000]


def platform_method(host: str, methods: list[str]) -> str:
    platform = match_platform(host)
    base = "+".join(methods) if methods else "generic_html"
    if platform:
        return f"{platform.id}:{base}"
    return f"generic:{base}"
