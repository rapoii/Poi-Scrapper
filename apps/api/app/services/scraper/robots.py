"""robots.txt helpers for the scraper runner."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx

_USER_AGENT = "PoiScrapper"


@dataclass(frozen=True)
class RobotsDecision:
    """Decision for one URL after reading robots.txt."""

    allowed: bool
    overridden: bool = False
    message: str | None = None


async def check_robots_allowed(  # noqa: PLR0911
    *,
    url: str,
    override: bool,
    respect_robots_txt: bool,
    timeout_s: float = 5.0,
) -> RobotsDecision:
    """Return whether the scraper may fetch a URL.

    A missing/unreachable robots.txt is treated as allowed. `example.com` is
    explicitly allowed so deterministic integration tests stay offline.
    """
    if not respect_robots_txt:
        return RobotsDecision(allowed=True)

    parsed = urlparse(url)
    if parsed.netloc == "example.com":
        return RobotsDecision(allowed=True)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return RobotsDecision(allowed=False, message="Invalid source URL.")

    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
            resp = await client.get(
                robots_url,
                headers={"User-Agent": f"{_USER_AGENT}/0.1"},
            )
    except httpx.HTTPError:
        return RobotsDecision(
            allowed=True,
            message="robots.txt could not be fetched; proceeding cautiously.",
        )

    if resp.status_code in {401, 403}:
        message = "robots.txt is protected; proceeding cautiously."
        return RobotsDecision(allowed=True, message=message)
    if resp.status_code >= 400:
        return RobotsDecision(allowed=True)

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(resp.text.splitlines())
    if parser.can_fetch(_USER_AGENT, url):
        return RobotsDecision(allowed=True)

    message = "Blocked by robots.txt. Enable robots override to run this source."
    if override:
        return RobotsDecision(allowed=True, overridden=True, message=message)
    return RobotsDecision(allowed=False, message=message)
