"""Reject product URLs that are not public HTTP(S) pages.

Every hop is checked. Local, private, link-local, and reserved addresses are refused
before a connection is opened.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google",
}
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".localdomain")


def assert_public_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Use a normal http or https product link.")
    if parsed.username or parsed.password:
        raise ValueError("Remove any username or password from the link.")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("That link has no website address.")
    if host in _BLOCKED_HOSTS or host.endswith(_BLOCKED_SUFFIXES):
        raise ValueError("That address is not a public product page.")
    if _host_is_blocked_ip(host):
        raise ValueError("That address is not a public product page.")
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("Could not find that website.") from exc
    if not addresses:
        raise ValueError("Could not find that website.")
    for info in addresses:
        ip = ipaddress.ip_address(info[4][0])
        if not _public_ip(ip):
            raise ValueError("That address is not a public product page.")
    return url.strip()


def resolve_redirect(current: str, location: str) -> str:
    if not location or not str(location).strip():
        raise ValueError("The page redirected nowhere.")
    return assert_public_url(urljoin(current, location.strip()))


def page_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host


def _host_is_blocked_ip(host: str) -> bool:
    literal = host
    if literal.startswith("[") and literal.endswith("]"):
        literal = literal[1:-1]
    try:
        ip = ipaddress.ip_address(literal)
    except ValueError:
        return False
    return not _public_ip(ip)


def _public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_global
        and not any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_reserved,
                ip.is_multicast,
                ip.is_unspecified,
            )
        )
    )
