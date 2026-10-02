"""Read a public product page and pull out an ingredient list.

This does not log in, solve captchas, or bypass a site that refuses.
If the shop will not show the list, the user pastes it. Pasting is more accurate.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.engine import parse_ingredient_text

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

_BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".localdomain")


def assert_public_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Use a normal http or https product link.")
    if parsed.username or parsed.password:
        raise ValueError("Remove any username or password from the link.")
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("That link has no website address.")
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
        raise ValueError("That address is not a public product page.")
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("Could not find that website.") from exc
    for info in addresses:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("That address is not a public product page.")
    return url.strip()


def _walk_json(node, names: list[str], ingredients: list[str]) -> None:
    if isinstance(node, list):
        for child in node:
            _walk_json(child, names, ingredients)
        return
    if not isinstance(node, dict):
        return
    kind = str(node.get("@type", "")).lower()
    name = node.get("name")
    if isinstance(name, str) and "product" in kind:
        names.append(name.strip())
    for key in ("ingredients", "ingredient"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            ingredients.append(value.strip())
    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_json(value, names, ingredients)


def _score(text: str) -> int:
    parsed = parse_ingredient_text(text)
    return len(parsed["tokens"]) + len(parsed["may_contain"])


def ingredients_from_html(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    names: list[str] = []
    candidates: list[str] = []

    for script in soup.find_all("script"):
        kind = (script.get("type") or "").lower()
        if "ld+json" not in kind or not script.string:
            continue
        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        found: list[str] = []
        _walk_json(payload, names, found)
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
            candidates.append(" ".join(chunks))

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    flat = soup.get_text("\n", strip=True)
    match = re.search(r"ingredients?\s*[:\-–]\s*(.+)", flat, flags=re.I | re.S)
    if match:
        chunk = match.group(1)
        chunk = re.split(r"\n\s*\n|\b(directions|how to use|caution|warning|about the brand)\b", chunk, maxsplit=1, flags=re.I)[0]
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
    return {"ingredients": best if best_score >= 3 else "", "product_name": title[:180]}


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


def _fail(message: str, product_name: str = "") -> dict:
    return {"ok": False, "ingredients": "", "product_name": product_name, "message": message}


async def extract_from_url(url: str) -> dict:
    try:
        current = assert_public_url(url)
    except ValueError as exc:
        return _fail(str(exc))

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), follow_redirects=False, headers=HEADERS) as client:
            response = None
            for _ in range(6):
                response = await client.get(current)
                if response.status_code not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("location")
                if not location:
                    return _fail("The page redirected nowhere.")
                current = assert_public_url(urljoin(current, location))
            else:
                return _fail("The page redirected too many times.")
    except ValueError as exc:
        return _fail(str(exc))
    except httpx.HTTPError:
        return _fail("The website did not answer. Open the product and paste the ingredient list.")

    if response is None:
        return _fail("The website did not answer. Paste the ingredient list.")
    if response.status_code in {401, 403, 429}:
        return _fail("This shop blocked automatic reading. Paste the ingredient list from the page. That is more accurate anyway.")
    if response.status_code >= 400:
        return _fail(f"The page returned an error ({response.status_code}). Paste the ingredient list.")

    kind = (response.headers.get("content-type") or "").lower()
    if "pdf" in kind:
        return _fail("That link is a PDF. Copy the ingredients out and paste them.")
    if kind.startswith("image/"):
        return _fail("That link is a picture. This version cannot read words inside a photo. Paste the ingredient list.")
    if kind and "html" not in kind and "text/" not in kind and "json" not in kind and "xml" not in kind:
        return _fail("COSMIX could not read that kind of file. Paste the ingredient list.")

    html = response.content[:2_000_000].decode(response.encoding or "utf-8", errors="replace")
    parsed = ingredients_from_html(html)
    if not parsed["ingredients"]:
        wall = shop_wall_message(html, str(response.url))
        if wall:
            return _fail(wall, parsed.get("product_name") or "")
        return _fail(
            "The page opened, but COSMIX could not find an ingredient list. Many shops hide it behind a button. Copy the list and paste it below.",
            parsed.get("product_name") or "",
        )
    source = parsed.get("product_name") or (urlparse(str(response.url)).hostname or "this page")
    return {
        "ok": True,
        "ingredients": parsed["ingredients"],
        "product_name": parsed.get("product_name") or "",
        "source_url": str(response.url),
        "message": (
            f"Read {source}. Check the words below before you run the check. "
            "If the tube in your hand says something else, the tube wins."
        ),
    }
