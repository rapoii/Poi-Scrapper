import { Sparkles } from "lucide-react";

import { HealthPill } from "@/components/health-pill";
import { JobShell } from "@/components/job-shell";

export default function HomePage() {
  return (
    <main className="mx-auto flex h-[100dvh] max-w-7xl flex-col gap-3 px-4 py-4 lg:px-6 lg:py-6">
      <header className="flex shrink-0 items-center gap-3">
        <span className="border-border bg-muted/40 text-muted-foreground inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium">
          <Sparkles className="text-primary h-3.5 w-3.5" />
          PoiScrapper v3
          <span className="bg-muted-foreground/40 mx-1 h-3 w-px" />
          <span>Phase 1.8 · Job History</span>
        </span>
        <h1 className="sr-only">PoiScrapper v3 — natural-language scraping</h1>
        <div className="ml-auto">
          <HealthPill />
        </div>
      </header>

      <div className="min-h-0 flex-1">
        <JobShell />
      </div>
    </main>
  );
}
