"""Scraper dispatcher."""

from __future__ import annotations

from app.db.models import ScrapeStrategy
from app.services.scraper.base import ScraperStrategyProtocol
from app.services.scraper.headless import HeadlessHtmlScraper
from app.services.scraper.static_html import StaticHtmlScraper


class ScraperDispatcher:
    """Choose a scraper strategy for a source."""

    def __init__(self) -> None:
        self._static_html = StaticHtmlScraper()
        self._headless = HeadlessHtmlScraper(extractor=self._static_html)

    def for_strategy(self, strategy: ScrapeStrategy) -> ScraperStrategyProtocol:
        if strategy == ScrapeStrategy.HEADLESS:
            return self._headless
        return self._static_html

    def headless(self) -> ScraperStrategyProtocol:
        """Return explicit headless fallback strategy."""
        return self._headless


def get_scraper_dispatcher() -> ScraperDispatcher:
    return ScraperDispatcher()
