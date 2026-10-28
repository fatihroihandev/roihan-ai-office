"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Loading, PageHero } from "@/components/ui/PageHero";
import {
  marketingApi, PIPELINE, SOURCE_TYPES, type Lead, type Opportunity, type Policy, type Retention,
} from "@/lib/marketingApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";
import { Icon } from "@/components/ui/Icons";

const IDR = new Intl.NumberFormat("id-ID");

export function LeadsFeature() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [retention, setRetention] = useState<Retention | null>(null);
  const [suppressed, setSuppressed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Form input state
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [size, setSize] = useState("unknown");
  const [cName, setCName] = useState("");
  const [cTitle, setCTitle] = useState("");
  const [cEmail, setCEmail] = useState("");
  const [cPhone, setCPhone] = useState("");
  const [sourceType, setSourceType] = useState<string>("manual");
  const [sourceUrl, setSourceUrl] = useState("");

  const fetchAll = useCallback(
    () => Promise.all([
      marketingApi.leads(),
      marketingApi.opportunities(),
      marketingApi.retention(),
      marketingApi.suppression(),
      marketingApi.policy(),
    ]),
    [],
  );

  const apply = useCallback(([l, o, rt, sp, p]: Awaited<ReturnType<typeof fetchAll>>) => {
    setLeads(l);
    setOpps(o);
    setRetention(rt);
    setSuppressed(sp.length);
    setPolicy(p);
  }, []);

  const reload = useCallback(async () => apply(await fetchAll()), [apply, fetchAll]);

  useEffect(() => {
    let cancelled = false;
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
      setCompany("");
      setIndustry("");
      setCName("");
      setCTitle("");
      setCEmail("");
      setCPhone("");
      setSourceUrl("");
    }, t("mkt.taskQueued"));
  };

  return (
    <PageTransition>
      <main data-accent="blue">
        <PageHero
          code="04.3"
          route="SYS://LEADS"
          art="marketing"
          title={t("nav.leadsCrm")}
          hint={t("mkt.hint")}
          stats={[
            { label: t("hero.stat.leads"), value: leads?.length ?? 0 },
            { label: t("hero.stat.opps"), value: opps.filter((o) => o.stage !== "won" && o.stage !== "lost").length, tone: "ok" },
            { label: t("mkt.retention.label"), value: retention?.due.length ?? 0, tone: (retention?.due.length ?? 0) > 0 ? "warn" : "ok" },
            { label: t("mkt.suppression.label"), value: suppressed },
          ]}
        />

        {error && <p className="bad" role="alert">{error}</p>}
        {notice && <p className="ok" role="status">{notice}</p>}

        <div className="duo">
          {policy && (
            <section className="card">
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <span style={{ color: "var(--info)", display: "flex" }}>
                  <Icon name="shield" size={17} />
                </span>
                <h3 style={{ margin: 0 }}>{t("mkt.policy")}</h3>
              </div>
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
                    type="button"
                    disabled={busy}
                    onClick={() => window.confirm(t("mkt.retention.confirm")) && void run(() => marketingApi.runRetention(), t("mkt.retention.apply"))}
                  >
                    {t("mkt.retention.apply")}
                  </button>
                </p>
              )}
            </section>
          )}

          <form className="card" onSubmit={onCreate}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ color: "var(--accent)", display: "flex" }}>
                <Icon name="plus" size={17} />
              </span>
              <h3 style={{ margin: 0 }}>{t("mkt.newLead")}</h3>
            </div>
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
            <div className="actions">
              <button
                type="submit"
                disabled={busy || !company.trim()}
                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
              >
                <Icon name="plus" size={14} />
                <span>{t("mkt.create")}</span>
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => { setCompany(""); setIndustry(""); setSize("unknown"); setCName(""); setCTitle(""); setCEmail(""); setCPhone(""); setSourceType("manual"); setSourceUrl(""); }}
                style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
              >
                <Icon name="close" size={13} />
                <span>{t("webfinder.clearInputs")}</span>
              </button>
            </div>
          </form>
        </div>

        <section className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="users" size={17} />
            </span>
            <h3 style={{ margin: 0 }}>{t("mkt.pipeline")}</h3>
          </div>
          {leads === null && !error && <Loading />}
          {leads?.length === 0 && <p className="muted">{t("mkt.empty")}</p>}
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
                      <div className="actions">
                        <Link
                          className="button"
                          href={`/marketing/leads/${l.id}`}
                          style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                        >
                          <span>{t("mkt.open")}</span>
                          <Icon name="arrow-right" size={12} />
                        </Link>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => window.confirm(t("mkt.lead.deleteConfirm")) && void run(() => marketingApi.deleteLead(l.id), t("mkt.lead.deleted"))}
                          style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                        >
                          <Icon name="trash" size={13} />
                          <span>{t("mkt.lead.delete")}</span>
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </section>

        <section className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "var(--ok)", display: "flex" }}>
              <Icon name="trend-up" size={17} />
            </span>
            <h3 style={{ margin: 0 }}>{t("mkt.opps")}</h3>
          </div>
          {opps.length === 0 && <p className="muted">-</p>}
          <ul className="list">
            {opps.map((o) => (
              <li key={o.id} className="card">
                <div>
                  <strong>{o.title}</strong>
                  <span className="badge">{label(`mkt.stage.${o.stage}`)}</span>
                  <span className="small muted"> {o.won_value_idr !== null ? `IDR ${IDR.format(o.won_value_idr)}` : o.value_estimate_idr !== null ? `~IDR ${IDR.format(o.value_estimate_idr)}` : ""}</span>
                </div>
                <Link
                  className="button"
                  href={`/marketing/leads/${o.lead_id}`}
                  style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                >
                  <span>{t("mkt.open")}</span>
                  <Icon name="arrow-right" size={12} />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </PageTransition>
  );
}
