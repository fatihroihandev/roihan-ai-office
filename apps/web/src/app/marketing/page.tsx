"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHero } from "@/components/ui/PageHero";
import {
  marketingApi, PIPELINE, SOURCE_TYPES, type Analytics, type Lead, type Opportunity, type Outreach, type Policy, type Research, type Retention,
} from "@/lib/marketingApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const IDR = new Intl.NumberFormat("id-ID");

export default function MarketingPage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [stats, setStats] = useState<Analytics | null>(null);
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [drafts, setDrafts] = useState<Outreach[]>([]);
  const [research, setResearch] = useState<Research[]>([]);
  const [retention, setRetention] = useState<Retention | null>(null);
  const [suppressed, setSuppressed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [size, setSize] = useState("unknown");
  const [cName, setCName] = useState("");
  const [cTitle, setCTitle] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cPhone, setCPhone] = useState("");
  const [sourceType, setSourceType] = useState<string>("manual");
  const [sourceUrl, setSourceUrl] = useState("");

  const [intakeSource, setIntakeSource] = useState<string>("event");
  const [intakeUrl, setIntakeUrl] = useState("");
  const [rawText, setRawText] = useState("");
  const [topic, setTopic] = useState("");
  const [material, setMaterial] = useState("");

  const fetchAll = useCallback(
    () => Promise.all([
      marketingApi.analytics(), marketingApi.leads(), marketingApi.opportunities(), marketingApi.outreach(), marketingApi.research(),
      marketingApi.retention(), marketingApi.suppression(),
    ]),
    [],
  );
  const apply = useCallback(([a, l, o, d, r, rt, sp]: Awaited<ReturnType<typeof fetchAll>>) => {
    setStats(a); setLeads(l); setOpps(o); setDrafts(d); setResearch(r); setRetention(rt); setSuppressed(sp.length);
  }, []);
  const reload = useCallback(async () => apply(await fetchAll()), [apply, fetchAll]);

  useEffect(() => {
    let cancelled = false;
    marketingApi.policy().then((p) => !cancelled && setPolicy(p), () => undefined);
    fetchAll().then((d) => !cancelled && apply(d), (e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [fetchAll, apply]);

  async function run(action: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      if (done) setNotice(done);
      await reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const onCreate = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      await marketingApi.createLead({
        company: { name: company, industry, size_band: size },
        contact: { name: cName, title: cTitle, email: cEmail, phone: cPhone },
        source: { source_type: sourceType, url: sourceUrl },
      });
      setCompany(""); setIndustry(""); setCName(""); setCTitle(""); setCEmail(""); setCPhone(""); setSourceUrl("");
    });
  };

  const unknown = t("mkt.m.unknown");
  const pct = (v: number | null) => (v === null ? unknown : `${Math.round(v * 100)}%`);

  return (
    <PageTransition>
<main data-accent="magenta">
      <PageHero
        code="04" route="SYS://MARKETING" art="marketing" title={t("mkt.title")} hint={t("mkt.hint")}
        stats={[
          { label: t("hero.stat.leads"), value: stats?.leads_total ?? 0 },
          { label: t("hero.stat.opps"), value: stats?.opportunities_open ?? 0, tone: "ok" },
          { label: t("hero.stat.drafts"), value: drafts.filter((d) => d.status === "ready_for_review").length, tone: "warn" },
          { label: t("office.stat.outbox"), value: drafts.filter((d) => d.status === "queued_for_dispatch").length },
        ]}
      />
      <p><Link className="button" href="/marketing/content">{t("mkt.nav.content")}</Link></p>
      {error && <p className="bad" role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      <div className="duo">
      {policy && (
        <section className="card">
          <h3>{t("mkt.policy")}</h3>
          <p className="small">{t("mkt.policy.allowed")}: {policy.allowed_sources.map((s) => label(`mkt.source.${s.type}`)).join(", ")}</p>
          <p className="small">{t("mkt.policy.forbidden")}: {policy.forbidden_sources.map((s) => s.type).join(", ")}</p>
          <p className="small">
            {t("mkt.policy.retention").replace("{a}", String(policy.retention.no_interaction_days)).replace("{b}", String(policy.retention.after_last_interaction_days))}
          </p>
          <p className="small">{t("mkt.policy.minScore").replace("{n}", String(policy.min_score_for_sales))}</p>
          <p className="small muted">{t("mkt.suppression").replace("{n}", String(suppressed))}</p>
          {retention && retention.due.length > 0 && (
            <p>
              <span className="bad">{t("mkt.retention.due").replace("{n}", String(retention.due.length))}</span>{" "}
              <button
                type="button" disabled={busy}
                onClick={() => window.confirm(t("mkt.retention.confirm")) && void run(() => marketingApi.runRetention())}
              >
                {t("mkt.retention.apply")}
              </button>
            </p>
          )}
        </section>
      )}

      {stats && (
        <section className="card">
          <h3>{t("mkt.analytics")}</h3>
          <dl>
            <dt>{t("mkt.m.leads")}</dt><dd>{stats.leads_total}</dd>
            <dt>{t("mkt.m.meeting")}</dt><dd>{pct(stats.lead_to_meeting_rate)}</dd>
            <dt>{t("mkt.m.opps")}</dt><dd>{stats.opportunities_open}</dd>
            <dt>{t("mkt.m.win")}</dt><dd>{pct(stats.win_rate)}</dd>
            <dt>{t("mkt.m.revenue")}</dt><dd>{stats.revenue_recorded_idr === null ? unknown : IDR.format(stats.revenue_recorded_idr)}</dd>
            <dt>{t("mkt.m.cac")}</dt><dd>{unknown}</dd>
          </dl>
        </section>
      )}

      </div>

      <form className="card" onSubmit={onCreate}>
        <h3>{t("mkt.newLead")}</h3>
        <label>{t("mkt.company")}<input value={company} maxLength={200} onChange={(e) => setCompany(e.target.value)} required /></label>
        <div className="row">
          <label>{t("mkt.industry")}<input value={industry} onChange={(e) => setIndustry(e.target.value)} /></label>
          <label>
            {t("mkt.size")}
            <select value={size} onChange={(e) => setSize(e.target.value)}>
              {["unknown", "micro", "small", "medium", "large"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <div className="row">
          <label>{t("mkt.contactName")}<input value={cName} onChange={(e) => setCName(e.target.value)} /></label>
          <label>{t("mkt.contactTitle")}<input value={cTitle} onChange={(e) => setCTitle(e.target.value)} /></label>
        </div>
        <div className="row">
          <label>{t("mkt.contactEmail")}<input type="email" value={cEmail} onChange={(e) => setCEmail(e.target.value)} /></label>
          <label>{t("mkt.contactPhone")}<input value={cPhone} onChange={(e) => setCPhone(e.target.value)} /></label>
        </div>
        <div className="row">
          <label>
            {t("mkt.sourceType")}
            <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
              {SOURCE_TYPES.map((s) => <option key={s} value={s}>{label(`mkt.source.${s}`)}</option>)}
            </select>
          </label>
          <label>{t("mkt.sourceUrl")}<input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://" /></label>
        </div>
        <button type="submit" disabled={busy || !company.trim()}>{t("mkt.create")}</button>
      </form>

      <section className="card">
        <h3>{t("mkt.pipeline")}</h3>
        {leads === null && !error && <Loading />}
        {leads?.length === 0 && <p>{t("mkt.empty")}</p>}
        {PIPELINE.map((st) => {
          const rows = (leads ?? []).filter((l) => l.status === st);
          if (rows.length === 0) return null;
          return (
            <div key={st}>
              <h4>{label(`mkt.status.${st}`)} ({rows.length})</h4>
              <ul className="list">
                {rows.map((l) => (
                  <li key={l.id} className="card">
                    <div>
                      <strong>{l.company.name}</strong>
                      <span className="badge">{t("mkt.score")} {l.score ?? "-"}</span>
                      <span className="badge">{label(`mkt.source.${l.source.type}`)}</span>
                      {l.anonymized && <span className="badge">{t("mkt.lead.anonymized")}</span>}
                      <div className="small muted">{l.contact.name ?? "-"} · {l.contact.email ?? "-"}</div>
                    </div>
                    <Link className="button" href={`/marketing/leads/${l.id}`}>{t("mkt.open")}</Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>

      <section className="card">
        <h3>{t("mkt.opps")}</h3>
        {opps.length === 0 && <p className="muted">-</p>}
        <ul className="list">
          {opps.map((o) => (
            <li key={o.id} className="card">
              <div>
                <strong>{o.title}</strong>
                <span className="badge">{label(`mkt.stage.${o.stage}`)}</span>
                <span className="small muted"> {o.won_value_idr !== null ? `IDR ${IDR.format(o.won_value_idr)}` : o.value_estimate_idr !== null ? `~IDR ${IDR.format(o.value_estimate_idr)}` : ""}</span>
              </div>
              <Link className="button" href={`/marketing/leads/${o.lead_id}`}>{t("mkt.open")}</Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>{t("mkt.outreach")}</h3>
        <p className="small muted">{t("mkt.outreach.sentNote")}</p>
        {drafts.length === 0 && <p className="muted">{t("mkt.outreach.empty")}</p>}
        <ul className="list">
          {drafts.map((d) => (
            <li key={d.id} className="card">
              <div>
                <strong>{d.subject}</strong>
                <span className="badge" data-task={d.status === "ready_for_review" || d.status === "sent_manual" ? "completed" : "failed"}>{label(`mkt.ostatus.${d.status}`)}</span>
                <pre className="output">{d.body}</pre>
                {d.claim_check && !d.claim_check.ok && (
                  <ul className="small bad">{d.claim_check.findings.map((f, i) => <li key={i}>{f.detail}{f.match ? ` — “${f.match}”` : ""}</li>)}</ul>
                )}
                <Link className="small" href={`/marketing/leads/${d.lead_id}`}>{t("mkt.open")}</Link>
              </div>
              {d.status === "ready_for_review" && (
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.requestSend(d.id), t("ext.requested"))}>{t("ext.requestSend")}</button>
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.markSent(d.id))}>{t("mkt.outreach.markSent")}</button>
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.cancelOutreach(d.id))}>{t("mkt.outreach.cancel")}</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await marketingApi.runIntake({ source_type: intakeSource, url: intakeUrl }, rawText);
            setRawText("");
          }, t("mkt.taskQueued"));
        }}
      >
        <h3>{t("mkt.intake")}</h3>
        <p className="muted small">{t("mkt.intake.hint")}</p>
        <div className="row">
          <label>
            {t("mkt.sourceType")}
            <select value={intakeSource} onChange={(e) => setIntakeSource(e.target.value)}>
              {SOURCE_TYPES.map((s) => <option key={s} value={s}>{label(`mkt.source.${s}`)}</option>)}
            </select>
          </label>
          <label>{t("mkt.sourceUrl")}<input value={intakeUrl} onChange={(e) => setIntakeUrl(e.target.value)} placeholder="https://" /></label>
        </div>
        <label>{t("mkt.rawText")}<textarea rows={5} maxLength={8000} value={rawText} onChange={(e) => setRawText(e.target.value)} required /></label>
        <button type="submit" disabled={busy || !rawText.trim()}>{t("mkt.runIntake")}</button>
      </form>

      <form
        className="card"
        onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await marketingApi.runResearch(topic, material);
            setMaterial("");
          }, t("mkt.taskQueued"));
        }}
      >
        <h3>{t("mkt.research")}</h3>
        <p className="muted small">{t("mkt.research.hint")}</p>
        <label>{t("mkt.topic")}<input value={topic} maxLength={200} onChange={(e) => setTopic(e.target.value)} required minLength={3} /></label>
        <label>{t("mkt.material")}<textarea rows={5} maxLength={8000} value={material} onChange={(e) => setMaterial(e.target.value)} required /></label>
        <button type="submit" disabled={busy || topic.trim().length < 3 || !material.trim()}>{t("mkt.runResearch")}</button>
      </form>

      {research.length > 0 && (
        <section className="card">
          <h3>{t("mkt.research.results")}</h3>
          {research.map((r) => (
            <div key={r.id}>
              <h4>{r.topic}</h4>
              <p className="small muted">{t("mkt.research.verified").replace("{v}", String(r.verified_count)).replace("{u}", String(r.unverified_count))}</p>
              <p>{r.summary}</p>
              <ul>
                {r.items.map((it, i) => (
                  <li key={i}>
                    {it.statement}
                    <span className="badge" data-task={it.verified ? "completed" : "failed"}>{it.verified ? it.basis : "unverified"}</span>
                    {it.verified && <div className="small muted">“{it.evidence_quote}”</div>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </main>
</PageTransition>
  );
}
