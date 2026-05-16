"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type ApiError, type RecordListResponse } from "@/lib/api";

export const recordsKeys = {
  all: ["records"] as const,
  list: (jobId: string, params?: { limit?: number; offset?: number }) =>
    [...recordsKeys.all, "list", jobId, params ?? {}] as const,
};

export function useRecords(
  jobId: string | null,
  params: { limit?: number; offset?: number } = { limit: 100 },
) {
  return useQuery<RecordListResponse, ApiError>({
    queryKey: recordsKeys.list(jobId ?? "", params),
    queryFn: () => {
      if (!jobId) throw new Error("Job id required");
      return api.jobs.records(jobId, params);
    },
    enabled: !!jobId,
  });
}
