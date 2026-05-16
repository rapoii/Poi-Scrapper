"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";

import { api, type HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Compact health indicator untuk chat layout.
 * - Loading → spinner pill abu-abu.
 * - OK      → titik hijau + label.
 * - Down    → expanded warning card dengan detail latency / error.
 */
export function HealthPill({ className }: { className?: string }) {
  const { data, isLoading, isError, error } = useQuery<HealthResponse, Error>({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 15_000,
    retry: 0,
  });

  if (isLoading) {
    return (
      <Pill tone="muted" className={className}>
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>Checking…</span>
      </Pill>
    );
  }

  if (isError || !data) {
    return (
      <div
        role="alert"
        className={cn(
          "border-destructive/40 bg-destructive/10 text-destructive flex items-start gap-2 rounded-md border px-3 py-2 text-xs",
          className,
        )}
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex flex-col">
          <span className="font-semibold">Backend tidak terhubung</span>
          <span className="opacity-80">{error?.message ?? "Pastikan API + DB + Redis jalan."}</span>
        </div>
      </div>
    );
  }

  const ok = data.status === "ok";
  if (ok) {
    return (
      <Pill tone="success" className={className} title={detailTooltip(data)}>
        <span className="bg-success h-2 w-2 rounded-full" aria-hidden />
        <span>Backend online</span>
        <span className="text-muted-foreground font-mono">v{data.version}</span>
      </Pill>
    );
  }

  return (
    <div
      role="status"
      className={cn(
        "border-warning/40 bg-warning/10 text-warning flex items-start gap-2 rounded-md border px-3 py-2 text-xs",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex flex-col">
        <span className="font-semibold">Backend degraded</span>
        <span className="font-mono opacity-80">
          db: {formatDep(data.db)} · redis: {formatDep(data.redis)}
        </span>
      </div>
    </div>
  );
}

function formatDep(info: { ok: boolean; latency_ms?: number; error?: string }): string {
  if (info.ok) return `ok (${info.latency_ms?.toFixed(1)}ms)`;
  return `down (${info.error ?? "unknown"})`;
}

function detailTooltip(d: HealthResponse): string {
  return `db ${formatDep(d.db)} · redis ${formatDep(d.redis)} · env ${d.app_env}`;
}

type Tone = "muted" | "success";

function Pill({
  tone,
  className,
  children,
  ...rest
}: {
  tone: Tone;
  className?: string;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  const palette: Record<Tone, string> = {
    muted: "border-border bg-muted/40 text-muted-foreground",
    success: "border-success/30 bg-success/10 text-success",
  };
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
        palette[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
