"use client";

import { api, type HealthResponse } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Indikator koneksi backend: polling /health tiap 10 detik.
 * Dipakai untuk memastikan infra Phase 0 siap sebelum mulai Phase 1.
 */
export function HealthBanner() {
  const { data, isLoading, isError, error } = useQuery<HealthResponse, Error>({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 10_000,
    retry: 0,
  });

  if (isLoading) {
    return (
      <Card tone="muted">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Mengecek koneksi ke backend…</span>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card tone="danger">
        <AlertTriangle className="h-5 w-5" />
        <div className="flex flex-col">
          <span className="font-medium">Backend tidak dapat dihubungi</span>
          <span className="text-xs opacity-80">
            {error?.message ??
              "Pastikan `docker compose up -d postgres redis` + `make dev-api` sudah jalan."}
          </span>
        </div>
      </Card>
    );
  }

  const ok = data.status === "ok";
  return (
    <Card tone={ok ? "success" : "warning"}>
      {ok ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
      <div className="flex flex-col gap-0.5">
        <span className="font-medium">
          Backend {ok ? "online" : "degraded"} · v{data.version} ({data.app_env})
        </span>
        <span className="font-mono text-xs opacity-80">
          db: {formatDep(data.db)} · redis: {formatDep(data.redis)}
        </span>
      </div>
    </Card>
  );
}

function formatDep(info: { ok: boolean; latency_ms?: number; error?: string }): string {
  if (info.ok) return `ok (${info.latency_ms?.toFixed(1)} ms)`;
  return `down (${info.error ?? "unknown"})`;
}

type Tone = "muted" | "success" | "warning" | "danger";

function Card({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  const palette: Record<Tone, string> = {
    muted: "border-border bg-muted/40 text-muted-foreground",
    success:
      "border-[color:var(--color-success)]/40 bg-[color:var(--color-success)]/10 text-[color:var(--color-success)]",
    warning:
      "border-[color:var(--color-warning)]/40 bg-[color:var(--color-warning)]/10 text-[color:var(--color-warning)]",
    danger: "border-destructive/40 bg-destructive/10 text-destructive",
  };
  return (
    <div
      className={cn("flex items-start gap-3 rounded-lg border px-4 py-3 text-sm", palette[tone])}
    >
      {children}
    </div>
  );
}
