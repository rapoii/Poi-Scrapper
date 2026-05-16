"use client";

import {
  AlertTriangle,
  Building2,
  Check,
  ExternalLink,
  Filter,
  Globe,
  Hash,
  Languages,
  ListChecks,
  MapPin,
  Pencil,
  Play,
  Search,
  Sparkles,
} from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { PlanEditor } from "@/components/preview/plan-editor";
import { SourceProgressBadge } from "@/components/preview/source-progress-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobEvents } from "@/hooks/use-job-events";
import { useDiscoverSources, useRunJob, useUpdateSources } from "@/hooks/use-jobs";
import { api, type Job, type Source } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { WsEvent } from "@poi/shared";

interface PlanPreviewProps {
  job: Job | null;
  pending?: boolean;
  onJobUpdated?: (job: Job) => void;
}

export function PlanPreview({ job, pending, onJobUpdated }: PlanPreviewProps) {
  const [editing, setEditing] = useState(false);
  const [discoveryRunning, setDiscoveryRunning] = useState(false);
  const discoverMutation = useDiscoverSources(job?.id ?? "");
  const updateSourcesMutation = useUpdateSources(job?.id ?? "");
  const runMutation = useRunJob(job?.id ?? "");

  const refreshJob = useCallback(async () => {
    if (!job?.id) return;
    try {
      const updatedJob = await api.jobs.get(job.id);
      onJobUpdated?.(updatedJob);
    } catch {
      // Query cache will catch up on the next user action; don't toast twice.
    }
  }, [job?.id, onJobUpdated]);

  const handleJobEvent = useCallback(
    (event: WsEvent) => {
      const payload = (event.payload ?? {}) as {
        stage?: string;
        message?: string;
        source_count?: number;
        record_count?: number;
      };

      if (payload.stage === "run_approved" && event.type === "job_status") {
        void refreshJob();
        return;
      }

      if (event.type === "source_status") {
        void refreshJob();
        return;
      }

      if (payload.stage === "scrape" && event.type === "done") {
        toast.success("Scrape finished", {
          description: `${payload.record_count ?? 0} record tersimpan.`,
        });
        void refreshJob();
        return;
      }

      if (payload.stage !== "source_discovery") return;

      if (event.type === "progress") {
        setDiscoveryRunning(true);
        return;
      }
      if (event.type === "done") {
        setDiscoveryRunning(false);
        toast.success("Sources discovered", {
          description: `${payload.source_count ?? 0} kandidat siap direview`,
        });
        void refreshJob();
        return;
      }
      if (event.type === "error") {
        setDiscoveryRunning(false);
        toast.error("Gagal discover sources", {
          description: payload.message ?? "Worker gagal memproses source discovery.",
        });
      }
    },
    [refreshJob],
  );

  useJobEvents(job?.id ?? null, handleJobEvent);

  if (pending) return <PlanSkeleton />;
  if (!job?.parsed_plan) return <EmptyState />;

  const plan = job.parsed_plan;
  const intent = plan.intent;
  const editable = job.status === "planning";

  if (editing && editable) {
    return (
      <PlanEditor
        jobId={job.id}
        initialIntent={intent}
        onCancel={() => setEditing(false)}
        onSaved={(updatedJob) => {
          onJobUpdated?.(updatedJob);
          setEditing(false);
        }}
      />
    );
  }
  const scope = (intent.target_scope ?? {}) as {
    institution?: string;
    location?: string;
    country?: string;
  };

  const requiredFields = intent.required_fields.filter((f) => f.required ?? true);
  const optionalFields = intent.required_fields.filter((f) => !(f.required ?? true));
  const sourceDiscoveryBusy = discoverMutation.isPending || discoveryRunning;
  const selectedSources = plan.sources.filter((s) => s.status === "pending");
  const canRun =
    editable &&
    selectedSources.length > 0 &&
    !sourceDiscoveryBusy &&
    !updateSourcesMutation.isPending;

  const handleDiscoverSources = () => {
    setDiscoveryRunning(true);
    discoverMutation.mutate(undefined, {
      onSuccess: (updatedJob) => {
        toast.success("Source discovery queued", {
          description: "Progress akan masuk lewat WebSocket.",
        });
        onJobUpdated?.(updatedJob);
      },
      onError: (err) => {
        setDiscoveryRunning(false);
        toast.error("Gagal discover sources", {
          description: err.message,
        });
      },
    });
  };

  const handleToggleSource = (source: Source, enabled: boolean) => {
    if (!source.id) return;
    updateSourcesMutation.mutate(
      {
        sources: [
          {
            id: source.id,
            enabled,
            override_robots: source.override_robots ?? false,
          },
        ],
      },
      {
        onSuccess: (updatedJob) => {
          onJobUpdated?.(updatedJob);
        },
        onError: (err) => {
          toast.error("Gagal update source", {
            description: err.message,
          });
        },
      },
    );
  };

  const handleRunJob = () => {
    runMutation.mutate(undefined, {
      onSuccess: (updatedJob) => {
        toast.success("Job approved", {
          description: "Run record dibuat, menunggu worker scraper.",
        });
        onJobUpdated?.(updatedJob);
      },
      onError: (err) => {
        toast.error("Gagal menjalankan job", {
          description: err.message,
        });
      },
    });
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="flex flex-col gap-6 p-6">
        {/* Header */}
        <header className="space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles className="text-primary h-4 w-4" />
            <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
              Scraping Plan
            </span>
            <div className="ml-auto flex items-center gap-2">
              <Badge variant="secondary" className="text-[10px]">
                {job.status}
              </Badge>
              {editable && (
                <>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={handleDiscoverSources}
                    disabled={sourceDiscoveryBusy}
                  >
                    <Search className="h-3.5 w-3.5" />
                    {sourceDiscoveryBusy
                      ? "Finding..."
                      : plan.sources.length > 0
                        ? "Refresh"
                        : "Discover"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setEditing(true)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </Button>
                </>
              )}
            </div>
          </div>
          <h2 className="text-2xl font-semibold leading-tight">
            {intent.entity_label ?? intent.entity_type}
          </h2>
          {intent.notes && (
            <p className="text-muted-foreground text-sm leading-relaxed">{intent.notes}</p>
          )}
        </header>

        {/* Scope chips */}
        <div className="flex flex-wrap gap-2">
          <ScopeChip icon={Hash} label="Entity" value={intent.entity_type} />
          <ScopeChip icon={Languages} label="Language" value={intent.language} />
          {scope.institution && (
            <ScopeChip icon={Building2} label="Institution" value={scope.institution} />
          )}
          {scope.location && <ScopeChip icon={MapPin} label="Location" value={scope.location} />}
          {scope.country && <ScopeChip icon={Globe} label="Country" value={scope.country} />}
        </div>

        {/* Warnings */}
        {plan.warnings && plan.warnings.length > 0 && (
          <div className="border-warning/30 bg-warning/5 rounded-lg border px-4 py-3">
            <div className="text-warning flex items-start gap-2 text-sm">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <ul className="space-y-1">
                {plan.warnings.map((w, i) => (
                  <li key={i}>{typeof w === "string" ? w : w.message}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Required fields */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <ListChecks className="text-muted-foreground h-4 w-4" />
            <h3 className="text-sm font-semibold">
              Required fields
              <span className="text-muted-foreground ml-1 font-normal">
                ({requiredFields.length})
              </span>
            </h3>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {requiredFields.map((f) => (
              <FieldRow key={f.name} name={f.name} label={f.label} type={f.data_type} />
            ))}
          </div>
        </section>

        {/* Optional fields */}
        {optionalFields.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <ListChecks className="text-muted-foreground h-4 w-4" />
              <h3 className="text-sm font-semibold">
                Optional fields
                <span className="text-muted-foreground ml-1 font-normal">
                  ({optionalFields.length})
                </span>
              </h3>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {optionalFields.map((f) => (
                <FieldRow key={f.name} name={f.name} label={f.label} type={f.data_type} optional />
              ))}
            </div>
          </section>
        )}

        {/* Filters */}
        {intent.filters && intent.filters.length > 0 && (
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <Filter className="text-muted-foreground h-4 w-4" />
              <h3 className="text-sm font-semibold">Filters</h3>
            </div>
            <ul className="border-border bg-muted/30 space-y-2 rounded-lg border p-3 text-sm">
              {intent.filters.map((f, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Badge
                    variant={f.op === "not_contains" ? "warning" : "outline"}
                    className="shrink-0"
                  >
                    {f.op ?? "filter"}
                  </Badge>
                  <span className="text-muted-foreground">{f.expression}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Sources */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Globe className="text-muted-foreground h-4 w-4" />
            <h3 className="text-sm font-semibold">
              Sources
              <span className="text-muted-foreground ml-1 font-normal">
                ({selectedSources.length}/{plan.sources.length})
              </span>
            </h3>
            {editable && plan.sources.length > 0 && (
              <Button
                size="sm"
                className="ml-auto h-7 px-2 text-xs"
                onClick={handleRunJob}
                disabled={!canRun || runMutation.isPending}
              >
                {runMutation.isPending ? (
                  <>
                    <Play className="h-3.5 w-3.5 animate-pulse" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5" />
                    Approve & Run
                  </>
                )}
              </Button>
            )}
          </div>
          {plan.sources.length === 0 ? (
            <p className="text-muted-foreground border-border rounded-lg border border-dashed bg-transparent px-4 py-6 text-center text-sm">
              Belum ada source kandidat.
            </p>
          ) : (
            <ul className="space-y-2">
              {plan.sources.map((s, i) => (
                <li
                  key={s.id ?? `${s.url}-${i}`}
                  className={cn(
                    "border-border flex items-center gap-3 rounded-lg border px-3 py-2 text-sm transition",
                    s.status === "skipped" && "bg-muted/30 opacity-60",
                  )}
                >
                  {editable ? (
                    <button
                      type="button"
                      disabled={!s.id || updateSourcesMutation.isPending}
                      onClick={() => handleToggleSource(s, s.status === "skipped")}
                      className={cn(
                        "border-input flex h-5 w-5 shrink-0 items-center justify-center rounded border transition",
                        s.status !== "skipped"
                          ? "border-primary bg-primary text-primary-foreground"
                          : "bg-background text-transparent",
                      )}
                      title={s.status === "skipped" ? "Enable source" : "Skip source"}
                    >
                      {s.status !== "skipped" && <Check className="h-3.5 w-3.5" />}
                    </button>
                  ) : (
                    <Globe className="text-muted-foreground h-4 w-4 shrink-0" />
                  )}
                  <div className="min-w-0 flex-1">
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:text-primary inline-flex max-w-full items-center gap-1 font-medium"
                    >
                      <span className="truncate">{s.title ?? s.domain ?? s.url}</span>
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                    <p className="text-muted-foreground truncate text-xs">{s.domain ?? s.url}</p>
                  </div>
                  <SourceProgressBadge source={s} />
                  {s.reliability_score != null && (
                    <Badge variant="outline" className="shrink-0">
                      {(s.reliability_score * 100).toFixed(0)}%
                    </Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function ScopeChip({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <span
      className={cn(
        "border-border bg-muted/40 inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs",
      )}
    >
      <Icon className="text-muted-foreground h-3.5 w-3.5" />
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium">{value}</span>
    </span>
  );
}

function FieldRow({
  name,
  label,
  type,
  optional,
}: {
  name: string;
  label?: string;
  type: string;
  optional?: boolean;
}) {
  return (
    <div className="border-border flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm">
      <div className="min-w-0 flex-1">
        <span className="font-medium">{label ?? name}</span>
        <span className="text-muted-foreground ml-1 font-mono text-xs">·{name}</span>
      </div>
      <Badge variant={optional ? "outline" : "secondary"} className="shrink-0 text-[10px]">
        {type}
      </Badge>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <div className="bg-muted text-muted-foreground rounded-full p-4">
        <Sparkles className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <h3 className="font-semibold">Plan akan muncul di sini</h3>
        <p className="text-muted-foreground text-sm">
          Kirim prompt di chat → sistem akan parse intent + tampilin field yang mau di-scrape.
        </p>
      </div>
    </div>
  );
}

function PlanSkeleton() {
  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-7 w-3/4" />
      </div>
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-28" />
        ))}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
