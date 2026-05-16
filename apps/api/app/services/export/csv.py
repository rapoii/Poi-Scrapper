"""CSV export builder for scraped records."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.db.models import Job, Record
from app.schemas.intent import Plan

_METADATA_COLUMNS = ["source_url", "completeness_score", "confidence_score", "scraped_at"]


@dataclass(frozen=True)
class CsvExportPayload:
    """Rendered CSV payload plus metadata for persistence."""

    content: bytes
    columns: list[str]
    row_count: int


def build_records_csv(*, job: Job, records: list[Record]) -> CsvExportPayload:
    """Build CSV bytes from records for one job."""
    columns = _columns_for_job_records(job=job, records=records)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(_record_to_row(record=record, columns=columns))

    return CsvExportPayload(
        content=buffer.getvalue().encode("utf-8-sig"),
        columns=columns,
        row_count=len(records),
    )


def _columns_for_job_records(*, job: Job, records: list[Record]) -> list[str]:
    columns: list[str] = []
    if job.parsed_plan:
        plan = Plan.model_validate(job.parsed_plan)
        columns.extend(field.name for field in plan.intent.required_fields)

    seen = set(columns)
    for record in records:
        for key in record.data:
            if key in seen:
                continue
            columns.append(key)
            seen.add(key)

    for column in _METADATA_COLUMNS:
        if column not in seen:
            columns.append(column)
            seen.add(column)
    return columns


def _record_to_row(*, record: Record, columns: list[str]) -> dict[str, str]:
    row: dict[str, str] = {}
    for column in columns:
        if column in record.data:
            value: Any = record.data[column]
        else:
            value = getattr(record, column, None)
        row[column] = _stringify_csv_value(value)
    return row


def _stringify_csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)
