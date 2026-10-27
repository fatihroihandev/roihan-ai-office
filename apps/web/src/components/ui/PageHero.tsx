"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useLanguage } from "@/i18n/LanguageProvider";

export type Accent = "blue" | "cyan" | "violet" | "magenta" | "amber" | "teal";
export type Art = "projects" | "tasks" | "products" | "marketing" | "approvals" | "ai";
export type HeroStat = { label: string; value: number | string; tone?: "ok" | "warn" | "bad" };

/** Angka naik dari 0 ke nilai tujuan (dimatikan oleh preferensi gerak berkurang). Nilai berikutnya dianimasikan dari nilai sebelumnya. */
export function CountUp({ value }: { value: number | string }) {
  const numeric = typeof value === "number";
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (!numeric) return;
    let raf = 0;
    const start = performance.now();
    const a = from.current;
    const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const step = (now: number) => {
      const p = reduce ? 1 : Math.min(1, (now - start) / 700);
      const eased = 1 - (1 - p) ** 3;
      setShown(Math.round(a + (value - a) * eased));
      if (p < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, numeric]);
  return <>{numeric ? shown : value}</>;
}

/** Kepala halaman bersih: judul, petunjuk, ringkasan angka, dan aksi. (`code`, `route`, `art` dipertahankan agar pemanggil lama tetap valid, tetapi tidak ditampilkan.) */
export function PageHero({ title, hint, stats, actions }: {
  code?: string; route?: string; title: string; hint?: string; art?: Art; stats: HeroStat[]; actions?: ReactNode;
}) {
  const { t } = useLanguage();
  return (
    <section className="pagehero" aria-label={title}>
      <div className="pagehero-main">
        <h2>{title}</h2>
        {hint && <p className="pagehero-hint">{hint}</p>}
        {stats.length > 0 && (
          <ul className="pagehero-stats" aria-label={t("deck.title")}>
            {stats.map((s) => (
              <li key={s.label} data-tone={s.tone}>
                <strong><CountUp value={s.value} /></strong>
                <span>{s.label}</span>
              </li>
            ))}
          </ul>
        )}
        {actions && <div className="actions">{actions}</div>}
      </div>
    </section>
  );
}
/** Keadaan memuat: garis kerangka berkilau dan teks sinkronisasi. */
export function Loading({ lines = 3 }: { lines?: number }) {
  const { t } = useLanguage();
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="loading-text">{t("common.loading")}</span>
      {Array.from({ length: lines }, (_, i) => <div key={i} className="skeleton" style={{ width: `${88 - i * 14}%` }} />)}
    </div>
  );
}
