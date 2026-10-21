"""Legacy imports. The extraction package owns the implementation."""

from app.extraction.html_extractor import ingredients_from_html, shop_wall_message
from app.extraction.service import extract_from_url
from app.extraction.validator import assert_public_url

__all__ = [
    "assert_public_url",
    "extract_from_url",
    "ingredients_from_html",
    "shop_wall_message",
]
