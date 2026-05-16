"use client";

import { Check, Plus, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateIntent } from "@/hooks/use-jobs";
import type { FieldDataType, FilterOp, Intent, IntentFilter, Job, RequiredField } from "@/lib/api";
import { cn } from "@/lib/utils";

const FIELD_TYPES: FieldDataType[] = [
  "string",
  "number",
  "boolean",
  "date",
  "datetime",
  "url",
  "email",
  "phone",
  "array",
  "object",
];

const FILTER_OPS: FilterOp[] = [
  "eq",
  "neq",
  "contains",
  "not_contains",
  "gt",
  "gte",
  "lt",
  "lte",
  "in",
  "not_in",
];

interface PlanEditorProps {
  jobId: string;
  initialIntent: Intent;
  onCancel: () => void;
  onSaved: (job: Job) => void;
}

export function PlanEditor({ jobId, initialIntent, onCancel, onSaved }: PlanEditorProps) {
  const [draft, setDraft] = useState<Intent>(() => deepClone(initialIntent));
  const updateMutation = useUpdateIntent(jobId);

  // Sync draft kalau initialIntent berubah dari luar (mis. user re-prompt).
  useEffect(() => {
    setDraft(deepClone(initialIntent));
  }, [initialIntent]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(initialIntent);
  const fieldNamesValid = draft.required_fields.every(
    (f) => f.name.trim().length > 0 && /^[a-z][a-z0-9_]*$/i.test(f.name.trim()),
  );
  const noDuplicateNames =
    new Set(draft.required_fields.map((f) => f.name.trim())).size === draft.required_fields.length;
  const valid = draft.required_fields.length > 0 && fieldNamesValid && noDuplicateNames;

  const handleSave = () => {
    if (!valid) {
      toast.error("Plan tidak valid", {
        description: "Pastikan semua field punya nama unik (snake_case).",
      });
      return;
    }
    updateMutation.mutate(
      { intent: draft },
      {
        onSuccess: (job) => {
          toast.success("Plan saved", {
            description: `${draft.required_fields.length} field, ${draft.filters?.length ?? 0} filter`,
          });
          onSaved(job);
        },
        onError: (err) => {
          toast.error("Gagal save plan", {
            description: err.message,
          });
        },
      },
    );
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Sticky header */}
      <header className="border-border bg-background sticky top-0 z-10 flex shrink-0 items-center gap-2 border-b px-6 py-3">
        <Badge variant="warning" className="text-[10px]">
          Editing
        </Badge>
        <h2 className="text-sm font-semibold">Edit Scraping Plan</h2>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={updateMutation.isPending}>
            <X className="h-4 w-4" />
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!dirty || !valid || updateMutation.isPending}
          >
            {updateMutation.isPending ? (
              <>
                <Save className="h-4 w-4 animate-pulse" />
                Saving…
              </>
            ) : (
              <>
                <Check className="h-4 w-4" />
                Save
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="space-y-6">
          {/* Identity */}
          <Section title="Identity">
            <FieldGrid>
              <Labeled label="Entity type">
                <Input
                  value={draft.entity_type}
                  onChange={(e) => setDraft({ ...draft, entity_type: e.target.value.trim() })}
                  placeholder="doctor"
                />
              </Labeled>
              <Labeled label="Label">
                <Input
                  value={draft.entity_label ?? ""}
                  onChange={(e) => setDraft({ ...draft, entity_label: e.target.value || null })}
                  placeholder="Dokter Spesialis Jantung"
                />
              </Labeled>
              <Labeled label="Language">
                <Select
                  value={draft.language}
                  onChange={(e) =>
                    setDraft({ ...draft, language: e.target.value as Intent["language"] })
                  }
                >
                  <option value="id">Indonesian (id)</option>
                  <option value="en">English (en)</option>
                </Select>
              </Labeled>
              <Labeled label="Output format">
                <Select
                  value={draft.output_format ?? "csv"}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      output_format: e.target.value as Intent["output_format"],
                    })
                  }
                >
                  <option value="csv">CSV</option>
                  <option value="xlsx">XLSX</option>
                  <option value="json">JSON</option>
                </Select>
              </Labeled>
            </FieldGrid>

            <Labeled label="Notes">
              <Textarea
                value={draft.notes ?? ""}
                onChange={(e) => setDraft({ ...draft, notes: e.target.value || null })}
                placeholder="Catatan untuk plan ini…"
                rows={2}
              />
            </Labeled>
          </Section>

          {/* Target scope */}
          <Section title="Target scope">
            <FieldGrid>
              <Labeled label="Institution">
                <Input
                  value={draft.target_scope?.institution ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      target_scope: {
                        ...draft.target_scope,
                        institution: e.target.value || null,
                      },
                    })
                  }
                  placeholder="RS Siloam Karawaci"
                />
              </Labeled>
              <Labeled label="Location">
                <Input
                  value={draft.target_scope?.location ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      target_scope: {
                        ...draft.target_scope,
                        location: e.target.value || null,
                      },
                    })
                  }
                  placeholder="Karawaci"
                />
              </Labeled>
              <Labeled label="Country">
                <Input
                  value={draft.target_scope?.country ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      target_scope: {
                        ...draft.target_scope,
                        country: e.target.value || null,
                      },
                    })
                  }
                  placeholder="ID"
                  maxLength={3}
                />
              </Labeled>
            </FieldGrid>
          </Section>

          {/* Required fields */}
          <Section
            title="Fields"
            actions={
              <Badge variant="outline" className="font-mono">
                {draft.required_fields.length}
              </Badge>
            }
          >
            <FieldsTable
              fields={draft.required_fields}
              onChange={(fields) => setDraft({ ...draft, required_fields: fields })}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2 w-fit"
              onClick={() =>
                setDraft({
                  ...draft,
                  required_fields: [
                    ...draft.required_fields,
                    {
                      name: `field_${draft.required_fields.length + 1}`,
                      label: "",
                      data_type: "string",
                      required: true,
                    },
                  ],
                })
              }
            >
              <Plus className="h-4 w-4" />
              Add field
            </Button>
            {!fieldNamesValid && (
              <p className="text-destructive text-xs">
                Nama field harus snake_case (huruf kecil, angka, underscore).
              </p>
            )}
            {!noDuplicateNames && (
              <p className="text-destructive text-xs">Ada nama field yang duplikat — harus unik.</p>
            )}
          </Section>

          {/* Filters */}
          <Section
            title="Filters"
            actions={
              <Badge variant="outline" className="font-mono">
                {draft.filters?.length ?? 0}
              </Badge>
            }
          >
            <FiltersTable
              filters={draft.filters ?? []}
              onChange={(filters) => setDraft({ ...draft, filters })}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2 w-fit"
              onClick={() =>
                setDraft({
                  ...draft,
                  filters: [
                    ...(draft.filters ?? []),
                    { field: "", op: "eq", value: "", expression: "" },
                  ],
                })
              }
            >
              <Plus className="h-4 w-4" />
              Add filter
            </Button>
          </Section>
        </div>
      </div>
    </div>
  );
}

// ---- Sub-components --------------------------------------------------------

function FieldsTable({
  fields,
  onChange,
}: {
  fields: RequiredField[];
  onChange: (next: RequiredField[]) => void;
}) {
  if (fields.length === 0) {
    return (
      <p className="text-muted-foreground border-border rounded-md border border-dashed px-4 py-6 text-center text-sm">
        Belum ada field. Klik &ldquo;Add field&rdquo; di bawah.
      </p>
    );
  }

  const setField = (idx: number, patch: Partial<RequiredField>) => {
    const next = [...fields];
    next[idx] = { ...next[idx], ...patch };
    onChange(next);
  };
  const removeField = (idx: number) => {
    const next = [...fields];
    next.splice(idx, 1);
    onChange(next);
  };

  return (
    <ul className="border-border divide-y rounded-md border">
      {fields.map((f, idx) => (
        <li
          key={idx}
          className="hover:bg-muted/30 grid grid-cols-[auto_1fr_1fr_auto_auto] items-center gap-2 px-2 py-1.5"
        >
          <button
            type="button"
            onClick={() => setField(idx, { required: !(f.required ?? true) })}
            className={cn(
              "border-input flex h-6 w-6 shrink-0 items-center justify-center rounded border",
              (f.required ?? true)
                ? "border-primary bg-primary text-primary-foreground"
                : "bg-background",
            )}
            title={
              (f.required ?? true)
                ? "Required (klik untuk optional)"
                : "Optional (klik untuk required)"
            }
          >
            {(f.required ?? true) && <Check className="h-3.5 w-3.5" />}
          </button>
          <Input
            value={f.name}
            onChange={(e) => setField(idx, { name: e.target.value })}
            placeholder="snake_case_name"
            className="font-mono text-xs"
          />
          <Input
            value={f.label ?? ""}
            onChange={(e) => setField(idx, { label: e.target.value })}
            placeholder="Display label"
            className="text-xs"
          />
          <Select
            value={f.data_type}
            onChange={(e) => setField(idx, { data_type: e.target.value as FieldDataType })}
            className="w-24 text-xs"
          >
            {FIELD_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-destructive h-7 w-7"
            onClick={() => removeField(idx)}
            title="Hapus field"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </li>
      ))}
    </ul>
  );
}

function FiltersTable({
  filters,
  onChange,
}: {
  filters: IntentFilter[];
  onChange: (next: IntentFilter[]) => void;
}) {
  if (filters.length === 0) {
    return (
      <p className="text-muted-foreground border-border rounded-md border border-dashed px-4 py-6 text-center text-sm">
        Tidak ada filter. Klik &ldquo;Add filter&rdquo; untuk menambah.
      </p>
    );
  }

  const setFilter = (idx: number, patch: Partial<IntentFilter>) => {
    const next = [...filters];
    next[idx] = { ...next[idx], ...patch };
    onChange(next);
  };
  const removeFilter = (idx: number) => {
    const next = [...filters];
    next.splice(idx, 1);
    onChange(next);
  };

  return (
    <ul className="space-y-2">
      {filters.map((f, idx) => (
        <li
          key={idx}
          className="border-border bg-muted/20 grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2 rounded-md border p-2"
        >
          <Input
            value={f.field ?? ""}
            onChange={(e) => setFilter(idx, { field: e.target.value || null })}
            placeholder="field"
            className="font-mono text-xs"
          />
          <Select
            value={f.op ?? "eq"}
            onChange={(e) => setFilter(idx, { op: e.target.value as FilterOp })}
            className="w-28 text-xs"
          >
            {FILTER_OPS.map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </Select>
          <Input
            value={f.value ?? ""}
            onChange={(e) => setFilter(idx, { value: e.target.value || null })}
            placeholder="value"
            className="text-xs"
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-destructive h-7 w-7"
            onClick={() => removeFilter(idx)}
            title="Hapus filter"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          {f.expression && (
            <p className="text-muted-foreground col-span-4 px-1 text-xs italic">
              from prompt: &ldquo;{f.expression}&rdquo;
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

function Section({
  title,
  children,
  actions,
}: {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {actions}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
        {label}
      </span>
      {children}
    </label>
  );
}

function FieldGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
