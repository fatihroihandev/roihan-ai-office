"use client";

import { useEffect, useRef, useState } from "react";
import { insightsApi, type Insights } from "@/lib/insightsApi";

const POLL_MS = 30_000;
const MIN_GAP_MS = 4_000; // event beruntun tidak membanjiri backend

/** Data grafik. `stamp` berubah setiap potret dashboard diperbarui (event WebSocket atau polling); pemuatan dibatasi agar tidak berlebihan. */
export function useInsights(stamp: string | null): Insights | null {
  const [data, setData] = useState<Insights | null>(null);
  const last = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const run = () => {
      last.current = Date.now();
      insightsApi.get().then(
        (d) => !cancelled && setData(d),
        () => undefined, // tetap menampilkan data terakhir
      );
    };
    if (Date.now() - last.current >= MIN_GAP_MS) run();
    const id = setInterval(run, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [stamp]);

  return data;
}
