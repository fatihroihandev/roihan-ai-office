"use client";

import { useState } from "react";
import { Tip, TipRow, type Series } from "@/components/charts/kit";

export type HRow = { id: string; label: string; sub?: string; values: number[]; end?: string };

const W = 640;
const LABEL_W = 168;
const END_W = 96;
const ROW = 30;
const BAR = 14;

/**
 * Batang horizontal bertumpuk: satu baris per entitas, tebal 14 px, celah 2 px antar segmen, ujung kanan membulat 4 px.
 * Nilai/ucapan akhir ditulis DI LUAR batang (di ujungnya) sehingga tidak pernah terpotong.
 */
export function HBars({ rows, series, aria, max }: { rows: HRow[]; series: Series[]; aria: string; max?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const totals = rows.map((r) => r.values.reduce((a, b) => a + b, 0));
  const scale = max ?? Math.max(1, ...totals);
  const plotW = W - LABEL_W - END_W;
  const H = rows.length * ROW + 4;

  return (
    <div className="plot" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={aria} preserveAspectRatio="xMidYMid meet">
        <line x1={LABEL_W} x2={LABEL_W} y1={0} y2={H} className="grid" />
        {rows.map((r, i) => {
          const cy = i * ROW + ROW / 2;
          let acc = 0;
          const lastIdx = r.values.reduce((a, v, k) => (v > 0 ? k : a), -1);
          return (
            <g key={r.id} opacity={hover === null || hover === i ? 1 : 0.6}>
              <text x={LABEL_W - 10} y={cy - (r.sub ? 2 : -3.5)} textAnchor="end" className="label">{r.label.length > 24 ? `${r.label.slice(0, 23)}…` : r.label}</text>
              {r.sub && <text x={LABEL_W - 10} y={cy + 10} textAnchor="end" className="axis">{r.sub.length > 30 ? `${r.sub.slice(0, 29)}…` : r.sub}</text>}
              {r.values.map((v, k) => {
                if (v <= 0) return null;
                const x0 = LABEL_W + (acc / scale) * plotW;
                const w = Math.max(0, (v / scale) * plotW - 2); // celah 2 px
                acc += v;
                const rr = k === lastIdx ? 4 : 0;
                const y0 = cy - BAR / 2;
                const path = rr && w > rr * 2
                  ? `M${x0},${y0} H${x0 + w - rr} Q${x0 + w},${y0} ${x0 + w},${y0 + rr} V${y0 + BAR - rr} Q${x0 + w},${y0 + BAR} ${x0 + w - rr},${y0 + BAR} H${x0} Z`
                  : `M${x0},${y0} H${x0 + w} V${y0 + BAR} H${x0} Z`;
                return <path key={k} d={path} fill={series[k].color} />;
              })}
              <text x={LABEL_W + (totals[i] / scale) * plotW + 8} y={cy + 4} className="value">{r.end ?? totals[i]}</text>
              <rect x={0} y={i * ROW} width={W} height={ROW} fill="transparent" onMouseEnter={() => setHover(i)} onMouseMove={() => setHover(i)}
                onFocus={() => setHover(i)} tabIndex={0} aria-label={`${r.label}: ${r.values.map((v, k) => `${series[k].label} ${v}`).join(", ")}`} />
            </g>
          );
        })}
      </svg>
      {hover !== null && (
        <Tip x={70} y={Math.min(80, (hover * ROW) / H * 100)}>
          <div className="tip-title">{rows[hover].label}</div>
          {series.map((s, k) => rows[hover].values[k] > 0 && <TipRow key={s.key} color={s.color} label={s.label} value={String(rows[hover].values[k])} />)}
        </Tip>
      )}
    </div>
  );
}
