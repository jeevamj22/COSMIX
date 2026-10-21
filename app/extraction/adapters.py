"""Platform adapters add candidate ingredient blocks. They never replace the generic reader."""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

# These selectors are extra hints. Pages are still read from headings, JSON-LD, and visible text.
# A selector that goes stale must not be the only way a list can be found.


@dataclass(frozen=True)
class Platform:
    id: str
    suffixes: tuple[str, ...]
    selectors: tuple[str, ...]
    note: str


PLATFORMS: tuple[Platform, ...] = (
    Platform(
        "amazon",
        ("amazon.",),
        ("#important-information", "#productDescription", "#nic-po-expander"),
        "Amazon often returns a shopping wall instead of the product. Paste the list when that happens.",
    ),
    Platform(
        "flipkart",
        ("flipkart.",),
        ("div._1mXcCf", "div._3k-BhJ"),
        "Flipkart pages change often and may refuse an automatic read.",
    ),
    Platform(
        "nykaa",
        ("nykaa.",),
        ("#ingredients", ".ingredients", "[data-label='Ingredients']"),
        "Nykaa is attempted with the generic reader plus an ingredient block when the page exposes one.",
    ),
    Platform(
        "myntra",
        ("myntra.",),
        ("#ingredients", ".pdp-product-description"),
        "Myntra product details are attempted only when the HTML already contains them.",
    ),
    Platform(
        "purplle",
        ("purplle.",),
        ("#ingredients", ".product-ingredients"),
        "Purplle is attempted with the generic reader. A blocked page falls back to manual entry.",
    ),
)


def match_platform(host: str) -> Platform | None:
    lowered = (host or "").lower()
    for platform in PLATFORMS:
        if any(part in lowered for part in platform.suffixes):
            return platform
    return None


def extra_candidates(soup: BeautifulSoup) -> list[str]:
    found: list[str] = []
    selectors = [
        "[itemprop='ingredients']",
        "#ingredients",
        ".ingredients",
        "[data-ingredient]",
        "table",
    ]
    for platform in PLATFORMS:
        selectors.extend(platform.selectors)
    seen = set()
    for selector in selectors:
        if selector in seen:
            continue
        seen.add(selector)
        try:
            nodes = soup.select(selector)
        except Exception:
            continue
        for node in nodes[:8]:
            text = node.get_text(" ", strip=True)
            if text and 8 < len(text) < 4000 and "ingredient" in text.lower():
                found.append(text)
    return found


def platform_catalog() -> list[dict]:
    rows = [
        {
            "id": "generic",
            "domains": ["any public hostname"],
            "status": "best_effort",
            "note": "Public HTML is read from structured product data, ingredient headings, and nearby text. A site that needs login, a captcha, or a browser script is not bypassed.",
        }
    ]
    for platform in PLATFORMS:
        rows.append(
            {
                "id": platform.id,
                "domains": list(platform.suffixes),
                "status": "best_effort",
                "note": platform.note,
            }
        )
    return rows
