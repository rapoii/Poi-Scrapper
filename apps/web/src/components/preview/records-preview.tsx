"use client";

import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import { Database, Download, ExternalLink, GripVertical, RefreshCw, Table2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { SourceProgressBadge } from "@/components/preview/source-progress-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobEvents } from "@/hooks/use-job-events";
import { useRecords } from "@/hooks/use-records";
import { api, type Job, type RequiredField, type ScrapedRecord, type Source } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { WsEvent } from "@poi/shared";

interface RecordsPreviewProps {
  job: Job;
  onJobUpdated?: (job: Job) => void;
}

type TableRecord = ScrapedRecord & {
  rowKey: string;
  rowNumber: number;
};

const ROW_HEIGHT = 44;
const OVERSCAN = 8;

export function RecordsPreview({ job, onJobUpdated }: RecordsPreviewProps) {
  const records = useRecords(job.id);
  const fields = job.parsed_plan?.intent.required_fields ?? [];
  const [editedRecords, setEditedRecords] = useState<Record<string, ScrapedRecord>>({});
  const [sourceStatuses, setSourceStatuses] = useState<Record<string, Source["status"]>>({});
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setEditedRecords({});
    setSourceStatuses({});
  }, [job.id]);

  const refreshJob = useCallback(async () => {
    try {
      onJobUpdated?.(await api.jobs.get(job.id));
    } catch {
      // Record query refresh is the primary UI update; job metrics can catch up later.
    }
  }, [job.id, onJobUpdated]);

  const handleJobEvent = useCallback(
    (event: WsEvent) => {
      const payload = (event.payload ?? {}) as {
        stage?: string;
        record_count?: number;
        source_id?: string;
        status?: Source["status"];
      };
      if (event.type === "source_status" && payload.source_id && payload.status) {
        setSourceStatuses((current) => ({
          ...current,
          [payload.source_id as string]: payload.status as Source["status"],
        }));
        void refreshJob();
      }
      if (event.type === "record_upsert" || payload.stage === "scrape") {
        void records.refetch();
      }
      if (payload.stage === "scrape" && event.type === "done") {
        toast.success("Scrape finished", {
          description: `${payload.record_count ?? 0} record tersimpan.`,
        });
        void refreshJob();
      }
    },
    [records, refreshJob],
  );

  useJobEvents(job.id, handleJobEvent);

  const items = useMemo(() => records.data?.items ?? [], [records.data?.items]);
  const itemsByKey = useMemo(() => {
    const map = new Map<string, ScrapedRecord>();
    items.forEach((item, index) => map.set(recordKey(item, index), item));
    return map;
  }, [items]);
  const displayItems = useMemo(
    () => items.map((item, index) => editedRecords[recordKey(item, index)] ?? item),
    [editedRecords, items],
  );
  const sources = useMemo(
    () =>
      (job.parsed_plan?.sources ?? []).map((source) =>
        source.id && sourceStatuses[source.id]
          ? { ...source, status: sourceStatuses[source.id] }
          : source,
      ),
    [job.parsed_plan?.sources, sourceStatuses],
  );
  const sourceIssues = useMemo(
    () =>
      sources
        .filter((source) => source.status === "failed" || source.status === "skipped")
        .map((source) => ({
          label: source.title ?? source.domain ?? source.url,
          message: source.last_error ?? `${source.status}: ${source.url}`,
        })),
    [sources],
  );

  const handleCellChange = useCallback(
    (rowKey: string, fieldName: string, value: unknown) => {
      const original = itemsByKey.get(rowKey);
      if (!original) return;
      setEditedRecords((current) => {
        const record = current[rowKey] ?? original;
        return {
          ...current,
          [rowKey]: {
            ...record,
            data: {
              ...record.data,
              [fieldName]: value,
            },
          },
        };
      });
    },
    [itemsByKey],
  );
  const recordTotal = records.data?.total ?? job.total_records ?? 0;

  const handleExportCsv = useCallback(async () => {
    setExporting(true);
    try {
      const { blob, filename } = await api.jobs.exportCsv(job.id);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
      toast.success("CSV exported", {
        description: `${recordTotal} row siap diunduh.`,
      });
    } catch (error) {
      toast.error("Gagal export CSV", {
        description: error instanceof Error ? error.message : "Export gagal diproses.",
      });
    } finally {
      setExporting(false);
    }
  }, [job.id, recordTotal]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="border-border bg-background/70 flex shrink-0 items-center gap-3 border-b px-5 py-3">
        <Table2 className="text-primary h-4 w-4" />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Records</h3>
          <p className="text-muted-foreground truncate text-xs">
            {job.status} · {recordTotal} rows
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant={job.status === "done" ? "success" : "secondary"} className="text-[10px]">
            {job.status}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              void records.refetch();
              void refreshJob();
            }}
            disabled={records.isFetching}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", records.isFetching && "animate-spin")} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              void handleExportCsv();
            }}
            disabled={recordTotal === 0 || exporting}
          >
            <Download className={cn("h-3.5 w-3.5", exporting && "animate-pulse")} />
            {exporting ? "Exporting..." : "Export CSV"}
          </Button>
        </div>
      </header>

      {sources.length > 0 && <SourceProgressStrip sources={sources} />}

      {records.isLoading ? (
        <RecordsSkeleton />
      ) : records.isError ? (
        <EmptyRecords title="Gagal memuat records" subtitle={records.error.message} />
      ) : items.length === 0 ? (
        <EmptyRecords
          title="Belum ada record"
          subtitle={
            sourceIssues.length > 0
              ? "Source sudah diproses, tapi belum ada record yang berhasil disimpan."
              : "Saat worker scraper menyimpan record, tabel ini akan otomatis refresh."
          }
          issues={sourceIssues}
        />
      ) : (
        <RecordsTable fields={fields} records={displayItems} onCellChange={handleCellChange} />
      )}
    </div>
  );
}

function RecordsTable({
  fields,
  records,
  onCellChange,
}: {
  fields: RequiredField[];
  records: ScrapedRecord[];
  onCellChange: (rowKey: string, fieldName: string, value: unknown) => void;
}) {
  const visibleFields = fields.length > 0 ? fields : inferFields(records);
  const tableRows = useMemo<TableRecord[]>(
    () =>
      records.map((record, index) => ({
        ...record,
        rowKey: recordKey(record, index),
        rowNumber: index + 1,
      })),
    [records],
  );
  const columns = useMemo<ColumnDef<TableRecord>[]>(
    () => [
      {
        id: "rowNumber",
        header: "#",
        size: 52,
        minSize: 48,
        maxSize: 70,
        enableResizing: false,
        cell: ({ row }) => (
          <span className="text-muted-foreground text-xs">{row.original.rowNumber}</span>
        ),
      },
      ...visibleFields.map<ColumnDef<TableRecord>>((field) => ({
        id: field.name,
        accessorFn: (row) => row.data[field.name],
        header: field.label ?? field.name,
        size: 180,
        minSize: 120,
        maxSize: 420,
        cell: ({ row }) => (
          <EditableCell
            field={field}
            value={row.original.data[field.name]}
            onChange={(value) => onCellChange(row.original.rowKey, field.name, value)}
          />
        ),
      })),
      {
        id: "quality",
        header: "Quality",
        size: 96,
        minSize: 88,
        maxSize: 130,
        cell: ({ row }) => <QualityBadge score={row.original.completeness_score ?? 0} />,
      },
      {
        id: "source",
        header: "Source",
        size: 220,
        minSize: 160,
        maxSize: 360,
        cell: ({ row }) => (
          <a
            href={row.original.source_url}
            target="_blank"
            rel="noreferrer"
            className="hover:text-primary inline-flex max-w-full items-center gap-1"
          >
            <span className="truncate">{hostnameFromUrl(row.original.source_url)}</span>
            <ExternalLink className="h-3 w-3 shrink-0" />
          </a>
        ),
      },
    ],
    [onCellChange, visibleFields],
  );
  const table = useReactTable({
    data: tableRows,
    columns,
    columnResizeMode: "onChange",
    defaultColumn: {
      minSize: 100,
      size: 180,
      maxSize: 420,
    },
    getCoreRowModel: getCoreRowModel(),
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(520);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const updateHeight = () => setViewportHeight(node.clientHeight || 520);
    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const rows = table.getRowModel().rows;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const endIndex = Math.min(rows.length, startIndex + visibleCount);
  const virtualRows = rows.slice(startIndex, endIndex);
  const topPadding = startIndex * ROW_HEIGHT;
  const bottomPadding = Math.max(0, (rows.length - endIndex) * ROW_HEIGHT);
  const leafColumnCount = table.getAllLeafColumns().length;

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-auto"
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
    >
      <table
        className="w-full min-w-[760px] border-separate border-spacing-0 text-sm"
        style={{ width: table.getTotalSize() }}
      >
        <thead className="bg-muted/70 sticky top-0 z-10">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="border-border border-b px-3 py-2 text-left text-xs font-semibold"
                  style={{ width: header.getSize() }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </span>
                    {header.column.getCanResize() && (
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground -mr-2 flex h-5 w-4 shrink-0 cursor-col-resize items-center justify-center"
                        onMouseDown={header.getResizeHandler()}
                        onTouchStart={header.getResizeHandler()}
                        title="Resize column"
                      >
                        <GripVertical className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {topPadding > 0 && (
            <tr aria-hidden="true">
              <td colSpan={leafColumnCount} style={{ height: topPadding }} />
            </tr>
          )}
          {virtualRows.map((row) => (
            <tr key={row.id} className="hover:bg-muted/30" style={{ height: ROW_HEIGHT }}>
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  className="border-border border-b px-3 py-2 align-top"
                  style={{ width: cell.column.getSize() }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
          {bottomPadding > 0 && (
            <tr aria-hidden="true">
              <td colSpan={leafColumnCount} style={{ height: bottomPadding }} />
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function EditableCell({
  field,
  value,
  onChange,
}: {
  field: RequiredField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(formatCellValue(value));

  useEffect(() => {
    if (!editing) setDraft(formatCellValue(value));
  }, [editing, value]);

  const commit = () => {
    setEditing(false);
    onChange(parseCellDraft(draft, field));
  };

  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
          if (event.key === "Escape") {
            setDraft(formatCellValue(value));
            setEditing(false);
          }
        }}
        className="border-input bg-background focus:ring-ring h-7 w-full rounded-sm border px-2 text-sm outline-none focus:ring-2"
      />
    );
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className="hover:bg-muted/50 block min-h-7 w-full rounded-sm px-1 py-0.5 text-left"
      title="Edit cell"
    >
      <CellValue value={value} />
    </button>
  );
}

function SourceProgressStrip({ sources }: { sources: Source[] }) {
  return (
    <div className="border-border bg-background/80 flex shrink-0 items-center gap-2 overflow-x-auto border-b px-5 py-2">
      <span className="text-muted-foreground shrink-0 text-xs font-medium">Sources</span>
      {sources.map((source, index) => (
        <div
          key={source.id ?? `${source.url}-${index}`}
          className="border-border bg-muted/25 flex max-w-[220px] shrink-0 items-center gap-2 rounded-md border px-2 py-1"
          title={source.last_error ?? source.url}
        >
          <SourceProgressBadge source={source} compact />
          <span className="truncate text-xs">{source.title ?? source.domain ?? source.url}</span>
        </div>
      ))}
    </div>
  );
}

function CellValue({ value }: { value: unknown }) {
  if (value == null || value === "") return <span className="text-muted-foreground">-</span>;
  if (Array.isArray(value)) return <span>{value.filter(Boolean).join(", ") || "-"}</span>;
  if (typeof value === "object") return <span>{JSON.stringify(value)}</span>;
  return <span>{String(value)}</span>;
}

function QualityBadge({ score }: { score: number }) {
  const variant = score >= 0.8 ? "success" : score >= 0.5 ? "warning" : "outline";
  return (
    <Badge variant={variant} className="text-[10px]">
      {(score * 100).toFixed(0)}%
    </Badge>
  );
}

function EmptyRecords({
  title,
  subtitle,
  issues,
}: {
  title: string;
  subtitle: string;
  issues?: { label: string; message: string }[];
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <div className="bg-muted text-muted-foreground rounded-full p-4">
        <Database className="h-6 w-6" />
      </div>
      <div className="space-y-1">
        <h3 className="font-semibold">{title}</h3>
        <p className="text-muted-foreground max-w-sm text-sm">{subtitle}</p>
      </div>
      {issues && issues.length > 0 && (
        <div className="border-border bg-muted/20 max-w-xl rounded-md border p-3 text-left">
          <p className="text-xs font-semibold">Source issues</p>
          <ul className="mt-2 space-y-2">
            {issues.slice(0, 4).map((issue) => (
              <li key={`${issue.label}-${issue.message}`} className="text-xs">
                <span className="font-medium">{issue.label}</span>
                <span className="text-muted-foreground block">{issue.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function RecordsSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-5">
      {Array.from({ length: 7 }).map((_, index) => (
        <Skeleton key={index} className="h-9 w-full" />
      ))}
    </div>
  );
}

function inferFields(records: ScrapedRecord[]): RequiredField[] {
  const names = new Set<string>();
  for (const record of records) {
    Object.keys(record.data).forEach((key) => names.add(key));
  }
  return Array.from(names).map((name) => ({ name, data_type: "string" }));
}

function recordKey(record: ScrapedRecord, index: number) {
  return record.id ?? record.fingerprint ?? `${record.source_url}-${index}`;
}

function hostnameFromUrl(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function formatCellValue(value: unknown) {
  if (value == null) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function parseCellDraft(value: string, field: RequiredField) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (field.data_type === "number") {
    const parsed = Number(trimmed.replace(",", "."));
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (field.data_type === "boolean") {
    return ["1", "true", "yes", "ya", "y"].includes(trimmed.toLowerCase());
  }
  if (field.data_type === "array") {
    return trimmed
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (field.data_type === "object") {
    try {
      return JSON.parse(trimmed) as Record<string, unknown>;
    } catch {
      return { value: trimmed };
    }
  }
  return trimmed;
}
