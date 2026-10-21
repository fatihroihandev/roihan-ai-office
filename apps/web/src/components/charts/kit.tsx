"use client";

import type { ReactNode } from "react";

export type Series = { key: string; label: string; color: string };

/** Kartu grafik: judul (nama grafik), subjudul (apa yang diukur), legenda (selalu ada untuk >= 2 seri), isi, dan tabel data. */
export function ChartCard({ title, subtitle, series, children, table, tableLabel, aside }: {
  title: string; subtitle?: string; series?: Series[]; children: ReactNode; table?: ReactNode; tableLabel: string; aside?: ReactNode;
}) {
  return (
    <section className="card chart">
      <header className="chart-head">
        <div>
          <h3>{title}</h3>
          {subtitle && <p className="small muted">{subtitle}</p>}
        </div>
        {aside}
      </header>
      {series && series.length >= 2 && (
        <ul className="legend">
          {series.map((s) => (
            <li key={s.key}><i style={{ background: s.color }} aria-hidden="true" />{s.label}</li>
          ))}
        </ul>
      )}
      {children}
      {table && (
        <details className="chart-table">
          <summary>{tableLabel}</summary>
          {table}
        </details>
      )}
    </section>
  );
}

/** Tooltip HTML di atas wadah chart; posisi dalam persen agar mengikuti lebar responsif. */
export function Tip({ x, y, children }: { x: number; y: number; children: ReactNode }) {
  return (
    <div className="tip" style={{ left: `${x}%`, top: `${y}%` }} role="status">
      {children}
    </div>
  );
}

export function TipRow({ color, label, value }: { color?: string; label: string; value: string }) {
  return (
    <div className="tip-row">
      {color ? <i style={{ background: color }} aria-hidden="true" /> : <i className="none" aria-hidden="true" />}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function EmptyNote({ text }: { text: string }) {
  return <p className="muted small chart-empty">{text}</p>;
}
