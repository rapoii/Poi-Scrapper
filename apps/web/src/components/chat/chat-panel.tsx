"use client";

import { Sparkles } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage } from "@/components/chat/chat-message";
import { useCreateJob, useReparseJob } from "@/hooks/use-jobs";
import type { ApiError, Job } from "@/lib/api";
import { cn } from "@/lib/utils";

const SAMPLE_PROMPTS = [
  "data dokter spesialis jantung di RS Siloam Karawaci",
  "list of restaurants in Bandung with rating above 4",
  "data hotel bintang 5 di Bali",
];

interface ChatPanelProps {
  /** Job aktif (latest atau yang user select). */
  activeJob: Job | null;
  onJobCreated: (job: Job) => void;
  className?: string;
}

interface ChatTurn {
  id: string;
  role: "user" | "system";
  content: React.ReactNode;
  ts: string;
}

function fmtTime(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

export function ChatPanel({ activeJob, onJobCreated, className }: ChatPanelProps) {
  const create = useCreateJob();
  const reparse = useReparseJob(activeJob?.id ?? "");
  const scrollerRef = React.useRef<HTMLDivElement>(null);
  const canReviseActiveJob = activeJob?.status === "planning";

  // Build conversation turns dari activeJob — Phase 1.1 chat = "single round".
  // Phase 2+ akan ada multi-turn (revisi plan, dll). Stateless dulu.
  const turns: ChatTurn[] = React.useMemo(() => {
    if (!activeJob) return [];
    const out: ChatTurn[] = [
      {
        id: `${activeJob.id}-user`,
        role: "user",
        content: activeJob.prompt,
        ts: fmtTime(activeJob.created_at),
      },
    ];
    if (activeJob.parsed_plan) {
      const intent = activeJob.parsed_plan.intent;
      const fieldCount = intent.required_fields.length;
      const sourceCount = activeJob.parsed_plan.sources.length;
      out.push({
        id: `${activeJob.id}-system`,
        role: "system",
        content: (
          <span>
            Saya rencana scrape <strong>{intent.entity_label ?? intent.entity_type}</strong> dengan{" "}
            <strong>{fieldCount} field</strong>
            {sourceCount > 0 && <> dari {sourceCount} sumber</>}. Plan lengkap di panel kanan — kamu
            bisa edit fields atau approve untuk dijalankan.
          </span>
        ),
        ts: fmtTime(activeJob.created_at),
      });
    }
    return out;
  }, [activeJob]);

  // Auto-scroll ke bawah saat ada turn baru.
  React.useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns.length, create.isPending, reparse.isPending]);

  const handleSubmit = (prompt: string) => {
    if (canReviseActiveJob && activeJob) {
      reparse.mutate(
        { prompt },
        {
          onSuccess: (job) => {
            toast.success("Prompt re-parsed", {
              description: "Plan diperbarui dan source kandidat lama di-reset.",
            });
            onJobCreated(job);
          },
          onError: (err: ApiError) => {
            toast.error("Gagal re-parse prompt", {
              description: err.message,
            });
          },
        },
      );
      return;
    }

    create.mutate(
      { prompt },
      {
        onSuccess: (job) => {
          onJobCreated(job);
        },
        onError: (err: ApiError) => {
          toast.error("Gagal membuat job", {
            description: err.message,
          });
        },
      },
    );
  };

  const pending = create.isPending || reparse.isPending;
  const showWelcome = turns.length === 0 && !pending;

  return (
    <section
      className={cn(
        "border-border bg-card flex h-full flex-col overflow-hidden rounded-xl border shadow-sm",
        className,
      )}
      aria-label="Chat panel"
    >
      <header className="border-border bg-background/60 flex items-center gap-2 border-b px-4 py-3">
        <Sparkles className="text-primary h-4 w-4" />
        <h2 className="text-sm font-semibold">Chat</h2>
        <span className="text-muted-foreground ml-auto text-xs">
          {activeJob ? `Job · ${activeJob.id.slice(0, 8)}` : "New conversation"}
        </span>
      </header>

      <div ref={scrollerRef} className="flex-1 overflow-y-auto">
        <div className="flex flex-col gap-5 px-4 py-6">
          {showWelcome ? (
            <WelcomeState onPick={handleSubmit} disabled={pending} />
          ) : (
            <>
              {turns.map((t) => (
                <ChatMessage key={t.id} role={t.role} timestamp={t.ts}>
                  {t.content}
                </ChatMessage>
              ))}
              {pending && (
                <ChatMessage role="system">
                  <span className="text-muted-foreground italic">
                    {reparse.isPending
                      ? "Re-parsing prompt dan reset source kandidat…"
                      : "Memproses prompt + parsing intent…"}
                  </span>
                </ChatMessage>
              )}
            </>
          )}
        </div>
      </div>

      <div className="border-border bg-background/60 border-t p-3">
        <ChatInput
          onSubmit={handleSubmit}
          pending={pending}
          placeholder={
            canReviseActiveJob
              ? "Revisi prompt untuk re-parse plan aktif…"
              : "Ketik kebutuhan data baru…"
          }
        />
        <p className="text-muted-foreground mt-2 px-2 text-[11px]">
          {canReviseActiveJob ? "Prompt baru akan memperbarui plan aktif · " : ""}
          Tekan <kbd className="bg-muted rounded px-1 font-mono">Enter</kbd> untuk kirim ·{" "}
          <kbd className="bg-muted rounded px-1 font-mono">Shift+Enter</kbd> untuk baris baru
        </p>
      </div>
    </section>
  );
}

function WelcomeState({ onPick, disabled }: { onPick: (p: string) => void; disabled: boolean }) {
  return (
    <div className="flex flex-col items-start gap-4 px-1">
      <div className="bg-primary/10 text-primary rounded-full p-3">
        <Sparkles className="h-5 w-5" />
      </div>
      <div className="space-y-1">
        <h3 className="text-lg font-semibold">Mulai dari prompt natural</h3>
        <p className="text-muted-foreground text-sm">
          Deskripsikan data yang ingin di-scrape. Sistem akan rencanakan field-nya, cari sumber,
          lalu jalankan otomatis.
        </p>
      </div>
      <div className="flex w-full flex-col gap-2">
        <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
          Coba contoh
        </p>
        {SAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            disabled={disabled}
            onClick={() => onPick(p)}
            className="border-border hover:bg-accent hover:text-accent-foreground rounded-lg border px-3 py-2 text-left text-sm transition disabled:opacity-50"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
