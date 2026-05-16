"""Tests for static HTML extraction upgrades."""

from __future__ import annotations

from typing import TypeVar

import pytest
from pydantic import BaseModel

from app.schemas.intent import Intent, IntentField
from app.services.scraper.static_html import StaticHtmlScraper

T = TypeVar("T", bound=BaseModel)


class _ScriptedExtractionProvider:
    name = "test"
    model = "test-extractor"

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        return response_schema.model_validate(
            {
                "records": [
                    {
                        "fields": [
                            {"name": "nama", "value": "Dr. A", "confidence": 0.92},
                            {"name": "spesialisasi", "value": "Jantung", "confidence": 0.9},
                            {
                                "name": "profile_url",
                                "value": "https://example.test/a",
                                "confidence": 0.8,
                            },
                        ]
                    },
                    {
                        "fields": [
                            {"name": "nama", "value": "Dr. B", "confidence": 0.88},
                            {"name": "spesialisasi", "value": "Jantung", "confidence": 0.86},
                            {
                                "name": "profile_url",
                                "value": "https://example.test/b",
                                "confidence": 0.8,
                            },
                        ]
                    },
                ]
            }
        )


@pytest.mark.asyncio
async def test_static_html_scraper_uses_llm_multi_record_extraction() -> None:
    intent = Intent(
        entity_type="doctor",
        entity_label="Dokter",
        required_fields=[
            IntentField(name="nama", label="Nama", data_type="string"),
            IntentField(name="spesialisasi", label="Spesialisasi", data_type="string"),
            IntentField(name="profile_url", label="Profile URL", data_type="url"),
        ],
        language="id",
    )
    scraper = StaticHtmlScraper(llm_provider=_ScriptedExtractionProvider())

    records = await scraper.scrape_html(
        html_text="<html><body><h2>Dr. A</h2><h2>Dr. B</h2></body></html>",
        url="https://example.test/doctors",
        title="Doctor Directory",
        reliability_score=0.8,
        intent=intent,
    )

    assert len(records) == 2
    assert records[0].data["nama"] == "Dr. A"
    assert records[1].data["profile_url"] == "https://example.test/b"
    assert records[0].completeness_score == 1.0
    assert records[0].confidence_score > 0.85
