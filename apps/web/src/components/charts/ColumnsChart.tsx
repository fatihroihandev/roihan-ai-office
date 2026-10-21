"use client";

import { useState } from "react";
import { compact, intTicks } from "@/lib/charts/math";
import { Tip, TipRow, type Series } from "@/components/charts/kit";

export type Column = { label: string; short: string; values: number[]; line?: number };

const W = 640;
const H = 220;
const M = { l: 38, r: 14, t: 12, b: 26 };

/**
 * Kolom bertumpuk (maks. 24 px, ujung data membulat 4 px, celah 2 px antar segmen) dengan garis opsional di satu sumbu yang sama.
 * Hover: garis bidik + tooltip untuk seluruh kolom; area sentuh seluas pita kolom (jauh lebih besar dari tandanya).
 */
export function ColumnsChart({ columns, series, line, lineLabel, lineColor, aria, fmt = (n: number) => compact(n), tipTitle }: {
  columns: Column[]; series: Series[]; line?: boolean; lineLabel?: string; lineColor?: string; aria: string; fmt?: (n: number) => string;
  tipTitle?: (c: Column) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = Math.max(1, columns.length);
  const totals = columns.map((c) => c.values.reduce((a, b) => a + b, 0));
  const maxVal = Math.max(1, ...totals, ...columns.map((c) => c.line ?? 0));
  const yt = intTicks(maxVal);
  const top = yt[yt.length - 1];
  const pw = W - M.l - M.r;
  const ph = H - M.t - M.b;
  const band = pw / n;
  const barW = Math.min(24, band * 0.62);
  const y = (v: number) => M.t + ph - (v / top) * ph;
  const cx = (i: number) => M.l + band * (i + 0.5);
  const every = Math.ceil(n / 7);
  const linePts = line ? columns.map((c, i) => `${cx(i)},${y(c.line ?? 0)}`).join(" ") : "";

  return (
    <div className="plot" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={aria} preserveAspectRatio="xMidYMid meet">
        {yt.map((v) => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="grid" />
            <text x={M.l - 6} y={y(v) + 3.5} textAnchor="end" className="axis">{compact(v)}</text>
          </g>
        ))}
        {hover !== null && <line x1={cx(hover)} x2={cx(hover)} y1={M.t} y2={M.t + ph} className="crosshair" />}
        {columns.map((c, i) => {
          let acc = 0;
          return (
            <g key={i}>
              {c.values.map((v, k) => {
                if (v <= 0) return null;
                const y1 = y(acc + v);
                const y0 = y(acc);
                acc += v;
                const isTop = acc === totals[i];
                const h = Math.max(0, y0 - y1 - 2); // celah 2 px antar segmen (warna permukaan)
                const r = isTop ? 4 : 0;
                const x = cx(i) - barW / 2;
                // sudut atas membulat 4 px hanya pada segmen teratas; dasar rata
                const path = isTop && h > r
                  ? `M${x},${y1 + h} V${y1 + r} Q${x},${y1} ${x + r},${y1} H${x + barW - r} Q${x + barW},${y1} ${x + barW},${y1 + r} V${y1 + h} Z`
                  : `M${x},${y1} H${x + barW} V${y1 + h} H${x} Z`;
                return <path key={k} d={path} fill={series[k].color} opacity={hover === null || hover === i ? 1 : 0.55} />;
              })}
              {i % every === 0 && <text x={cx(i)} y={H - 8} textAnchor="middle" className="axis">{c.short}</text>}
            </g>
          );
        })}
        {line && <polyline points={linePts} fill="none" stroke={lineColor} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />}
        {line && hover !== null && (
          <circle cx={cx(hover)} cy={y(columns[hover].line ?? 0)} r="4.5" fill={lineColor} stroke="var(--surface)" strokeWidth="2" />
        )}
        {columns.map((_, i) => (
          <rect key={i} x={M.l + band * i} y={M.t} width={band} height={ph} fill="transparent" onMouseEnter={() => setHover(i)} onMouseMove={() => setHover(i)}
            onFocus={() => setHover(i)} tabIndex={0} aria-label={`${columns[i].label}: ${columns[i].values.map((v, k) => `${series[k].label} ${v}`).join(", ")}`} />
        ))}
      </svg>
      {hover !== null && (
        <Tip x={Math.min(88, Math.max(12, (cx(hover) / W) * 100))} y={4}>
          <div className="tip-title">{tipTitle ? tipTitle(columns[hover]) : columns[hover].label}</div>
          {series.map((s, k) => <TipRow key={s.key} color={s.color} label={s.label} value={fmt(columns[hover].values[k])} />)}
          {line && <TipRow color={lineColor} label={lineLabel ?? ""} value={fmt(columns[hover].line ?? 0)} />}
        </Tip>
      )}
    </div>
  );
}
