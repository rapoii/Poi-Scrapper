/**
 * Client-side env helpers. Hanya baca NEXT_PUBLIC_* (di-embed saat build).
 */

export const env = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  wsBaseUrl: process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000",
} as const;
