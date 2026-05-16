"""Headless browser scraper fallback."""

from __future__ import annotations

import importlib

from app.schemas.intent import Intent
from app.services.scraper.base import ScrapedRecordDraft
from app.services.scraper.static_html import StaticHtmlScraper

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)


class HeadlessHtmlScraper:
    """Render a page with Playwright, then reuse the HTML extractor."""

    def __init__(
        self,
        *,
        timeout_s: float = 30.0,
        extractor: StaticHtmlScraper | None = None,
    ) -> None:
        self._timeout_ms = int(timeout_s * 1000)
        self._extractor = extractor or StaticHtmlScraper(timeout_s=timeout_s)

    async def scrape(
        self,
        *,
        url: str,
        title: str | None,
        reliability_score: float | None,
        intent: Intent,
    ) -> list[ScrapedRecordDraft]:
        html_text = await self._render_html(url)
        return await self._extractor.scrape_html(
            html_text=html_text,
            url=url,
            title=title,
            reliability_score=reliability_score,
            intent=intent,
            allow_headless_signal=False,
        )

    async def _render_html(self, url: str) -> str:
        try:
            playwright_api = importlib.import_module("playwright.async_api")
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            msg = (
                "Playwright is not installed; install the scraping extra and browser binaries "
                "to use headless scraping."
            )
            raise RuntimeError(msg) from exc

        async_playwright = playwright_api.async_playwright
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=_USER_AGENT)
                await page.goto(url, wait_until="networkidle", timeout=self._timeout_ms)
                content: object = await page.content()
                return str(content)
            finally:
                await browser.close()
