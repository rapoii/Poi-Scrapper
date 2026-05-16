"use client";

import { Ban, CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Source, SourceStatus } from "@/lib/api";

interface SourceProgressBadgeProps {
  source: Source;
  compact?: boolean;
}

const STATUS_CONFIG: Record<
  SourceStatus,
  {
    label: string;
    variant: "secondary" | "success" | "warning" | "destructive" | "outline";
    icon: React.ComponentType<{ className?: string }>;
    spin?: boolean;
  }
> = {
  pending: { label: "Pending", variant: "secondary", icon: Circle },
  running: { label: "Running", variant: "warning", icon: Loader2, spin: true },
  done: { label: "Done", variant: "success", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "destructive", icon: XCircle },
  skipped: { label: "Skipped", variant: "outline", icon: Ban },
};

export function SourceProgressBadge({ source, compact }: SourceProgressBadgeProps) {
  const config = STATUS_CONFIG[source.status];
  const Icon = config.icon;
  const title = source.last_error
    ? `${config.label}: ${source.last_error}`
    : `${config.label}: ${source.title ?? source.domain ?? source.url}`;

  return (
    <Badge variant={config.variant} className="shrink-0 gap-1 text-[10px]" title={title}>
      <Icon className={config.spin ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
      {!compact && config.label}
    </Badge>
  );
}
