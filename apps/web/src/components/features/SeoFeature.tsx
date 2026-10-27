"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHero } from "@/components/ui/PageHero";
import { ApiError, api, type Project } from "@/lib/api";
import { productsApi, type Product } from "@/lib/productsApi";
import { SEO_METRICS, seoApi, type Artifact, type Kpis, type SeoCampaign, type SiteInfo } from "@/lib/seoApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const pct = (v: number | null) => (v === null ? null : `${(v * 100).toFixed(1)}%`);

export function SeoFeature() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const unknown = t("seo.unknown");
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [items, setItems] = useState<Artifact[] | null>(null);
  const [open, setOpen] = useState<Artifact | null>(null);
  const [siteList, setSiteList] = useState<SiteInfo[]>([]);
  const [campaigns, setCampaigns] = useState<SeoCampaign[] | null>(null);
  const [siteId, setSiteId] = useState("");
  const [siteDetail, setSiteDetail] = useState<SiteInfo | null>(null);
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
  const [campaignName, setCampaignName] = useState("");
  const [campaignUrl, setCampaignUrl] = useState("");
  const [campaignSiteId, setCampaignSiteId] = useState("");
  const [campaignKeywords, setCampaignKeywords] = useState("");
  const [campaignObjective, setCampaignObjective] = useState<SeoCampaign["objective"]>("organic_traffic");
  const [campaignBudget, setCampaignBudget] = useState("0");
  const [campaignExternalBudget, setCampaignExternalBudget] = useState("0");
  const [campaignTarget, setCampaignTarget] = useState("");
  const [campaignBaseline, setCampaignBaseline] = useState("");
  const [campaignBaselineSource, setCampaignBaselineSource] = useState("");
  const [campaignCountry, setCampaignCountry] = useState("");
  const [campaignLanguage, setCampaignLanguage] = useState("");
  const [campaignLocation, setCampaignLocation] = useState("");
  const [campaignStart, setCampaignStart] = useState("");
  const [campaignReview, setCampaignReview] = useState("");
  const [campaignKeywordDraft, setCampaignKeywordDraft] = useState("");
  const [campaignMaterial, setCampaignMaterial] = useState("");
  const [selectedCampaignKeywords, setSelectedCampaignKeywords] = useState<Record<string, string[]>>({});

  const load = useCallback(() => {
    seoApi.kpis().then(setKpis, (e: Error) => setError(e.message));
    seoApi.artifacts().then(setItems, (e: Error) => setError(e.message));
    seoApi.sites().then(setSiteList, () => undefined);
    seoApi.campaigns().then(setCampaigns, (e: Error) => setError(e.message));
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
  async function refreshCampaign(id?: string) {
    const rows = await seoApi.campaigns();
    setCampaigns(rows);
    if (id) {
      const updated = await seoApi.campaign(id);
      setCampaigns((prev) => (prev ?? rows).map((c) => c.id === id ? updated : c));
    }
  }
  const campaignStatusLabel = (status: SeoCampaign["status"]) => label(`seo.campaign.status.${status}`);
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
        <h3>{t("seo.campaign.title")}</h3>
        <p className="small muted">{t("seo.campaign.hint")}</p>
        <form className="grid2" onSubmit={(e) => { e.preventDefault(); void run(async () => {
          const created = await seoApi.createCampaign({ name: campaignName, website_url: campaignUrl, site_id: campaignSiteId || undefined,
            primary_keywords: campaignKeywords.split(/[\n,]/).map((x) => x.trim()).filter(Boolean), objective: campaignObjective,
            target_country: campaignCountry || undefined, target_language: campaignLanguage || undefined, target_location: campaignLocation || undefined,
            target_value: campaignTarget === "" ? undefined : Number(campaignTarget), baseline: campaignBaseline === "" ? {} : { [campaignObjective]: Number(campaignBaseline) },
            baseline_source: campaignBaseline === "" ? "not_provided" : campaignBaselineSource.trim() || "user_entered_source_unspecified",
            starts_on: campaignStart ? new Date(`${campaignStart}T00:00:00Z`).toISOString() : undefined,
            review_on: campaignReview ? new Date(`${campaignReview}T00:00:00Z`).toISOString() : undefined,
            api_budget_idr: Number(campaignBudget) || 0, external_budget_idr: Number(campaignExternalBudget) || 0, autonomy: "read_only" });
          setCampaignName(""); setCampaignUrl(""); setCampaignKeywords(""); setCampaignBudget("0"); setCampaignTarget(""); setCampaignBaseline(""); setCampaignBaselineSource(""); setCampaignExternalBudget("0"); await refreshCampaign(created.id);
        }, t("seo.campaign.created")); }}>
          <label>{t("seo.campaign.name")}<input value={campaignName} onChange={(e) => setCampaignName(e.target.value)} required maxLength={160} /></label>
          <label>{t("seo.campaign.website")}<input type="url" value={campaignUrl} onChange={(e) => setCampaignUrl(e.target.value)} placeholder="https://example.com" required /></label>
          <label>{t("seo.campaign.site")}
            <select value={campaignSiteId} onChange={(e) => { const next = e.target.value; setCampaignSiteId(next); const site = siteList.find((s) => s.id === next); if (site) setCampaignUrl(site.url); }}>
              <option value="">{t("seo.campaign.externalSite")}</option>{siteList.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.url}</option>)}
            </select>
          </label>
          <label>{t("seo.campaign.objective")}<select value={campaignObjective} onChange={(e) => setCampaignObjective(e.target.value as SeoCampaign["objective"])}>
            {(["keyword_rank", "organic_traffic", "clicks", "leads", "conversions"] as const).map((x) => <option key={x} value={x}>{t(`seo.campaign.objective.${x}` as MessageKey)}</option>)}
          </select></label>
          <label>{t("seo.campaign.targetCountry")}<input value={campaignCountry} onChange={(e) => setCampaignCountry(e.target.value)} maxLength={80} /></label>
          <label>{t("seo.campaign.targetLanguage")}<input value={campaignLanguage} onChange={(e) => setCampaignLanguage(e.target.value)} maxLength={40} /></label>
          <label>{t("seo.campaign.targetLocation")}<input value={campaignLocation} onChange={(e) => setCampaignLocation(e.target.value)} maxLength={160} /></label>
          <label>{t("seo.campaign.targetValue")}<input type="number" min={0} step="any" value={campaignTarget} onChange={(e) => setCampaignTarget(e.target.value)} /></label>
          <label>{t("seo.campaign.baseline")}<input type="number" min={0} step="any" value={campaignBaseline} onChange={(e) => setCampaignBaseline(e.target.value)} /></label>
          <label>{t("seo.campaign.baselineSource")}<input value={campaignBaselineSource} onChange={(e) => setCampaignBaselineSource(e.target.value)} maxLength={500} placeholder={t("seo.campaign.baselineSourceHint")} /></label>
          <label>{t("seo.campaign.startDate")}<input type="date" value={campaignStart} onChange={(e) => setCampaignStart(e.target.value)} /></label>
          <label>{t("seo.campaign.reviewDate")}<input type="date" value={campaignReview} onChange={(e) => setCampaignReview(e.target.value)} /></label>
          <label>{t("seo.campaign.keywords")}<textarea rows={2} value={campaignKeywords} onChange={(e) => setCampaignKeywords(e.target.value)} placeholder={t("seo.campaign.keywordsPlaceholder")} /></label>
          <label>{t("seo.campaign.apiBudget")}<input type="number" min={0} step={1000} value={campaignBudget} onChange={(e) => setCampaignBudget(e.target.value)} /></label>
          <label>{t("seo.campaign.externalBudget")}<input type="number" min={0} step={1000} value={campaignExternalBudget} onChange={(e) => setCampaignExternalBudget(e.target.value)} /></label>
          <p className="small muted">{t("seo.campaign.readOnlyDefault")}</p>
          <button type="submit" disabled={busy || !campaignName.trim() || !campaignUrl.trim()}>{t("seo.campaign.create")}</button>
        </form>
        {!campaigns ? <Loading /> : campaigns.length === 0 ? <p className="small muted">{t("seo.campaign.empty")}</p> : (
          <ul className="list">
            {campaigns.map((c) => (
              <li key={c.id} className="card">
                <div>
                  <strong>{c.name}</strong> <span className="badge">{campaignStatusLabel(c.status)}</span>
                  <p><a href={c.website_url} target="_blank" rel="noopener noreferrer">{c.website_url}</a> · {t(`seo.campaign.objective.${c.objective}` as MessageKey)}</p>
                  <p className="small muted">{t("seo.campaign.baseline")}: {Object.entries(c.baseline).map(([key, val]) => `${key}=${val ?? unknown}`).join(", ") || unknown} · {t("seo.campaign.baselineSource")}: {c.baseline_source}</p>
                  <p className="small muted">{t("seo.campaign.allowedDomain")}: {c.allowed_domains.join(", ")} · {t("seo.campaign.integrationsNotConnected")}</p>
                  <div className="row">
                    {c.status === "draft" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.updateCampaignStatus(c.id, "planning"); await refreshCampaign(c.id); }, t("seo.campaign.updated"))}>{t("seo.campaign.plan")}</button>}
                    {c.status === "auditing" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.updateCampaignStatus(c.id, "planning"); await refreshCampaign(c.id); }, t("seo.campaign.updated"))}>{t("seo.campaign.auditReviewed")}</button>}
                    {c.status === "planning" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.updateCampaignStatus(c.id, "active"); await refreshCampaign(c.id); }, t("seo.campaign.updated"))}>{t("seo.campaign.start")}</button>}
                    {c.status === "active" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.updateCampaignStatus(c.id, "paused"); await refreshCampaign(c.id); }, t("seo.campaign.updated"))}>{t("seo.campaign.pause")}</button>}
                    {c.status === "paused" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.updateCampaignStatus(c.id, "active"); await refreshCampaign(c.id); }, t("seo.campaign.updated"))}>{t("seo.campaign.resume")}</button>}
                    {!(["completed", "archived"].includes(c.status)) && <button type="button" className="danger" disabled={busy} onClick={() => void run(async () => { await seoApi.updateCampaignStatus(c.id, "archived"); await refreshCampaign(c.id); }, t("seo.campaign.updated"))}>{t("seo.campaign.archive")}</button>}
                    <button type="button" disabled={busy} onClick={() => void run(async () => { const report = await seoApi.campaignReport(c.id); const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }); const href = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = href; a.download = `seo-campaign-${c.id}.json`; a.click(); URL.revokeObjectURL(href); }, t("seo.campaign.reportDownloaded"))}>{t("seo.campaign.exportReport")}</button>
                    {["draft", "planning", "paused"].includes(c.status) && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.campaignAudit(c.id); await refreshCampaign(c.id); }, t("seo.queued"))}>{t("seo.campaign.runAudit")}</button>}
                  </div>
                </div>
                <section>
                  <form className="row" onSubmit={(e) => { e.preventDefault(); void run(async () => { await seoApi.addCampaignKeyword(c.id, { keyword: campaignKeywordDraft, intent: "mixed" }); setCampaignKeywordDraft(""); await refreshCampaign(c.id); }, t("seo.campaign.keywordAdded")); }}>
                    <label>{t("seo.campaign.addKeyword")}<input value={campaignKeywordDraft} onChange={(e) => setCampaignKeywordDraft(e.target.value)} maxLength={240} /></label>
                    <button type="submit" disabled={busy || campaignKeywordDraft.trim().length < 2}>{t("seo.campaign.add")}</button>
                  </form>
                  <label>{t("seo.campaign.sourceMaterial")}<textarea rows={2} value={campaignMaterial} onChange={(e) => setCampaignMaterial(e.target.value)} /></label>
                  <div className="actions">
                    <button type="button" disabled={busy || (!c.site_id && !campaignMaterial.trim())} onClick={() => void run(async () => { await seoApi.suggestCampaignKeywords(c.id, { material: campaignMaterial }); await refreshCampaign(c.id); }, t("seo.campaign.suggestionQueued"))}>{t("seo.campaign.suggest")}</button>
                    <button type="button" disabled={busy || (!c.site_id && !campaignMaterial.trim())} onClick={() => void run(async () => { await seoApi.suggestCampaignKeywords(c.id, { material: campaignMaterial }); await refreshCampaign(c.id); }, t("seo.campaign.suggestionQueued"))}>{t("seo.campaign.refreshSuggestions")}</button>
                    <button type="button" disabled={busy || !(selectedCampaignKeywords[c.id]?.length)} onClick={() => void run(async () => { await seoApi.decideCampaignKeywords(c.id, selectedCampaignKeywords[c.id], "approved"); setSelectedCampaignKeywords((prev) => ({ ...prev, [c.id]: [] })); await refreshCampaign(c.id); }, t("seo.campaign.keywordApproved"))}>{t("seo.campaign.approveSelected")}</button>
                  </div>
                  <ul className="small">
                    {(c.keywords ?? []).map((kw) => <li key={kw.id}>
                      {kw.approval_status === "pending" && <input aria-label={t("seo.campaign.selectKeyword")} type="checkbox" checked={selectedCampaignKeywords[c.id]?.includes(kw.id) ?? false} onChange={(e) => setSelectedCampaignKeywords((prev) => ({ ...prev, [c.id]: e.target.checked ? [...(prev[c.id] ?? []), kw.id] : (prev[c.id] ?? []).filter((id) => id !== kw.id) }))} />}{" "}
                      <strong>{kw.keyword}</strong> · {kw.intent} · {t(`seo.campaign.keyword.${kw.approval_status}` as MessageKey)} · {t("seo.campaign.keywordSource")} {kw.source}
                      <span className="muted"> · volume: {kw.volume ?? unknown}, competition: {kw.competition ?? unknown} · {kw.rationale || t("seo.campaign.noRationale")}</span>
                      {kw.approval_status !== "approved" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.decideCampaignKeyword(c.id, kw.id, "approved"); await refreshCampaign(c.id); }, t("seo.campaign.keywordApproved"))}>{t("seo.campaign.approveKeyword")}</button>}
                      {kw.approval_status !== "rejected" && <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.decideCampaignKeyword(c.id, kw.id, "rejected"); await refreshCampaign(c.id); }, t("seo.campaign.keywordRejected"))}>{t("seo.campaign.rejectKeyword")}</button>}
                      {kw.approval_status === "approved" && <button type="button" disabled={busy} onClick={() => void run(() => seoApi.campaignContentPlan(c.id, { keyword_id: kw.id, material: campaignMaterial }), t("seo.campaign.contentPlanQueued"))}>{t("seo.campaign.generateContentPlan")}</button>}
                      <button type="button" className="danger" disabled={busy} onClick={() => void run(async () => { await seoApi.deleteCampaignKeyword(c.id, kw.id); await refreshCampaign(c.id); }, t("seo.campaign.keywordDeleted"))}>{t("seo.campaign.deleteKeyword")}</button>
                    </li>)}
                  </ul>
                  <h4>{t("seo.campaign.backlog")}</h4>
                  {(c.recommendations ?? []).length === 0 ? <p className="small muted">{t("seo.campaign.noRecommendations")}</p> : <ol className="small">
                    {c.recommendations?.map((r) => <li key={r.id}>
                      <span className="badge" data-risk={r.severity === "critical" ? "high" : r.severity === "warning" ? "medium" : undefined}>{label(`seo.sev.${r.severity}`)}</span> <strong>{r.title}</strong>
                      <p>{r.recommendation}</p>
                      <p className="muted">{t("seo.campaign.evidence")}: {String(r.evidence.page ?? "-")} · {String(r.evidence.detail ?? "-")} · {t("seo.campaign.impact")}: {r.impact_basis} · {t("seo.campaign.effort")}: {r.effort} · {t("seo.campaign.risk")}: {r.risk}</p>
                      <p className="muted">{t("seo.campaign.verify")}: {r.verification_method}</p>
                      {r.status === "proposed" && <div className="actions">
                        <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.decideCampaignRecommendation(c.id, r.id, "approved"); await refreshCampaign(c.id); }, t("seo.campaign.recommendationApproved"))}>{t("seo.campaign.approveRecommendation")}</button>
                        <button type="button" disabled={busy} onClick={() => void run(async () => { await seoApi.decideCampaignRecommendation(c.id, r.id, "rejected"); await refreshCampaign(c.id); }, t("seo.campaign.recommendationRejected"))}>{t("seo.campaign.rejectRecommendation")}</button>
                      </div>}
                      <span className="badge">{t(`seo.campaign.recommendation.${r.status}` as MessageKey)}</span>
                    </li>)}
                  </ol>}
                  {c.history && <details><summary>{t("seo.campaign.history")}</summary><ul className="small">{c.history.slice(0, 8).map((h) => <li key={h.id}>{new Date(h.created_at).toLocaleString()} · {h.kind}</li>)}</ul></details>}
                </section>
              </li>
            ))}
          </ul>
        )}
      </section>

      {siteList.length > 0 && (
        <section className="card">
          <h3>{t("seo.sites.title")}</h3>
          <p className="small muted">{t("seo.sites.hint")}</p>
          <ul className="list">
            {siteList.map((s) => (
              <li key={s.id} className="card">
                <div>
                  <strong>{s.name}</strong> <a href={s.url} target="_blank" rel="noopener noreferrer">{s.url}</a>
                  <p className="small muted">
                    {s.last_audit?.counts
                      ? t("seo.counts").replace("{c}", String(s.last_audit.counts.critical)).replace("{w}", String(s.last_audit.counts.warning)).replace("{i}", String(s.last_audit.counts.info))
                      : t("seo.sites.noaudit")}
                  </p>
                  {siteDetail?.id === s.id && siteDetail.pages && (
                    <p className="small muted">{siteDetail.pages.map((p) => p.path).join(" · ")}{siteDetail.has_robots ? " · robots.txt" : ""}{siteDetail.has_sitemap ? " · sitemap.xml" : ""}</p>
                  )}
                </div>
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => void run(() => seoApi.siteAudit(s.id), t("seo.queued"))}>{t("seo.sites.audit")}</button>
                  <button type="button" onClick={() => void seoApi.site(s.id).then(setSiteDetail, (e: Error) => setError(e.message))}>{t("seo.sites.pages")}</button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

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
          <label>{t("seo.topic")}<input value={topic} onChange={(e) => setTopic(e.target.value)} minLength={2} /></label>
          <label>{t("seo.material")}<textarea rows={5} value={material} onChange={(e) => setMaterial(e.target.value)} /></label>
          {siteList.length > 0 && (
            <label>{t("seo.sites.pick")}<select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
              <option value="">-</option>{siteList.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          )}
          <label>{t("seo.product")}<select value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">-</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
          <div className="actions">
            <button type="button" disabled={busy || (!siteId && (topic.length < 2 || !material.trim()))} onClick={() => void run(() => siteId ? seoApi.siteKeywords(siteId, { topic: topic || undefined, material }) : seoApi.keywords({ topic, material, product_id: productId || undefined }), t("seo.queued"))}>{t("seo.kw.run")}</button>
            <button type="button" disabled={busy || (!siteId && topic.length < 2)} onClick={() => void run(() => siteId ? seoApi.siteBrief(siteId, { topic: topic || undefined, material }) : seoApi.brief({ topic, material, product_id: productId || undefined }), t("seo.queued"))}>{t("seo.brief.run")}</button>
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
              <ul>{open.data.findings.map((f, index) => <li key={`${f.id}:${f.page ?? ""}:${index}`}><span className="badge" data-risk={f.severity === "critical" ? "high" : f.severity === "warning" ? "medium" : undefined}>{label(`seo.sev.${f.severity}`)}</span> {f.page ? <code>{f.page}</code> : null} {f.message}{f.recommendation ? <span className="small muted"> → {f.recommendation}</span> : null}</li>)}</ul>
              <p className="small muted">{t("seo.notchecked")}: {open.data.not_checked.join("; ")}</p>
              {open.handed_off_to ? <p className="small ok">{t("seo.handed")}: <Link href={`/tasks/${open.handed_off_to}`}>{open.handed_off_to.slice(0, 8)}</Link></p> : (
                <div className="row">
                  <label>{open.data.site_id ? t("seo.handoff.siteproject") : t("seo.handoff.project")}<select value={handoffProject} onChange={(e) => setHandoffProject(e.target.value)}><option value="">-</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
                  <button type="button" disabled={busy || (!handoffProject && !open.data?.site_id)} onClick={() => void run(() => seoApi.handoff(open.id, handoffProject), t("seo.handoff.done"))}>{t("seo.handoff.run")}</button>
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
