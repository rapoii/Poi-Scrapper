"use client";

import { Eye } from "lucide-react";

import { PlanPreview } from "@/components/preview/plan-preview";
import { RecordsPreview } from "@/components/preview/records-preview";
import { Badge } from "@/components/ui/badge";
import type { Job } from "@/lib/api";
import { cn } from "@/lib/utils";

interface PreviewPanelProps {
  job: Job | null;
  pending?: boolean;
  onJobUpdated?: (job: Job) => void;
  className?: string;
}

export function PreviewPanel({ job, pending, onJobUpdated, className }: PreviewPanelProps) {
  const showRecords = !!job && job.status !== "planning" && job.status !== "draft";

  return (
    <section
      className={cn(
        "border-border bg-card flex h-full flex-col overflow-hidden rounded-xl border shadow-sm",
        className,
      )}
      aria-label="Preview panel"
    >
      <header className="border-border bg-background/60 flex items-center gap-2 border-b px-4 py-3">
        <Eye className="text-primary h-4 w-4" />
        <h2 className="text-sm font-semibold">Preview</h2>
        <Badge variant="outline" className="ml-auto text-[10px]">
          {showRecords ? "Phase 1.6 · Records" : "Phase 1.4 · Review"}
        </Badge>
      </header>

      <div className="flex-1 overflow-hidden">
        {showRecords ? (
          <RecordsPreview job={job} onJobUpdated={onJobUpdated} />
        ) : (
          <PlanPreview job={job} pending={pending} onJobUpdated={onJobUpdated} />
        )}
      </div>
    </section>
  );
}
