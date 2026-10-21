"use client";

import { useEffect, useRef, useState } from "react";
import { dashboardApi, type Dashboard } from "@/lib/dashboardApi";
import { shouldApply } from "@/lib/office/model";
import { useTaskEvents } from "@/lib/useTaskEvents";

const POLL_MS = 15_000; // status berbasis waktu (mis. "baru selesai" -> idle) berubah tanpa event; potret dimuat ulang berkala

/**
 * Memuat potret konsisten dari backend. Event WebSocket hanya MEMICU pemuatan ulang (tidak membawa keadaan),
 * jadi setelah reconnect tampilan otomatis sama dengan backend. Respons yang lebih lama tidak menimpa yang lebih baru.
 */
export function useOfficeData(): { data: Dashboard | null; stale: boolean; connected: boolean; updatedAt: number | null } {
  const [data, setData] = useState<Dashboard | null>(null);
  const [stale, setStale] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const tick = useRef<() => void>(() => undefined);

  useEffect(() => {
    let cancelled = false;
    let issued = 0;
    let applied = 0;
    const run = () => {
      const seq = ++issued;
      dashboardApi.get().then(
        (d) => {
          if (cancelled || !shouldApply(applied, seq)) return;
          applied = seq;
          setData(d);
          setStale(false);
          setUpdatedAt(Date.now());
        },
        () => {
          if (!cancelled) setStale(true); // tetap menampilkan potret terakhir, tetapi ditandai usang
        },
      );
    };
    tick.current = run;
    run();
    const id = setInterval(run, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const connected = useTaskEvents(() => tick.current());
  return { data, stale, connected, updatedAt };
}
