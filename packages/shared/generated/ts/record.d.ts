/* eslint-disable */
// AUTO-GENERATED from schema/record.json. Do not edit manually.

/**
 * Satu record hasil scraping. Schema field `data` bebas (JSONB) sesuai intent.required_fields.
 */
export interface Record {
  id?: string;
  job_id?: string;
  source_id?: string | null;
  /**
   * Dynamic key-value. Key sesuai intent.required_fields[].name.
   */
  data: {
    [k: string]: unknown;
  };
  /**
   * Confidence LLM per field (0..1).
   */
  field_confidences?: {
    [k: string]: number;
  };
  source_url: string;
  /**
   * filled_fields / total_required_fields.
   */
  completeness_score?: number;
  /**
   * Rata-rata tertimbang field_confidences.
   */
  confidence_score?: number;
  /**
   * Hash deterministik untuk dedup (nama+alamat+normalized phone).
   */
  fingerprint?: string;
  scraped_at: string;
  deleted_at?: string | null;
}
