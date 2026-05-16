"""Unit test untuk Gemini schema sanitizer.

Pastikan output dari `_pydantic_to_gemini_schema`:
  - tidak punya `$ref` / `$defs`
  - tidak punya `additionalProperties` / `title`
  - tetap punya `type`, `properties`, `required`, `items`, `enum`
"""

from __future__ import annotations

from typing import Any

from app.schemas.intent import Intent, IntentField, IntentFilter, Plan
from app.services.llm.gemini_provider import _pydantic_to_gemini_schema


def _walk(node: Any, predicate, path: str = "$") -> list[str]:
    """Yield path-string untuk setiap node yang match `predicate`."""
    found: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if predicate(k, v):
                found.append(f"{path}.{k}")
            found.extend(_walk(v, predicate, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_walk(item, predicate, f"{path}[{i}]"))
    return found


def test_intent_schema_has_no_refs() -> None:
    schema = _pydantic_to_gemini_schema(Intent)
    refs = _walk(schema, lambda k, _v: k == "$ref")
    assert refs == [], f"Expected no $ref in sanitized schema, got: {refs}"
    assert "$defs" not in schema


def test_intent_schema_has_no_additional_properties() -> None:
    schema = _pydantic_to_gemini_schema(Intent)
    flagged = _walk(schema, lambda k, _v: k == "additionalProperties")
    assert flagged == [], f"Expected no additionalProperties, got: {flagged}"


def test_intent_schema_has_no_titles() -> None:
    schema = _pydantic_to_gemini_schema(Intent)
    flagged = _walk(schema, lambda k, _v: k == "title")
    assert flagged == [], f"Expected no title fields, got: {flagged}"


def test_intent_schema_keeps_essential_keys() -> None:
    schema = _pydantic_to_gemini_schema(Intent)
    assert schema["type"] == "object"
    assert "entity_type" in schema["properties"]
    assert "required_fields" in schema["properties"]
    # Nested IntentField: setelah inline, "items" harus ada dengan "properties".
    items = schema["properties"]["required_fields"]["items"]
    assert items["type"] == "object"
    assert "name" in items["properties"]
    assert "data_type" in items["properties"]


def test_intent_field_data_type_enum_preserved() -> None:
    schema = _pydantic_to_gemini_schema(IntentField)
    enum = schema["properties"]["data_type"].get("enum")
    assert enum is not None
    assert "string" in enum
    assert "url" in enum


def test_intent_filter_value_is_string_or_null() -> None:
    schema = _pydantic_to_gemini_schema(IntentFilter)
    value_schema = schema["properties"]["value"]
    # Pydantic emits union type for `str | None`.
    assert "anyOf" in value_schema or value_schema.get("type") in {"string", "null"}


def test_plan_schema_works_too() -> None:
    """Plan punya nested Intent + nested PlanSourceDraft → harus inline rapi."""
    schema = _pydantic_to_gemini_schema(Plan)
    refs = _walk(schema, lambda k, _v: k == "$ref")
    assert refs == []
    assert schema["properties"]["intent"]["type"] == "object"
    assert schema["properties"]["intent"]["properties"]["entity_type"]["type"] == "string"
