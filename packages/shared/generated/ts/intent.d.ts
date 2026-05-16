/* eslint-disable */
// AUTO-GENERATED from schema/intent.json. Do not edit manually.

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
