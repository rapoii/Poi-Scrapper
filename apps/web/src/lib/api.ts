/**
 * Typed minimal fetch client ke FastAPI.
 *
 * Phase 1: jobs CRUD + source discovery. Selanjutnya akan tambah records,
 * exports, dan scraper run orchestration.
 */

import type {
  FieldDataType,
  FilterOp,
  Intent,
  IntentFilter,
  Job,
  JobStatus,
  Record_ as SharedRecord,
  RequiredField,
  ScrapeStrategy,
  ScrapingPlan,
  Source,
  SourceStatus,
  TargetScope,
} from "@poi/shared";

export type {
  FieldDataType,
  FilterOp,
  Intent,
  IntentFilter,
  Job,
  JobStatus,
  RequiredField,
  ScrapeStrategy,
  ScrapingPlan,
  Source,
  SourceStatus,
  TargetScope,
};

export type ScrapedRecord = SharedRecord;

export interface HealthInfo {
  ok: boolean;
  latency_ms?: number;
  error?: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  app_env: string;
  now: string;
  db: HealthInfo;
  redis: HealthInfo;
}

export interface VersionResponse {
  version: string;
  app_env: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly traceId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Selalu pakai relative URL via Next.js rewrite (apps/web/next.config.ts).
// Browser fetch jadi same-origin → tidak ada CORS issue lintas dev/staging/prod
// karena Next server jadi proxy ke backend FastAPI (`/api/*` → backend `/*`).
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `/api${path}`;
  const resp = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const traceId = resp.headers.get("x-trace-id") ?? undefined;
  if (!resp.ok) {
    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = { message: resp.statusText };
    }
    const message =
      (body as { message?: string; detail?: string })?.message ??
      (body as { message?: string; detail?: string })?.detail ??
      resp.statusText;
    throw new ApiError(message, resp.status, traceId, body);
  }
  return (await resp.json()) as T;
}

async function requestBlob(
  path: string,
  init?: RequestInit,
): Promise<{ blob: Blob; filename: string }> {
  const url = `/api${path}`;
  const resp = await fetch(url, {
    ...init,
    headers: {
      Accept: "text/csv",
      ...(init?.headers ?? {}),
    },
  });
  const traceId = resp.headers.get("x-trace-id") ?? undefined;
  if (!resp.ok) {
    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = { message: resp.statusText };
    }
    const message =
      (body as { message?: string; detail?: string })?.message ??
      (body as { message?: string; detail?: string })?.detail ??
      resp.statusText;
    throw new ApiError(message, resp.status, traceId, body);
  }
  return {
    blob: await resp.blob(),
    filename: filenameFromContentDisposition(resp.headers.get("content-disposition")),
  };
}

function filenameFromContentDisposition(value: string | null): string {
  if (!value) return "poiscrapper-export.csv";
  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1].replace(/"/g, ""));
  const asciiMatch = /filename="?([^";]+)"?/i.exec(value);
  return asciiMatch?.[1] ?? "poiscrapper-export.csv";
}

// ---- Jobs ------------------------------------------------------------------
export interface JobListItem {
  id: string;
  prompt: string;
  status: JobStatus;
  total_records: number;
  avg_completeness: number | null;
  created_at: string;
  finished_at: string | null;
}

export interface JobListResponse {
  items: JobListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface RecordListResponse {
  items: ScrapedRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobCreatePayload {
  prompt: string;
}

export interface JobIntentUpdatePayload {
  intent: Intent;
}

export interface JobReparsePayload {
  prompt: string;
}

export interface JobDiscoverSourcesParams {
  async?: boolean;
}

export interface JobSourceSelection {
  id: string;
  enabled: boolean;
  override_robots?: boolean | null;
}

export interface JobSourcesUpdatePayload {
  sources: JobSourceSelection[];
}

export interface JobRunParams {
  async?: boolean;
}

export const api = {
  getHealth: () => request<HealthResponse>("/health"),
  getVersion: () => request<VersionResponse>("/version"),
  jobs: {
    create: (payload: JobCreatePayload) =>
      request<Job>("/jobs", { method: "POST", body: JSON.stringify(payload) }),
    list: (params: { limit?: number; offset?: number; status?: JobStatus } = {}) => {
      const search = new URLSearchParams();
      if (params.limit) search.set("limit", String(params.limit));
      if (params.offset) search.set("offset", String(params.offset));
      if (params.status) search.set("status", params.status);
      const qs = search.toString();
      return request<JobListResponse>(`/jobs${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<Job>(`/jobs/${id}`),
    reparse: (id: string, payload: JobReparsePayload) =>
      request<Job>(`/jobs/${id}/reparse`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateIntent: (id: string, payload: JobIntentUpdatePayload) =>
      request<Job>(`/jobs/${id}/intent`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    updateSources: (id: string, payload: JobSourcesUpdatePayload) =>
      request<Job>(`/jobs/${id}/sources`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    discoverSources: (id: string, params: JobDiscoverSourcesParams = { async: true }) => {
      const search = new URLSearchParams();
      search.set("async", String(params.async ?? true));
      return request<Job>(`/jobs/${id}/discover?${search.toString()}`, { method: "POST" });
    },
    run: (id: string, params: JobRunParams = { async: true }) => {
      const search = new URLSearchParams();
      search.set("async", String(params.async ?? true));
      return request<Job>(`/jobs/${id}/run?${search.toString()}`, { method: "POST" });
    },
    records: (id: string, params: { limit?: number; offset?: number } = {}) => {
      const search = new URLSearchParams();
      if (params.limit) search.set("limit", String(params.limit));
      if (params.offset) search.set("offset", String(params.offset));
      const qs = search.toString();
      return request<RecordListResponse>(`/jobs/${id}/records${qs ? `?${qs}` : ""}`);
    },
    exportCsv: (id: string) => requestBlob(`/jobs/${id}/export?format=csv`),
  },
};
