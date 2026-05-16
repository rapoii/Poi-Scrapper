"""Unit test stub intent parser (rule-based)."""

from __future__ import annotations

import pytest

from app.services.intent_parser import StubIntentParser


@pytest.fixture
def parser() -> StubIntentParser:
    return StubIntentParser()


@pytest.mark.asyncio
async def test_parses_doctor_with_institution(parser: StubIntentParser) -> None:
    plan = await parser.parse("data dokter spesialis jantung di RS Siloam Karawaci")

    intent = plan.intent
    assert intent.entity_type == "doctor"
    assert intent.target_scope.institution is not None
    assert "Siloam" in intent.target_scope.institution
    assert intent.language == "id"
    field_names = {f.name for f in intent.required_fields}
    assert {"nama", "spesialisasi", "poli"}.issubset(field_names)


@pytest.mark.asyncio
async def test_parses_restaurant_with_location(parser: StubIntentParser) -> None:
    plan = await parser.parse("saya mau scrapping restoran di Bandung")

    intent = plan.intent
    assert intent.entity_type == "restaurant"
    assert intent.target_scope.location == "Bandung"
    assert intent.language == "id"
    assert any(f.name == "rating" for f in intent.required_fields)


@pytest.mark.asyncio
async def test_parses_school_english_prompt(parser: StubIntentParser) -> None:
    plan = await parser.parse("List of schools in Jakarta with accreditation A")

    intent = plan.intent
    assert intent.entity_type == "school"
    assert intent.target_scope.location == "Jakarta"
    # English prompt → bukan id
    assert intent.language == "en"


@pytest.mark.asyncio
async def test_extracts_exclusion_filter(parser: StubIntentParser) -> None:
    plan = await parser.parse("data dokter di RS X kecuali dokter umum")

    intent = plan.intent
    assert intent.entity_type == "doctor"
    assert len(intent.filters) >= 1
    assert any("umum" in f.expression for f in intent.filters)
    # At least one filter dengan op not_contains
    assert any(f.op == "not_contains" for f in intent.filters)


@pytest.mark.asyncio
async def test_unknown_entity_falls_back_to_generic(parser: StubIntentParser) -> None:
    plan = await parser.parse("collect random stuff")

    assert plan.intent.entity_type == "generic"
    assert plan.warnings, "Generic fallback harus tampilkan warning"


@pytest.mark.asyncio
async def test_empty_prompt_raises(parser: StubIntentParser) -> None:
    with pytest.raises(ValueError, match="prompt is empty"):
        await parser.parse("   ")
