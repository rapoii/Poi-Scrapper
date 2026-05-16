# @poi/shared

Single source of truth untuk kontrak data antara frontend (TypeScript) dan backend (Python).

## Struktur

- `schema/*.json` — JSON Schema master (draft 2020-12). Diversikan di git.
- `scripts/codegen.mjs` — generator: baca `schema/*.json` → hasilkan types TS di `generated/ts/` dan Python Pydantic di `generated/py/`.
- `src/index.ts` — barrel re-export untuk dipakai di Next.js via `@poi/shared`.

## Schema saat ini (Phase 0/1)

| File | Deskripsi |
|---|---|
| `intent.json` | Hasil parsing prompt user → `entity_type`, `required_fields`, `filters`, `seed_urls`. |
| `plan.json` | Scraping plan yang di-review user (intent + sources + estimated stats). |
| `source.json` | Target URL beserta strategy & status. |
| `record.json` | Data hasil scraping dengan metadata (`source_url`, `completeness_score`, dll). |
| `job.json` | Agregat job status untuk dikirim ke FE. |

## Menjalankan codegen

```bash
pnpm --filter @poi/shared codegen
```

Output:

- `generated/ts/*.d.ts` → auto-consumed oleh `apps/web` via `@poi/shared`.
- `generated/py/*.py` → symlink-copy ke `apps/api/app/schemas/generated/` saat build.

> Phase 0 hanya meletakkan schema + scaffolding codegen. Generator TS sudah jalan; generator Python menyusul di Phase 1 supaya Pydantic v2 model in-sync otomatis.
