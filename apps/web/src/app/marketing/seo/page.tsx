"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHero } from "@/components/ui/PageHero";
import { ApiError, api, type Project } from "@/lib/api";
import { productsApi, type Product } from "@/lib/productsApi";
import { SEO_METRICS, seoApi, type Artifact, type Kpis } from "@/lib/seoApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const pct = (v: number | null) => (v === null ? null : `${(v * 100).toFixed(1)}%`);

export default function SeoPage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const unknown = t("seo.unknown");
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [items, setItems] = useState<Artifact[] | null>(null);
  const [open, setOpen] = useState<Artifact | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [url, setUrl] = useState("");
  const [html, setHtml] = useState("");
  const [robots, setRobots] = useState("");
  const [sitemap, setSitemap] = useState("");
  const [topic, setTopic] = useState("");
  const [material, setMaterial] = useState("");
  const [productId, setProductId] = useState("");
  const [metric, setMetric] = useState<string>("impressions");
  const [value, setValue] = useState("");
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));
  const [handoffProject, setHandoffProject] = useState("");

  const load = useCallback(() => {
    seoApi.kpis().then(setKpis, (e: Error) => setError(e.message));
    seoApi.artifacts().then(setItems, (e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
    api.listProjects().then(setProjects, () => undefined);
    productsApi.list().then(setProducts, () => undefined);
    const id = setInterval(load, 8000); // pekerjaan agent selesai di latar belakang
    return () => clearInterval(id);
  }, [load]);

  async function run(action: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(ok);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const k = kpis;
  const kpiCell = (name: string, v: string | number | null) => (
    <div className="kpi" key={name}><strong className={v === null ? "kpi-null" : undefined}>{v === null ? unknown : v}</strong><span>{name}</span></div>
  );

  return (
    <PageTransition>
<main data-accent="cyan">
      <p><Link href="/marketing">← {t("ext.back")}</Link></p>
      <PageHero
        code="04.2" route="SYS://SEO" art="marketing" title={t("seo.title")} hint={t("seo.hint")}
        stats={[
          { label: t("seo.stat.artifacts"), value: items?.length ?? 0 },
          { label: t("seo.stat.audits"), value: (items ?? []).filter((a) => a.kind === "audit").length },
          { label: t("seo.stat.clicks"), value: k?.organic.clicks ?? unknown, tone: k?.organic.clicks == null ? "warn" : "ok" },
        ]}
      />
      {error && <p className="bad" role="alert">{error}</p>}
      {notice && <p className="ok" role="status">{notice}</p>}

      <section className="card">
        <h3>{t("seo.kpi.title")}</h3>
        {!k ? <Loading /> : (
          <>
            <div className="kpis">
              {kpiCell(t("seo.kpi.impressions"), k.organic.impressions)}
              {kpiCell(t("seo.kpi.clicks"), k.organic.clicks)}
              {kpiCell("CTR", pct(k.organic.ctr))}
              {kpiCell(t("seo.kpi.position"), k.organic.avg_position)}
              {kpiCell(t("seo.kpi.sessions"), k.organic.organic_sessions)}
              {kpiCell(t("seo.kpi.conversions"), k.organic.page_conversions)}
              {kpiCell(t("seo.kpi.leads"), k.leads.total)}
              {kpiCell(t("seo.kpi.meeting"), pct(k.funnel.lead_to_meeting_rate))}
              {kpiCell(t("seo.kpi.win"), pct(k.funnel.win_rate))}
              {kpiCell("ROI", pct(k.money.roi))}
            </div>
            <ul className="small muted">{k.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          </>
        )}
        <form className="row" onSubmit={(e) => { e.preventDefault(); void run(async () => { await seoApi.metric({ metric, value: Number(value), period }); setValue(""); }, t("seo.metric.saved")); }}>
          <label>{t("seo.metric")}<select value={metric} onChange={(e) => setMetric(e.target.value)}>{SEO_METRICS.map((m) => <option key={m} value={m}>{label(`seo.kpi.${m}`)}</option>)}</select></label>
          <label>{t("seo.value")}<input type="number" min={0} step="any" value={value} onChange={(e) => setValue(e.target.value)} required /></label>
          <label>{t("seo.period")}<input value={period} pattern="\d{4}-\d{2}(-\d{2})?" onChange={(e) => setPeriod(e.target.value)} required /></label>
          <button type="submit" disabled={busy || value === ""}>{t("seo.metric.save")}</button>
        </form>
        <div className="actions"><button type="button" disabled={busy} onClick={() => void run(() => seoApi.analysis(), t("seo.queued"))}>{t("seo.analysis.run")}</button></div>
      </section>

      <div className="duo">
        <form className="card" onSubmit={(e) => { e.preventDefault(); void run(() => seoApi.audit({ url, html, robots_txt: robots, sitemap_xml: sitemap }), t("seo.queued")); }}>
          <h3>{t("seo.audit.title")}</h3>
          <p className="small muted">{t("seo.audit.hint")}</p>
          <label>URL<input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" /></label>
          <label>HTML<textarea rows={5} value={html} onChange={(e) => setHtml(e.target.value)} required /></label>
          <label>robots.txt<textarea rows={2} value={robots} onChange={(e) => setRobots(e.target.value)} /></label>
          <label>sitemap.xml<textarea rows={2} value={sitemap} onChange={(e) => setSitemap(e.target.value)} /></label>
          <button type="submit" disabled={busy || !html.trim()}>{t("seo.audit.run")}</button>
        </form>

        <form className="card" onSubmit={(e) => e.preventDefault()}>
          <h3>{t("seo.kw.title")}</h3>
          <p className="small muted">{t("seo.kw.hint")}</p>
          <label>{t("seo.topic")}<input value={topic} onChange={(e) => setTopic(e.target.value)} required minLength={2} /></label>
          <label>{t("seo.material")}<textarea rows={5} value={material} onChange={(e) => setMaterial(e.target.value)} /></label>
          <label>{t("seo.product")}<select value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">-</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <div className="actions">
            <button type="button" disabled={busy || topic.length < 2 || !material.trim()} onClick={() => void run(() => seoApi.keywords({ topic, material, product_id: productId || undefined }), t("seo.queued"))}>{t("seo.kw.run")}</button>
            <button type="button" disabled={busy || topic.length < 2} onClick={() => void run(() => seoApi.brief({ topic, material, product_id: productId || undefined }), t("seo.queued"))}>{t("seo.brief.run")}</button>
          </div>
        </form>
      </div>

      <section className="card">
        <h3>{t("seo.artifacts")}</h3>
        {!items ? <Loading /> : items.length === 0 ? <p className="muted">{t("seo.empty")}</p> : (
          <ul className="list">
            {items.map((a) => (
              <li key={a.id} className="card">
                <div>
                  <strong>{a.title}</strong> <span className="badge">{label(`seo.kind.${a.kind}`)}</span>
                  <p className="small muted">{a.summary}</p>
                </div>
                <button type="button" onClick={() => void seoApi.artifact(a.id).then(setOpen, (e: Error) => setError(e.message))}>{t("seo.open")}</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {open?.data && (
        <section className="card" aria-label={open.title}>
          <h3>{open.title}</h3>
          {open.kind === "audit" && (
            <>
              <p className="small">{t("seo.counts").replace("{c}", String(open.data.counts.critical)).replace("{w}", String(open.data.counts.warning)).replace("{i}", String(open.data.counts.info))}</p>
              <ul>{open.data.findings.map((f) => <li key={f.id}><span className="badge" data-risk={f.severity === "critical" ? "high" : f.severity === "warning" ? "medium" : undefined}>{label(`seo.sev.${f.severity}`)}</span> {f.message}{f.recommendation ? <span className="small muted"> → {f.recommendation}</span> : null}</li>)}</ul>
              <p className="small muted">{t("seo.notchecked")}: {open.data.not_checked.join("; ")}</p>
              {open.handed_off_to ? <p className="small ok">{t("seo.handed")}: <Link href={`/tasks/${open.handed_off_to}`}>{open.handed_off_to.slice(0, 8)}</Link></p> : (
                <div className="row">
                  <label>{t("seo.handoff.project")}<select value={handoffProject} onChange={(e) => setHandoffProject(e.target.value)}><option value="">-</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
                  <button type="button" disabled={busy || !handoffProject} onClick={() => void run(() => seoApi.handoff(open.id, handoffProject), t("seo.handoff.done"))}>{t("seo.handoff.run")}</button>
                </div>
              )}
            </>
          )}
          {open.kind === "keywords" && (
            <table><thead><tr><th>{t("seo.kw.keyword")}</th><th>{t("seo.kw.intent")}</th><th>{t("seo.kw.volume")}</th><th>{t("seo.kw.competition")}</th></tr></thead>
              <tbody>{(open.data.items ?? []).map((i) => <tr key={i.keyword}><td>{i.keyword}</td><td>{i.intent}</td><td>{i.volume ?? unknown}</td><td>{i.competition ?? unknown}</td></tr>)}</tbody></table>
          )}
          {open.kind === "brief" && (
            <>
              <p>{open.data.search_intent}</p>
              <ul>{(open.data.title_options ?? []).map((x) => <li key={x}>{x}</li>)}</ul>
              {(open.data.outline ?? []).map((o) => <div key={o.heading}><h4>{o.heading}</h4><ul>{o.points.map((p) => <li key={p}>{p}</li>)}</ul></div>)}
            </>
          )}
          {open.kind === "analysis" && <ul>{(open.data.observations ?? []).map((o) => <li key={o}>{o}</li>)}</ul>}
        </section>
      )}
    </main>
</PageTransition>
  );
}
