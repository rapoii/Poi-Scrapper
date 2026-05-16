/* eslint-disable */
// AUTO-GENERATED from schema/source.json. Do not edit manually.

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
