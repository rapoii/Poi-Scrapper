"use client";

import { useEffect, useRef } from "react";

import { env } from "@/lib/env";
import type { WsEvent } from "@poi/shared";

export function useJobEvents(
  jobId: string | null,
  onEvent: (event: WsEvent) => void,
  onError?: () => void,
) {
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
    onErrorRef.current = onError;
  }, [onEvent, onError]);

  useEffect(() => {
    if (!jobId) return;

    const base = env.wsBaseUrl.replace(/\/$/, "");
    const ws = new WebSocket(`${base}/ws/jobs/${jobId}`);

    ws.onmessage = (message) => {
      try {
        onEventRef.current(JSON.parse(message.data as string) as WsEvent);
      } catch {
        // Ignore malformed dev-time frames.
      }
    };
    ws.onerror = () => {
      onErrorRef.current?.();
    };

    return () => {
      ws.close();
    };
  }, [jobId]);
}
