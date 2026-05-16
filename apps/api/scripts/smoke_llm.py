"""Smoke test untuk LLM intent parser — bypass HTTP.

Run: `uv run python scripts/smoke_llm.py "prompt anda"`
"""

from __future__ import annotations

import asyncio
import sys

from app.services.intent_parser_llm import build_llm_parser


async def main(prompt: str) -> None:
    parser = build_llm_parser()
    print(f"[smoke] Provider chain: {parser.provider.name} / {parser.provider.model}")
    print(f"[smoke] Prompt: {prompt!r}\n")
    plan = await parser.parse(prompt)
    intent = plan.intent
    print(f"Entity:       {intent.entity_type}")
    print(f"Label:        {intent.entity_label}")
    print(f"Institution:  {intent.target_scope.institution}")
    print(f"Location:     {intent.target_scope.location}")
    print(f"Country:      {intent.target_scope.country}")
    print(f"Language:     {intent.language}")
    print(f"Output:       {intent.output_format}")
    print(f"Notes:        {intent.notes}")
    print(f"\nFields ({len(intent.required_fields)}):")
    for f in intent.required_fields:
        req = "*" if f.required else " "
        print(f"  {req} {f.name:<22} [{f.data_type}] {f.label or ''}")
    if intent.filters:
        print(f"\nFilters ({len(intent.filters)}):")
        for fl in intent.filters:
            print(f"  - op={fl.op} field={fl.field} value={fl.value!r} expr={fl.expression!r}")
    if plan.warnings:
        print("\nWarnings:")
        for w in plan.warnings:
            print(f"  ! {w}")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]).strip() or "data dokter spesialis jantung di RS Siloam Karawaci"
    asyncio.run(main(prompt))
