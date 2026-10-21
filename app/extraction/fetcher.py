"""Fetch one public page with timeouts, a size cap, and checked redirects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.extraction.validator import assert_public_url, resolve_redirect

logger = logging.getLogger("cosmix.extract")

MAX_BYTES = 1_500_000
MAX_REDIRECTS = 5
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}
_REDIRECTS = {301, 302, 303, 307, 308}
_ALLOWED_TYPES = ("html", "text/", "json", "xml")


@dataclass
class FetchResult:
    final_url: str
    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    error_code: str | None = None
    message: str = ""


def content_type_error(content_type: str) -> str | None:
    kind = (content_type or "").lower()
    if not kind:
        return None
    if "pdf" in kind:
        return "That link is a PDF. Copy the ingredients out and paste them."
    if kind.startswith("image/"):
        return "That link is a picture. This version cannot read words inside a photo. Paste the ingredient list."
    if not any(token in kind for token in _ALLOWED_TYPES):
        return "COSMIX could not read that kind of file. Paste the ingredient list."
    return None


def enforce_size(content_length: str | None, body: bytes) -> None:
    if content_length:
        digits = content_length.strip().split(";", 1)[0]
        if digits.isdigit() and int(digits) > MAX_BYTES:
            raise ValueError("That page is too large to read automatically. Paste the ingredient list.")
    if len(body) > MAX_BYTES:
        raise ValueError("That page is too large to read automatically. Paste the ingredient list.")


async def _read_limited(response: httpx.Response) -> bytes:
    length = response.headers.get("content-length")
    enforce_size(length, b"")
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValueError("That page is too large to read automatically. Paste the ingredient list.")
        chunks.append(chunk)
    body = b"".join(chunks)
    enforce_size(None, body)
    return body


async def fetch_public(url: str) -> FetchResult:
    try:
        current = assert_public_url(url)
    except ValueError as exc:
        return FetchResult(final_url="", error_code="invalid_url", message=str(exc))

    timeout = httpx.Timeout(12.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers=HEADERS) as client:
            for _ in range(MAX_REDIRECTS + 1):
                async with client.stream("GET", current) as response:
                    status = response.status_code
                    headers = {key.lower(): value for key, value in response.headers.items()}
                    if status in _REDIRECTS:
                        location = headers.get("location", "")
                        try:
                            current = resolve_redirect(current, location)
                        except ValueError as exc:
                            logger.info("extract rejected redirect host")
                            return FetchResult(final_url="", error_code="invalid_url", message=str(exc))
                        continue
                    kind_error = content_type_error(headers.get("content-type", ""))
                    if kind_error:
                        return FetchResult(
                            final_url=current,
                            status_code=status,
                            headers=headers,
                            error_code="unsupported_content",
                            message=kind_error,
                        )
                    try:
                        body = await _read_limited(response)
                    except ValueError as exc:
                        return FetchResult(
                            final_url=current,
                            status_code=status,
                            headers=headers,
                            error_code="response_too_large",
                            message=str(exc),
                        )
                    logger.info("extract fetched status=%s bytes=%s", status, len(body))
                    return FetchResult(final_url=current, status_code=status, headers=headers, body=body)
    except httpx.HTTPError:
        logger.info("extract network failure")
        return FetchResult(
            final_url=current,
            error_code="unavailable",
            message="The website did not answer. Open the product and paste the ingredient list.",
        )
    return FetchResult(
        final_url=current,
        error_code="unavailable",
        message="The page redirected too many times.",
    )
