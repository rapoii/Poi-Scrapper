/**
 * `@poi/shared` — single source of truth untuk kontrak data.
 *
 * Tipe berikut di-generate dari `schema/*.json` via `pnpm --filter @poi/shared codegen`.
 * Di Phase 0 kita expose typed shim sederhana sambil menunggu codegen full.
 */

export type JobStatus = "draft" | "planning" | "running" | "paused" | "done" | "failed" | "partial";

export type SourceStatus = "pending" | "running" | "done" | "failed" | "skipped";

export type ScrapeStrategy = "static_html" | "headless" | "api" | "pdf" | "docx";

export type FieldDataType =
  | "string"
  | "number"
  | "boolean"
  | "date"
  | "datetime"
  | "url"
  | "email"
  | "phone"
  | "array"
  | "object";

export interface RequiredField {
  name: string;
  label?: string;
  data_type: FieldDataType;
  required?: boolean;
  description?: string;
}

export type FilterOp =
  | "eq"
  | "neq"
  | "contains"
  | "not_contains"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "in"
  | "not_in";

export interface IntentFilter {
  field?: string | null;
  op?: FilterOp | null;
  value?: string | null;
  expression: string;
}

export interface TargetScope {
  institution?: string | null;
  location?: string | null;
  country?: string | null;
}

export interface Intent {
  entity_type: string;
  entity_label?: string | null;
  target_scope?: TargetScope;
  required_fields: RequiredField[];
  filters?: IntentFilter[];
  output_format?: "csv" | "xlsx" | "json";
  seed_urls?: string[];
  language: "id" | "en";
  notes?: string | null;
}

export interface Source {
  id?: string;
  job_id?: string;
  url: string;
  domain?: string;
  title?: string;
  strategy: ScrapeStrategy;
  reliability_score?: number;
  status: SourceStatus;
  override_robots?: boolean;
  last_error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface PlanWarning {
  level: "info" | "warn" | "error";
  message: string;
  ref?: string;
}

export interface ScrapingPlan {
  intent: Intent;
  sources: Source[];
  estimated_record_count?: number;
  estimated_duration_sec?: number;
  warnings?: PlanWarning[];
}

export interface Record_ {
  id?: string;
  job_id?: string;
  source_id?: string | null;
  data: Record<string, unknown>;
  field_confidences?: Record<string, number>;
  source_url: string;
  completeness_score?: number;
  confidence_score?: number;
  fingerprint?: string;
  scraped_at: string;
  deleted_at?: string | null;
}

export interface Job {
  id: string;
  user_id?: string | null;
  prompt: string;
  parsed_plan?: ScrapingPlan;
  status: JobStatus;
  total_records?: number;
  avg_completeness?: number | null;
  avg_confidence?: number | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export type WsEventType =
  | "job_status"
  | "source_status"
  | "record_upsert"
  | "record_delete"
  | "progress"
  | "log"
  | "error"
  | "done";

export interface WsEvent<P = unknown> {
  type: WsEventType;
  job_id: string;
  ts: string;
  payload?: P;
}
