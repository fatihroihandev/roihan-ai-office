"use client";

import Link from "next/link";
import type { Dashboard } from "@/lib/dashboardApi";
import type { Insights } from "@/lib/insightsApi";
import { ago, compact, parseUtc, pct, stepRates } from "@/lib/charts/math";
import { ChartCard, EmptyNote, type Series } from "@/components/charts/kit";
import { ColumnsChart, type Column } from "@/components/charts/ColumnsChart";
import { HBars, type HRow } from "@/components/charts/HBars";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

// Warna status = peran, bukan urutan (lolos validasi palet: pita lightness, chroma, CVD, kontras pada permukaan gelap).
const C = { done: "var(--c-done)", run: "var(--c-run)", queue: "var(--c-queue)", warn: "var(--c-warn)", bad: "var(--c-bad)" };

function Gauge({ value, label, unknown }: { value: number | null; label: string; unknown: string }) {
  const r = 38;
  const len = 2 * Math.PI * r;
  const v = value ?? 0;
  return (
    <svg viewBox="0 0 100 100" className="gauge" role="img" aria-label={`${label}: ${value === null ? unknown : pct(value)}`}>
      <circle cx="50" cy="50" r={r} className="gauge-track" />
      {value !== null && (
        <circle cx="50" cy="50" r={r} className="gauge-fill" strokeDasharray={`${len * v} ${len}`} transform="rotate(-90 50 50)" strokeLinecap="round" />
      )}
      <text x="50" y="55" textAnchor="middle" className="gauge-text">{value === null ? "—" : pct(value)}</text>
    </svg>
  );
}

export function CommandDeck({ d, ins }: { d: Dashboard; ins: Insights | null }) {
  const { t, lang } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const fill = (key: string, params: Record<string, string | number>) => Object.entries(params).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), label(key));
  const tableLabel = t("chart.table");

  // ---- peta status task (selalu tersedia dari potret dashboard)
  const c = d.tasks;
  const pipeSeries: Series[] = [
    { key: "completed", label: t("series.completed"), color: C.done },
    { key: "running", label: t("series.running"), color: C.run },
    { key: "queued", label: t("series.queued"), color: C.queue },
    { key: "blocked", label: t("series.blocked"), color: C.warn },
    { key: "failed", label: t("series.failed"), color: C.bad },
  ];
  const queued = (c.draft ?? 0) + (c.queued ?? 0) + (c.pending_approval ?? 0);
  const pipeRow: HRow = {
    id: "all", label: t("chart.col.total"),
    values: [c.completed ?? 0, c.running ?? 0, queued, (c.blocked ?? 0) + (c.interrupted ?? 0), c.failed ?? 0],
  };
  const pipeTotal = pipeRow.values.reduce((a, b) => a + b, 0);

  const loading = <EmptyNote text={t("common.loading")} />;
  const empty = <EmptyNote text={t("chart.empty")} />;

  // ---- grafik dari /insights
  const flowSeries: Series[] = [{ key: "completed", label: t("series.completed"), color: C.done }, { key: "failed", label: t("series.failed"), color: C.bad }];
  const flowCols: Column[] = (ins?.throughput ?? []).map((x) => ({
    label: x.date, short: x.date.slice(8), values: [x.completed, x.failed], line: x.created,
  }));
  const flowActive = flowCols.some((x) => x.values[0] + x.values[1] + (x.line ?? 0) > 0);

  const projSeries = pipeSeries;
  const projRows: HRow[] = (ins?.projects ?? []).map((p) => ({
    id: p.id, label: p.name, sub: p.current ?? undefined,
    values: [p.counts.completed ?? 0, p.counts.running ?? 0, (p.counts.draft ?? 0) + (p.counts.queued ?? 0) + (p.counts.pending_approval ?? 0), (p.counts.blocked ?? 0) + (p.counts.interrupted ?? 0), p.counts.failed ?? 0],
    end: p.percent === null ? "—" : `${p.percent}%`,
  }));

  const loadSeries: Series[] = [
    { key: "running", label: t("series.running"), color: C.run },
    { key: "queued", label: t("series.queued"), color: C.queue },
    { key: "blocked", label: t("series.blocked"), color: C.warn },
    { key: "completed7", label: t("series.completed7"), color: C.done },
    { key: "failed7", label: t("series.failed7"), color: C.bad },
  ];
  const loadRows: HRow[] = (ins?.workload ?? []).map((w) => ({ id: w.role, label: label(`role.${w.role}`), values: [w.running, w.queued, w.blocked, w.completed_7d, w.failed_7d] }));

  const aiSeries: Series[] = [{ key: "ok", label: t("series.ok"), color: C.run }, { key: "error", label: t("series.error"), color: C.bad }];
  const aiCols: Column[] = (ins?.ai_hourly ?? []).map((h) => {
    const hh = h.hour.slice(11, 13);
    return { label: `${hh}:00 · ${fill("chart.tokens", { n: compact(h.tokens, lang) })}`, short: hh, values: [h.calls - h.errors, h.errors] };
  });
  const aiActive = aiCols.some((x) => x.values[0] + x.values[1] > 0);

  const stages = ins?.funnel.stages ?? [];
  const rates = stepRates(stages.map((s) => s.reached));
  const funnelRows: HRow[] = stages.map((s, i) => ({
    id: s.stage, label: label(`mkt.status.${s.stage}`), values: [s.reached],
    end: rates[i] === null ? String(s.reached) : `${s.reached} · ${Math.round((rates[i] ?? 0) * 100)}%`,
  }));
  const funnelActive = stages.some((s) => s.reached > 0);

  const q = ins?.quality;
  const now = parseUtc(d.generated_at); // waktu server: murni dan konsisten

  return (
    <section aria-label={t("deck.title")} className="deck">
      <div className="deck-head">
        <h3 className="section-title">{t("deck.title")}</h3>
        <p className="muted small">{t("deck.sub")}</p>
      </div>

      <div className="deckgrid">
        <ChartCard title={t("chart.pipeline.title")} subtitle={t("chart.pipeline.sub")} series={pipeSeries} tableLabel={tableLabel}
          table={<table><tbody>{pipeSeries.map((s, i) => <tr key={s.key}><td>{s.label}</td><td>{pipeRow.values[i]}</td></tr>)}</tbody></table>}>
          {pipeTotal === 0 ? empty : <HBars rows={[{ ...pipeRow, end: String(pipeTotal) }]} series={pipeSeries} aria={t("chart.pipeline.title")} />}
        </ChartCard>

        <ChartCard title={t("chart.quality.title")} subtitle={t("chart.quality.sub")} tableLabel={tableLabel}>
          {!q ? loading : (
            <div className="quality">
              <div>
                <Gauge value={q.success_rate_7d} label={t("chart.quality.rate")} unknown={t("chart.quality.unknown")} />
                <span className="small muted">{t("chart.quality.rate")}</span>
              </div>
              <dl>
                <dt>{t("chart.quality.avg")}</dt>
                <dd>{q.avg_minutes === null ? t("chart.quality.unknown") : fill("chart.quality.min", { n: String(q.avg_minutes).replace(".", lang === "id" ? "," : ".") })}</dd>
                <dt>{t("chart.quality.count")}</dt>
                <dd>{q.finished_7d}</dd>
              </dl>
            </div>
          )}
        </ChartCard>

        <ChartCard title={t("chart.flow.title")} subtitle={fill("chart.flow.sub", { n: ins?.days ?? 14 })} series={[...flowSeries, { key: "created", label: t("series.created"), color: C.run }]}
          tableLabel={tableLabel}
          table={<table><thead><tr><th>{t("chart.col.date")}</th><th>{t("series.created")}</th><th>{t("series.completed")}</th><th>{t("series.failed")}</th></tr></thead>
            <tbody>{(ins?.throughput ?? []).map((x) => <tr key={x.date}><td>{x.date}</td><td>{x.created}</td><td>{x.completed}</td><td>{x.failed}</td></tr>)}</tbody></table>}>
          {!ins ? loading : !flowActive ? empty : (
            <ColumnsChart columns={flowCols} series={flowSeries} line lineLabel={t("series.created")} lineColor={C.run} aria={t("chart.flow.title")} />
          )}
        </ChartCard>

        <ChartCard title={t("chart.projects.title")} subtitle={t("chart.projects.sub")} series={projSeries} tableLabel={tableLabel}
          table={<table><thead><tr><th>{t("chart.col.name")}</th><th>%</th><th>{t("chart.col.total")}</th></tr></thead>
            <tbody>{(ins?.projects ?? []).map((p) => <tr key={p.id}><td>{p.name}</td><td>{p.percent ?? "—"}</td><td>{p.total}</td></tr>)}</tbody></table>}>
          {!ins ? loading : projRows.length === 0 ? empty : <HBars rows={projRows} series={projSeries} aria={t("chart.projects.title")} />}
        </ChartCard>

        <ChartCard title={t("chart.workload.title")} subtitle={t("chart.workload.sub")} series={loadSeries} tableLabel={tableLabel}
          table={<table><thead><tr><th>{t("chart.col.name")}</th>{loadSeries.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
            <tbody>{loadRows.map((r) => <tr key={r.id}><td>{r.label}</td>{r.values.map((v, i) => <td key={i}>{v}</td>)}</tr>)}</tbody></table>}>
          {!ins ? loading : <HBars rows={loadRows} series={loadSeries} aria={t("chart.workload.title")} />}
        </ChartCard>

        <ChartCard title={t("chart.ai.title")} subtitle={t("chart.ai.sub")} series={aiSeries} tableLabel={tableLabel}
          aside={<span className="badge" data-task={d.ai.paid_calls_24h > 0 ? "failed" : "completed"}>{d.ai.paid_calls_24h > 0 ? t("office.ai.paidOn") : t("office.ai.paidOff")}</span>}
          table={<table><thead><tr><th>{t("chart.col.date")}</th><th>{t("series.ok")}</th><th>{t("series.error")}</th></tr></thead>
            <tbody>{aiCols.map((x, i) => <tr key={i}><td>{x.label}</td><td>{x.values[0]}</td><td>{x.values[1]}</td></tr>)}</tbody></table>}>
          {!ins ? loading : !aiActive ? empty : <ColumnsChart columns={aiCols} series={aiSeries} aria={t("chart.ai.title")} tipTitle={(x) => x.label} />}
        </ChartCard>

        <ChartCard title={t("chart.funnel.title")} subtitle={t("chart.funnel.sub")} tableLabel={tableLabel}
          table={<table><thead><tr><th>{t("chart.col.stage")}</th><th>{t("series.reached")}</th><th>{t("chart.col.rate")}</th></tr></thead>
            <tbody>{stages.map((s, i) => <tr key={s.stage}><td>{label(`mkt.status.${s.stage}`)}</td><td>{s.reached}</td><td>{pct(rates[i]) ?? "—"}</td></tr>)}</tbody></table>}
          aside={<Link className="small" href="/marketing">{t("nav.marketing")}</Link>}>
          {!ins ? loading : !funnelActive ? empty : (
            <>
              <HBars rows={funnelRows} series={[{ key: "reached", label: t("series.reached"), color: C.queue }]} aria={t("chart.funnel.title")} />
              <p className="small muted">{fill("chart.funnel.out", { l: ins.funnel.out.lost ?? 0, d: ins.funnel.out.disqualified ?? 0, n: ins.funnel.out.do_not_contact ?? 0 })}</p>
            </>
          )}
        </ChartCard>

        <ChartCard title={t("chart.activity.title")} subtitle={t("chart.activity.sub")} tableLabel={tableLabel}>
          {!ins ? loading : ins.activity.length === 0 ? <EmptyNote text={t("chart.activity.empty")} /> : (
            <ol className="trail">
              {ins.activity.slice(0, 10).map((e) => (
                <li key={e.seq} data-to={e.to_status ?? e.type}>
                  <i aria-hidden="true" />
                  <div>
                    <Link href={`/tasks/${e.task_id}`}>{e.title ?? e.task_id.slice(0, 8)}</Link>
                    <span className="small muted">
                      {" "}{e.to_status ? label(`status.task.${e.to_status}`) : e.type}{e.role ? ` · ${label(`role.${e.role}`)}` : ""}{e.project ? ` · ${e.project}` : ""} · {ago(e.at, now, lang)}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </ChartCard>
      </div>
    </section>
  );
}
