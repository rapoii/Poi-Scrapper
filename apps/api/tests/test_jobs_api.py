"""Integration test endpoint /jobs (Phase 1.1)."""

from __future__ import annotations

import csv
import io
from uuid import UUID

import pytest
from httpx import AsyncClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Export, Record, Source, SourceStatus
from app.services.scraper.robots import RobotsDecision


@pytest.mark.asyncio
async def test_create_job_returns_planning_with_parsed_plan(client: AsyncClient) -> None:
    resp = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["status"] == "planning"
    assert body["prompt"].startswith("data dokter")
    plan = body["parsed_plan"]
    assert plan is not None
    intent = plan["intent"]
    assert intent["entity_type"] == "doctor"
    assert intent["target_scope"]["institution"] is not None
    assert any(f["name"] == "spesialisasi" for f in intent["required_fields"])


@pytest.mark.asyncio
async def test_list_jobs_paginates_and_returns_total(client: AsyncClient) -> None:
    for i in range(3):
        r = await client.post(
            "/jobs",
            json={"prompt": f"data hotel di Bali nomor {i}"},
        )
        assert r.status_code == 201

    resp = await client.get("/jobs", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["total"] >= 3
    assert len(body["items"]) == 2
    assert body["items"][0]["created_at"] >= body["items"][1]["created_at"]


@pytest.mark.asyncio
async def test_get_job_by_id_returns_full_plan(client: AsyncClient) -> None:
    create = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    job_id = create.json()["id"]

    detail = await client.get(f"/jobs/{job_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == job_id
    assert body["parsed_plan"]["intent"]["entity_type"] == "school"


@pytest.mark.asyncio
async def test_get_job_unknown_id_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_job_rejects_short_prompt(client: AsyncClient) -> None:
    resp = await client.post("/jobs", json={"prompt": "hi"})
    assert resp.status_code == 422  # Pydantic min_length validation


@pytest.mark.asyncio
async def test_list_jobs_filters_by_status(client: AsyncClient) -> None:
    await client.post("/jobs", json={"prompt": "data restoran di Bandung"})

    resp = await client.get("/jobs", params={"status": "planning"})
    assert resp.status_code == 200
    body = resp.json()
    assert all(item["status"] == "planning" for item in body["items"])


@pytest.mark.asyncio
async def test_patch_intent_replaces_fields(client: AsyncClient) -> None:
    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]
    original_intent = create.json()["parsed_plan"]["intent"]

    # User edit: keep entity, change required fields to just 2.
    new_intent = {
        **original_intent,
        "required_fields": [
            {"name": "nama", "label": "Nama", "data_type": "string", "required": True},
            {"name": "email", "label": "Email", "data_type": "email", "required": False},
        ],
        "filters": [],
        "notes": "User trimmed to essentials",
    }

    patch = await client.patch(f"/jobs/{job_id}/intent", json={"intent": new_intent})
    assert patch.status_code == 200, patch.text
    updated = patch.json()
    fields = updated["parsed_plan"]["intent"]["required_fields"]
    assert len(fields) == 2
    assert {f["name"] for f in fields} == {"nama", "email"}
    assert updated["parsed_plan"]["intent"]["notes"] == "User trimmed to essentials"


@pytest.mark.asyncio
async def test_patch_intent_rejects_invalid_payload(client: AsyncClient) -> None:
    create = await client.post("/jobs", json={"prompt": "data hotel di Bali"})
    job_id = create.json()["id"]

    # Empty required_fields (Pydantic min_length=1) → 422.
    bad = {
        "intent": {
            "entity_type": "hotel",
            "required_fields": [],
        }
    }
    resp = await client.patch(f"/jobs/{job_id}/intent", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_intent_404_for_unknown_job(client: AsyncClient) -> None:
    payload = {
        "intent": {
            "entity_type": "doctor",
            "required_fields": [
                {"name": "nama", "data_type": "string"},
            ],
        }
    }
    resp = await client.patch(
        "/jobs/00000000-0000-0000-0000-000000000000/intent",
        json=payload,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reparse_prompt_replaces_plan_and_clears_sources(client: AsyncClient) -> None:
    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert len(discover.json()["parsed_plan"]["sources"]) == 1

    reparse = await client.post(
        f"/jobs/{job_id}/reparse",
        json={"prompt": "data hotel bintang 5 di Bali"},
    )
    assert reparse.status_code == 200, reparse.text
    body = reparse.json()
    assert body["prompt"] == "data hotel bintang 5 di Bali"
    assert body["status"] == "planning"
    assert body["parsed_plan"]["intent"]["entity_type"] == "hotel"
    assert body["parsed_plan"]["sources"] == []


@pytest.mark.asyncio
async def test_reparse_prompt_rejects_running_job(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.jobs.run_scrape_task.delay", lambda _job_id, _run_id: None)

    create = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    job_id = create.json()["id"]
    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert len(discover.json()["parsed_plan"]["sources"]) == 1
    run = await client.post(f"/jobs/{job_id}/run")
    assert run.status_code == 200

    reparse = await client.post(
        f"/jobs/{job_id}/reparse",
        json={"prompt": "data hotel di Bali"},
    )
    assert reparse.status_code == 409


@pytest.mark.asyncio
async def test_discover_sources_updates_plan_and_persists_sources(client: AsyncClient) -> None:
    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert discover.status_code == 200, discover.text
    body = discover.json()
    plan = body["parsed_plan"]
    assert plan["estimated_record_count"] == 10
    assert len(plan["sources"]) == 1

    source = plan["sources"][0]
    assert source["url"] == "https://example.com/doctor"
    assert source["strategy"] == "static_html"
    assert source["status"] == "pending"
    assert source["reliability_score"] == 0.6
    assert source["id"]
    assert source["job_id"] == job_id


@pytest.mark.asyncio
async def test_discover_sources_is_idempotent(client: AsyncClient) -> None:
    create = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    assert create.status_code == 201
    job_id = create.json()["id"]

    first = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    second = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert first.status_code == 200
    assert second.status_code == 200

    first_urls = [s["url"] for s in first.json()["parsed_plan"]["sources"]]
    second_urls = [s["url"] for s in second.json()["parsed_plan"]["sources"]]
    assert first_urls == second_urls
    assert len(second_urls) == len(set(second_urls))


@pytest.mark.asyncio
async def test_discover_sources_404_for_unknown_job(client: AsyncClient) -> None:
    resp = await client.post("/jobs/00000000-0000-0000-0000-000000000000/discover")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_discover_sources_default_queues_celery_task(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    queued: list[str] = []

    def fake_delay(job_id: str) -> None:
        queued.append(job_id)

    monkeypatch.setattr("app.api.jobs.discover_sources_task.delay", fake_delay)

    create = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    assert create.status_code == 201
    job_id = create.json()["id"]

    resp = await client.post(f"/jobs/{job_id}/discover")
    assert resp.status_code == 200, resp.text
    assert queued == [job_id]
    assert resp.json()["parsed_plan"]["sources"] == []


@pytest.mark.asyncio
async def test_patch_sources_can_skip_and_reenable_source(client: AsyncClient) -> None:
    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    assert create.status_code == 201
    job_id = create.json()["id"]

    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    source = discover.json()["parsed_plan"]["sources"][0]

    skipped = await client.patch(
        f"/jobs/{job_id}/sources",
        json={"sources": [{"id": source["id"], "enabled": False, "override_robots": True}]},
    )
    assert skipped.status_code == 200, skipped.text
    skipped_source = skipped.json()["parsed_plan"]["sources"][0]
    assert skipped_source["status"] == "skipped"
    assert skipped_source["override_robots"] is True

    enabled = await client.patch(
        f"/jobs/{job_id}/sources",
        json={"sources": [{"id": source["id"], "enabled": True}]},
    )
    assert enabled.status_code == 200, enabled.text
    enabled_source = enabled.json()["parsed_plan"]["sources"][0]
    assert enabled_source["status"] == "pending"
    assert enabled_source["override_robots"] is True


@pytest.mark.asyncio
async def test_patch_sources_404_for_source_from_other_job(client: AsyncClient) -> None:
    first = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    second = await client.post("/jobs", json={"prompt": "data hotel di Bali"})
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    discover = await client.post(f"/jobs/{first_id}/discover", params={"async": "false"})
    source = discover.json()["parsed_plan"]["sources"][0]

    resp = await client.patch(
        f"/jobs/{second_id}/sources",
        json={"sources": [{"id": source["id"], "enabled": False}]},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_job_sets_running_and_requires_selected_source(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    queued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.api.jobs.run_scrape_task.delay",
        lambda job_id, run_id: queued.append((job_id, run_id)),
    )

    create = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    job_id = create.json()["id"]
    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    source = discover.json()["parsed_plan"]["sources"][0]

    skipped = await client.patch(
        f"/jobs/{job_id}/sources",
        json={"sources": [{"id": source["id"], "enabled": False}]},
    )
    assert skipped.status_code == 200

    no_sources = await client.post(f"/jobs/{job_id}/run")
    assert no_sources.status_code == 409

    enabled = await client.patch(
        f"/jobs/{job_id}/sources",
        json={"sources": [{"id": source["id"], "enabled": True}]},
    )
    assert enabled.status_code == 200

    run = await client.post(f"/jobs/{job_id}/run")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "running"
    assert body["started_at"] is not None
    assert queued and queued[0][0] == job_id

    second_run = await client.post(f"/jobs/{job_id}/run")
    assert second_run.status_code == 409


@pytest.mark.asyncio
async def test_run_job_sync_scrapes_records(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    job_id = create.json()["id"]
    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert discover.status_code == 200

    run = await client.post(f"/jobs/{job_id}/run", params={"async": "false"})
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "done"
    assert body["total_records"] == 1
    assert body["avg_completeness"] is not None
    assert body["avg_confidence"] is not None

    records = (
        (await db_session.execute(select(Record).where(Record.job_id == UUID(job_id))))
        .scalars()
        .all()
    )
    assert len(records) == 1
    assert records[0].source_url == "https://example.com/doctor"
    assert records[0].data["profile_url"] == "https://example.com/doctor"
    assert body["parsed_plan"]["sources"][0]["status"] == "done"

    listed = await client.get(f"/jobs/{job_id}/records")
    assert listed.status_code == 200, listed.text
    listed_body = listed.json()
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["source_url"] == "https://example.com/doctor"
    assert listed_body["items"][0]["data"]["profile_url"] == "https://example.com/doctor"


@pytest.mark.asyncio
async def test_export_job_records_csv_persists_export_row(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    job_id = create.json()["id"]
    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert discover.status_code == 200
    run = await client.post(f"/jobs/{job_id}/run", params={"async": "false"})
    assert run.status_code == 200, run.text

    export = await client.get(f"/jobs/{job_id}/export", params={"format": "csv"})
    assert export.status_code == 200, export.text
    assert "text/csv" in export.headers["content-type"]
    assert "attachment" in export.headers["content-disposition"]
    assert f"poiscrapper-{job_id[:8]}" in export.headers["content-disposition"]

    reader = csv.DictReader(io.StringIO(export.content.decode("utf-8-sig")))
    rows = list(reader)
    assert reader.fieldnames is not None
    assert "nama" in reader.fieldnames
    assert "profile_url" in reader.fieldnames
    assert "source_url" in reader.fieldnames
    assert "completeness_score" in reader.fieldnames
    assert len(rows) == 1
    assert rows[0]["profile_url"] == "https://example.com/doctor"
    assert rows[0]["source_url"] == "https://example.com/doctor"

    exports = (
        (await db_session.execute(select(Export).where(Export.job_id == UUID(job_id))))
        .scalars()
        .all()
    )
    assert len(exports) == 1
    assert exports[0].row_count == 1
    assert exports[0].byte_size == len(export.content)
    assert exports[0].column_map is not None
    assert "source_url" in exports[0].column_map["columns"]


@pytest.mark.asyncio
async def test_export_job_records_rejects_empty_job(client: AsyncClient) -> None:
    create = await client.post("/jobs", json={"prompt": "data hotel di Bali"})
    job_id = create.json()["id"]

    export = await client.get(f"/jobs/{job_id}/export", params={"format": "csv"})
    assert export.status_code == 409


@pytest.mark.asyncio
async def test_export_job_records_404_for_unknown_job(client: AsyncClient) -> None:
    resp = await client.get(
        "/jobs/00000000-0000-0000-0000-000000000000/export",
        params={"format": "csv"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_job_sync_skips_robots_blocked_source(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_robots_check(**_: object) -> RobotsDecision:
        return RobotsDecision(
            allowed=False,
            message="Blocked by robots.txt. Enable robots override to run this source.",
        )

    monkeypatch.setattr("app.services.scraper.runner.check_robots_allowed", fake_robots_check)

    create = await client.post("/jobs", json={"prompt": "list of schools in Jakarta"})
    job_id = create.json()["id"]
    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    assert discover.status_code == 200

    run = await client.post(f"/jobs/{job_id}/run", params={"async": "false"})
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "failed"
    assert body["total_records"] == 0
    assert body["parsed_plan"]["sources"][0]["status"] == "skipped"
    assert "robots" in body["parsed_plan"]["sources"][0]["last_error"]

    source = (
        (await db_session.execute(select(Source).where(Source.job_id == UUID(job_id))))
        .scalars()
        .one()
    )
    assert source.status == SourceStatus.SKIPPED
    assert source.last_error is not None


@pytest.mark.asyncio
async def test_run_job_sync_allows_robots_override(
    client: AsyncClient,
    monkeypatch: MonkeyPatch,
) -> None:
    async def fake_robots_check(**kwargs: object) -> RobotsDecision:
        assert kwargs["override"] is True
        return RobotsDecision(
            allowed=True,
            overridden=True,
            message="Blocked by robots.txt. Enable robots override to run this source.",
        )

    monkeypatch.setattr("app.services.scraper.runner.check_robots_allowed", fake_robots_check)

    create = await client.post(
        "/jobs",
        json={"prompt": "data dokter spesialis jantung di RS Siloam Karawaci"},
    )
    job_id = create.json()["id"]
    discover = await client.post(f"/jobs/{job_id}/discover", params={"async": "false"})
    source = discover.json()["parsed_plan"]["sources"][0]
    update = await client.patch(
        f"/jobs/{job_id}/sources",
        json={"sources": [{"id": source["id"], "enabled": True, "override_robots": True}]},
    )
    assert update.status_code == 200

    run = await client.post(f"/jobs/{job_id}/run", params={"async": "false"})
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] == "done"
    assert body["total_records"] == 1
    assert any("robots.txt override" in warning for warning in body["parsed_plan"]["warnings"])


@pytest.mark.asyncio
async def test_list_records_404_for_unknown_job(client: AsyncClient) -> None:
    resp = await client.get("/jobs/00000000-0000-0000-0000-000000000000/records")
    assert resp.status_code == 404
