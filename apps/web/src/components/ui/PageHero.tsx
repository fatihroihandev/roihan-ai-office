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

/** Ilustrasi SVG beranimasi tiap halaman (CSS murni: berhenti otomatis saat gerak berkurang diminta). */
function PageArt({ art }: { art: Art }) {
  switch (art) {
    case "projects":
      return (
        <svg viewBox="0 0 240 180" className="art" aria-hidden="true">
          <g className="art-blueprint">
            {[0, 1, 2].map((i) => (
              <g key={i} style={{ animationDelay: `${i * 0.5}s` }} className="art-layer">
                <polygon points={`120,${40 + i * 32} 200,${72 + i * 32} 120,${104 + i * 32} 40,${72 + i * 32}`} />
                <line x1="40" y1={72 + i * 32} x2="40" y2={92 + i * 32} /><line x1="200" y1={72 + i * 32} x2="200" y2={92 + i * 32} /><line x1="120" y1={104 + i * 32} x2="120" y2={124 + i * 32} />
              </g>
            ))}
          </g>
          <circle className="art-dot" cx="120" cy="22" r="4" />
        </svg>
      );
    case "tasks":
      return (
        <svg viewBox="0 0 240 180" className="art" aria-hidden="true">
          <path id="lane" className="art-path" d="M10 150 H70 V90 H130 V50 H230" fill="none" />
          <path className="art-path faint" d="M10 120 H40 V60 H100 V120 H170 V150 H230" fill="none" />
          {[0, 1, 2, 3].map((i) => (
            <circle key={i} r="5" className="art-runner" style={{ animationDelay: `${i * -1.1}s` }}>
              <animateMotion dur="4.4s" begin={`${i * -1.1}s`} repeatCount="indefinite" path="M10 150 H70 V90 H130 V50 H230" />
            </circle>
          ))}
          {[70, 130, 230].map((x, i) => <rect key={x} x={x - 7} y={[150, 90, 50][i] - 7} width="14" height="14" className="art-node" />)}
        </svg>
      );
    case "products":
      return (
        <div className="art cube-wrap" aria-hidden="true">
          <div className="cube">
            {["f", "b", "l", "r", "t", "u"].map((f) => <span key={f} className={`face ${f}`} />)}
          </div>
          <div className="cube small">
            {["f", "b", "l", "r", "t", "u"].map((f) => <span key={f} className={`face ${f}`} />)}
          </div>
        </div>
      );
    case "marketing":
      return (
        <svg viewBox="0 0 240 180" className="art" aria-hidden="true">
          {[24, 48, 72].map((r) => <circle key={r} cx="120" cy="90" r={r} className="art-ring" />)}
          <line x1="120" y1="12" x2="120" y2="168" className="art-ring" /><line x1="42" y1="90" x2="198" y2="90" className="art-ring" />
          <g className="art-sweep"><path d="M120 90 L120 18 A72 72 0 0 1 182 54 Z" /></g>
          {[[150, 60], [92, 112], [170, 112], [104, 56]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="3.5" className="art-blip" style={{ animationDelay: `${i * 0.8}s` }} />)}
        </svg>
      );
    case "approvals":
      return (
        <svg viewBox="0 0 240 180" className="art" aria-hidden="true">
          <circle cx="120" cy="90" r="64" className="art-ring dashed spin-slow" />
          <circle cx="120" cy="90" r="48" className="art-ring dashed spin-rev" />
          <circle cx="120" cy="90" r="30" className="art-core" />
          <path d="M108 92 l9 9 l17 -20" className="art-check" fill="none" />
          {[0, 90, 180, 270].map((a) => <rect key={a} x="116" y="14" width="8" height="14" className="art-gate" transform={`rotate(${a} 120 90)`} />)}
        </svg>
      );
    case "ai":
      return (
        <svg viewBox="0 0 240 180" className="art" aria-hidden="true">
          {[[30, 40], [30, 90], [30, 140], [120, 25], [120, 70], [120, 115], [120, 160], [210, 60], [210, 120]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r="6" className="art-neuron" style={{ animationDelay: `${(i % 5) * 0.35}s` }} />)}
          {[[30, 40, 120, 25], [30, 40, 120, 70], [30, 90, 120, 70], [30, 90, 120, 115], [30, 140, 120, 115], [30, 140, 120, 160], [120, 25, 210, 60], [120, 70, 210, 60], [120, 115, 210, 120], [120, 160, 210, 120], [120, 70, 210, 120]].map(([a, b, c, d], i) => (
            <line key={i} x1={a} y1={b} x2={c} y2={d} className="art-synapse" style={{ animationDelay: `${i * 0.25}s` }} />
          ))}
        </svg>
      );
  }
}

/** Kepala halaman bergaya HUD: kode rute, judul glitch, petunjuk, statistik hidup, dan ilustrasi beranimasi. */
export function PageHero({ code, route, title, hint, art, stats, actions }: {
  code: string; route: string; title: string; hint?: string; art: Art; stats: HeroStat[]; actions?: ReactNode;
}) {
  const { t } = useLanguage();
  return (
    <section className="pagehero" aria-label={title}>
      <div className="pagehero-main">
        <p className="pagehero-route"><span>{code}</span> {route}<i aria-hidden="true" /></p>
        <h2><span className="glitch" data-text={title}>{title}</span></h2>
        {hint && <p className="pagehero-hint">{hint}</p>}
        {stats.length > 0 && (
          <ul className="pagehero-stats" aria-label={t("deck.title")}>
            {stats.map((s, i) => (
              <li key={s.label} data-tone={s.tone} style={{ animationDelay: `${0.15 + i * 0.08}s` }}>
                <strong><CountUp value={s.value} /></strong>
                <span>{s.label}</span>
              </li>
            ))}
          </ul>
        )}
        {actions && <div className="actions">{actions}</div>}
      </div>
      <div className="pagehero-art"><PageArt art={art} /></div>
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
