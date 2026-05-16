# apps/web — PoiScrapper v3 Frontend

Next.js 15 (App Router, React 19, Turbopack) + Tailwind CSS v4 + shadcn/ui.

## Setup

```bash
# dari root repo
pnpm install
```

## Menjalankan

```bash
pnpm --filter @poi/web dev
# atau: pnpm dev
```

UI buka di http://localhost:3000. Banner akan nge-polling `/health` di backend FastAPI (default `http://localhost:8000`). Kalau merah berarti backend belum jalan.

## Environment

`.env` di root atau `.env.local` di `apps/web/` boleh digunakan:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

## Stack

- Next.js 15 App Router + TypeScript strict
- Tailwind CSS v4 (CSS-first config di `src/app/globals.css`)
- shadcn/ui (new-york style) — tambah komponen via `pnpm dlx shadcn@latest add <name>`
- TanStack Query untuk data fetching
- Lucide React untuk ikon
- Sonner untuk toast
