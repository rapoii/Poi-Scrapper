"use client";

/**
 * Top-level interactive shell untuk Phase 1.
 *
 * Tugas: simpan job aktif (hasil POST /jobs paling baru), pass ke ChatPanel +
 * PreviewPanel, plus sidebar history untuk reload job lama.
 */

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ChatPanel } from "@/components/chat/chat-panel";
import { JobHistorySidebar } from "@/components/job-history-sidebar";
import { PreviewPanel } from "@/components/preview/preview-panel";
import { jobsKeys } from "@/hooks/use-jobs";
import type { Job } from "@/lib/api";

export function JobShell() {
  const [activeJob, setActiveJob] = React.useState<Job | null>(null);
  const queryClient = useQueryClient();

  const handleJobChange = React.useCallback(
    (job: Job) => {
      setActiveJob(job);
      queryClient.setQueryData(jobsKeys.detail(job.id), job);
      void queryClient.invalidateQueries({ queryKey: jobsKeys.all });
    },
    [queryClient],
  );

  return (
    <div className="grid h-full gap-4 lg:grid-cols-[280px_minmax(0,2fr)] xl:grid-cols-[280px_minmax(0,2fr)_minmax(0,3fr)]">
      <JobHistorySidebar
        activeJobId={activeJob?.id}
        onSelectJob={handleJobChange}
        onNewJob={() => setActiveJob(null)}
        className="min-h-0"
      />
      <ChatPanel activeJob={activeJob} onJobCreated={handleJobChange} className="min-h-0" />
      <PreviewPanel
        job={activeJob}
        onJobUpdated={handleJobChange}
        className="min-h-0 lg:col-span-2 xl:col-span-1"
      />
    </div>
  );
}
