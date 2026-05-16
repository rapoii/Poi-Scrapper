/* eslint-disable */
// AUTO-GENERATED from schema/ws_event.json. Do not edit manually.

/**
 * Payload WebSocket yang di-push backend ke client selama job jalan.
 */
export interface WsEvent {
  type:
    | "job_status"
    | "source_status"
    | "record_upsert"
    | "record_delete"
    | "progress"
    | "log"
    | "error"
    | "done";
  job_id: string;
  ts: string;
  /**
   * Payload spesifik per type. FE cek berdasarkan type.
   */
  payload?: {
    [k: string]: unknown;
  };
}
