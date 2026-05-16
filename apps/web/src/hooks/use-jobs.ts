"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  api,
  type ApiError,
  type Job,
  type JobCreatePayload,
  type JobIntentUpdatePayload,
  type JobListResponse,
  type JobReparsePayload,
  type JobSourcesUpdatePayload,
} from "@/lib/api";

export const jobsKeys = {
  all: ["jobs"] as const,
  list: (params?: { limit?: number; offset?: number }) =>
    [...jobsKeys.all, "list", params ?? {}] as const,
  detail: (id: string) => [...jobsKeys.all, "detail", id] as const,
};

export function useJobs(params: { limit?: number; offset?: number } = { limit: 20 }) {
  return useQuery<JobListResponse, ApiError>({
    queryKey: jobsKeys.list(params),
    queryFn: () => api.jobs.list(params),
  });
}

export function useJob(id: string | null) {
  return useQuery<Job, ApiError>({
    queryKey: jobsKeys.detail(id ?? ""),
    queryFn: () => {
      if (!id) throw new Error("Job id required");
      return api.jobs.get(id);
    },
    enabled: !!id,
  });
}

export function useCreateJob() {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, JobCreatePayload>({
    mutationFn: (payload) => api.jobs.create(payload),
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: jobsKeys.all });
      qc.setQueryData(jobsKeys.detail(job.id), job);
    },
  });
}

export function useUpdateIntent(jobId: string) {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, JobIntentUpdatePayload>({
    mutationFn: (payload) => api.jobs.updateIntent(jobId, payload),
    onSuccess: (job) => {
      qc.setQueryData(jobsKeys.detail(job.id), job);
      qc.invalidateQueries({ queryKey: jobsKeys.all });
    },
  });
}

export function useReparseJob(jobId: string) {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, JobReparsePayload>({
    mutationFn: (payload) => api.jobs.reparse(jobId, payload),
    onSuccess: (job) => {
      qc.setQueryData(jobsKeys.detail(job.id), job);
      qc.invalidateQueries({ queryKey: jobsKeys.all });
    },
  });
}

export function useDiscoverSources(jobId: string) {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, void>({
    mutationFn: () => api.jobs.discoverSources(jobId),
    onSuccess: (job) => {
      qc.setQueryData(jobsKeys.detail(job.id), job);
      qc.invalidateQueries({ queryKey: jobsKeys.all });
    },
  });
}

export function useUpdateSources(jobId: string) {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, JobSourcesUpdatePayload>({
    mutationFn: (payload) => api.jobs.updateSources(jobId, payload),
    onSuccess: (job) => {
      qc.setQueryData(jobsKeys.detail(job.id), job);
      qc.invalidateQueries({ queryKey: jobsKeys.all });
    },
  });
}

export function useRunJob(jobId: string) {
  const qc = useQueryClient();
  return useMutation<Job, ApiError, void>({
    mutationFn: () => api.jobs.run(jobId),
    onSuccess: (job) => {
      qc.setQueryData(jobsKeys.detail(job.id), job);
      qc.invalidateQueries({ queryKey: jobsKeys.all });
    },
  });
}
