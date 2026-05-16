"use client";

import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Database,
  History,
  Loader2,
  Plus,
  RefreshCw,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobs, jobsKeys } from "@/hooks/use-jobs";
import { api, type ApiError, type Job, type JobListItem, type JobStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useQueryClient } from "@tanstack/react-query";

interface JobHistorySidebarProps {
  activeJobId?: string | null;
  onSelectJob: (job: Job) => void;
  onNewJob: () => void;
  className?: string;
}

const STATUS_CONFIG: Record<
  JobStatus,
  {
    label: string;
    variant: "secondary" | "success" | "warning" | "destructive" | "outline";
    icon: React.ComponentType<{ className?: string }>;
    spin?: boolean;
  }
> = {
  draft: { label: "Draft", variant: "outline", icon: Clock3 },
  planning: { label: "Planning", variant: "secondary", icon: Clock3 },
  running: { label: "Running", variant: "warning", icon: Loader2, spin: true },
  paused: { label: "Paused", variant: "outline", icon: Clock3 },
  done: { label: "Done", variant: "success", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "destructive", icon: AlertCircle },
  partial: { label: "Partial", variant: "warning", icon: AlertCircle },
};

export function JobHistorySidebar({
  activeJobId,
  onSelectJob,
  onNewJob,
  className,
}: JobHistorySidebarProps) {
  const queryClient = useQueryClient();
  const jobs = useJobs({ limit: 30 });
  const [loadingJobId, setLoadingJobId] = React.useState<string | null>(null);

  const handleSelect = React.useCallback(
    async (jobId: string) => {
      setLoadingJobId(jobId);
      try {
        const job = await queryClient.fetchQuery({
          queryKey: jobsKeys.detail(jobId),
          queryFn: () => api.jobs.get(jobId),
        });
        onSelectJob(job);
      } catch (error) {
        toast.error("Gagal membuka job", {
          description: error instanceof Error ? error.message : "Job detail tidak bisa dimuat.",
        });
      } finally {
        setLoadingJobId(null);
      }
    },
    [onSelectJob, queryClient],
  );

  return (
    <aside
      className={cn(
        "border-border bg-card flex h-full min-h-[220px] flex-col overflow-hidden rounded-xl border shadow-sm",
        className,
      )}
      aria-label="Job history"
    >
      <header className="border-border bg-background/60 flex shrink-0 items-center gap-2 border-b px-4 py-3">
        <History className="text-primary h-4 w-4" />
        <h2 className="text-sm font-semibold">History</h2>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="ml-auto h-7 w-7"
          onClick={() => void jobs.refetch()}
          disabled={jobs.isFetching}
          title="Refresh jobs"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", jobs.isFetching && "animate-spin")} />
        </Button>
      </header>

      <div className="border-border border-b p-3">
        <Button type="button" size="sm" className="h-8 w-full justify-start" onClick={onNewJob}>
          <Plus className="h-3.5 w-3.5" />
          New job
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {jobs.isLoading ? (
          <HistorySkeleton />
        ) : jobs.isError ? (
          <HistoryEmpty
            icon={AlertCircle}
            title="History gagal dimuat"
            subtitle={(jobs.error as ApiError).message}
          />
        ) : (jobs.data?.items.length ?? 0) === 0 ? (
          <HistoryEmpty
            icon={Database}
            title="Belum ada job"
            subtitle="Job baru akan muncul di sini setelah prompt pertama dibuat."
          />
        ) : (
          <ul className="space-y-1">
            {jobs.data?.items.map((job) => (
              <li key={job.id}>
                <JobHistoryItem
                  job={job}
                  active={job.id === activeJobId}
                  loading={loadingJobId === job.id}
                  onClick={() => {
                    void handleSelect(job.id);
                  }}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {jobs.data && jobs.data.total > jobs.data.items.length && (
        <footer className="border-border text-muted-foreground border-t px-4 py-2 text-xs">
          Showing {jobs.data.items.length} of {jobs.data.total}
        </footer>
      )}
    </aside>
  );
}

function JobHistoryItem({
  job,
  active,
  loading,
  onClick,
}: {
  job: JobListItem;
  active: boolean;
  loading: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "hover:bg-accent hover:text-accent-foreground flex w-full flex-col gap-2 rounded-lg px-3 py-2.5 text-left transition",
        active && "bg-accent text-accent-foreground",
      )}
    >
      <div className="flex min-w-0 items-start gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{job.prompt}</span>
        {loading ? <Loader2 className="mt-0.5 h-3.5 w-3.5 animate-spin" /> : null}
      </div>
      <div className="flex items-center gap-2">
        <JobStatusBadge status={job.status} />
        <span className="text-muted-foreground truncate text-xs">
          {formatRelative(job.created_at)}
        </span>
      </div>
      <div className="text-muted-foreground flex items-center justify-between gap-2 text-xs">
        <span>{job.total_records} rows</span>
        {job.avg_completeness != null && <span>{(job.avg_completeness * 100).toFixed(0)}%</span>}
      </div>
    </button>
  );
}

function JobStatusBadge({ status }: { status: JobStatus }) {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;
  return (
    <Badge variant={config.variant} className="gap-1 text-[10px]">
      <Icon className={config.spin ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
      {config.label}
    </Badge>
  );
}

function HistoryEmpty({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-4 py-8 text-center">
      <div className="bg-muted text-muted-foreground rounded-full p-3">
        <Icon className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-muted-foreground text-xs leading-relaxed">{subtitle}</p>
      </div>
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-2 p-1">
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="space-y-2 rounded-lg px-3 py-2.5">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

function formatRelative(value: string) {
  const date = new Date(value);
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60_000);
  if (diffMinutes < 1) return "baru saja";
  if (diffMinutes < 60) return `${diffMinutes}m lalu`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}j lalu`;
  return date.toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
}
