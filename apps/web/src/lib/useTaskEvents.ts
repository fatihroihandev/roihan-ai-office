"use client";

import { useEffect, useRef, useState } from "react";

const WS_BASE = process.env.NEXT_PUBLIC_API_WS_URL ?? "ws://127.0.0.1:8000";

/**
 * Berlangganan event backend lewat WebSocket.
 *
 * - Token lokal tidak masuk browser: klien meminta tiket sekali-pakai lewat proxy server.
 * - `onChange` dipanggil saat (re)connect dan setiap event. Backend adalah sumber kebenaran, jadi
 *   pemanggil cukup memuat ulang state dari API dan tidak mengandalkan isi event (yang mungkin terlewat).
 * - Reconnect otomatis dengan backoff. Mengembalikan status koneksi.
 */
export function useTaskEvents(onChange: () => void): boolean {
  const [connected, setConnected] = useState(false);
  const callback = useRef(onChange);

  useEffect(() => {
    callback.current = onChange;
  });

  useEffect(() => {
    let socket: WebSocket | null = null;
    let stopped = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function scheduleReconnect() {
      if (stopped) return;
      attempts += 1;
      timer = setTimeout(connect, Math.min(15000, 1000 * 2 ** Math.min(attempts, 4)));
    }

    async function connect() {
      try {
        const res = await fetch("/api/events/ticket", { method: "POST", cache: "no-store" });
        if (!res.ok) throw new Error(String(res.status));
        const { ticket } = (await res.json()) as { ticket: string };
        if (stopped) return;
        socket = new WebSocket(`${WS_BASE}/api/ws?ticket=${encodeURIComponent(ticket)}`);
        socket.onopen = () => {
          attempts = 0;
          setConnected(true);
          callback.current();
        };
        socket.onmessage = (m) => {
          const data = JSON.parse(String(m.data)) as { type?: string };
          if (data.type !== "hello") callback.current();
        };
        socket.onclose = () => {
          setConnected(false);
          scheduleReconnect();
        };
        socket.onerror = () => socket?.close();
      } catch {
        setConnected(false);
        scheduleReconnect();
      }
    }

    timer = setTimeout(connect, 0);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return connected;
}
