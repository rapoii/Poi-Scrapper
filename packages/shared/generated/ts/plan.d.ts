/* eslint-disable */
// AUTO-GENERATED from schema/plan.json. Do not edit manually.

/**
 * Rencana scraping yang direview user sebelum run. Gabungan Intent + daftar Source + estimasi.
 */
export interface ScrapingPlan {
  intent: Intent;
  sources: Source[];
  /**
   * Estimasi jumlah record yang bisa di-scrape (heuristik).
   */
  estimated_record_count?: number;
  /**
   * Estimasi durasi total eksekusi dalam detik.
   */
  estimated_duration_sec?: number;
  /**
   * Peringatan dari planner (robots.txt, PII risk, dll).
   */
  warnings?: {
    level: "info" | "warn" | "error";
    message: string;
    ref?: string;
  }[];
}
/**
 * Hasil parsing prompt user oleh LLM intent parser.
 */
export interface Intent {
  /**
   * Jenis entity yang ingin di-scrape, misal 'doctor', 'restaurant', 'school'.
   */
  entity_type: string;
  /**
   * Label yang lebih manusiawi untuk UI, misal 'Dokter di RS Siloam Karawaci'.
   */
  entity_label?: string;
  /**
   * Konteks target yang dibatasi user, misal institusi, kota, rentang waktu.
   */
  target_scope?: {
    institution?: string;
    location?: string;
    country?: string;
    [k: string]: unknown;
  };
  /**
   * Daftar field yang wajib di-scrape (di-infer + optional user override).
   *
   * @minItems 1
   */
  required_fields: [
    {
      name: string;
      label?: string;
      data_type:
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
      required?: boolean;
      description?: string;
    },
    ...{
      name: string;
      label?: string;
      data_type:
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
      required?: boolean;
      description?: string;
    }[],
  ];
  /**
   * Kondisi filter tambahan, misal 'exclude dokter umum'.
   */
  filters?: {
    field?: string;
    op?: "eq" | "neq" | "contains" | "not_contains" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in";
    value?: unknown;
    expression: string;
  }[];
  output_format?: "csv" | "xlsx" | "json";
  /**
   * URL kandidat hasil tebakan LLM (boleh kosong; bisa dilengkapi di tahap discovery).
   */
  seed_urls?: string[];
  /**
   * Bahasa prompt user (ISO 639-1).
   */
  language: "id" | "en";
  /**
   * Catatan bebas hasil interpretasi LLM untuk ditampilkan ke user.
   */
  notes?: string;
}
/**
 * Target URL yang akan di-scrape beserta strategy & status.
 */
export interface Source {
  id?: string;
  job_id?: string;
  url: string;
  domain?: string;
  title?: string;
  /**
   * Metode fetch + parse yang dipakai.
   */
  strategy: "static_html" | "headless" | "api" | "pdf" | "docx";
  /**
   * 0.4*domain_authority + 0.4*field_coverage + 0.2*freshness.
   */
  reliability_score?: number;
  status: "pending" | "running" | "done" | "failed" | "skipped";
  override_robots?: boolean;
  last_error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}
