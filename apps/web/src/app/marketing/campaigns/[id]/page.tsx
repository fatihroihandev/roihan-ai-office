"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { Icon } from "@/components/ui/Icons";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { marketingApi, METRICS, NEXT_CAMPAIGN, type Campaign } from "@/lib/marketingApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function CampaignPage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const { id } = useParams<{ id: string }>();
  const [camp, setCamp] = useState<Campaign | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [metric, setMetric] = useState<string>("impressions");
  const [value, setValue] = useState("");

  useEffect(() => {
    let cancelled = false;
    marketingApi.campaign(id).then((c) => !cancelled && setCamp(c), (e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setCamp(await marketingApi.campaign(id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!camp) return <PageTransition>
<main>{error ? <p className="bad" role="alert">{error}</p> : <p>{t("common.loading")}</p>}</main>
</PageTransition>;
  const unknown = t("mkt.m.unknown");
  const sorted = [...(camp.content ?? [])].sort((a, b) => (a.scheduled_for ?? "9").localeCompare(b.scheduled_for ?? "9"));

  return (
    <PageTransition>
<main>
      <p><Link href="/marketing/content" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}><Icon name="arrow-left" size={14} /> {t("ext.back")}</Link></p>
      <h2>{camp.name} <span className="badge">{label(`ext.campstatus.${camp.status}`)}</span></h2>
      <p className="muted">{camp.objective}</p>
      <p className="small">{camp.channels.join(", ")} · {t("ext.campaign.budget")}</p>
      {error && <p className="bad" role="alert">{error}</p>}

      {(NEXT_CAMPAIGN[camp.status] ?? []).length > 0 && (
        <div className="actions">
          <span className="muted">{t("ext.campaign.status")}:</span>
          {NEXT_CAMPAIGN[camp.status].map((s) => (
            <button key={s} type="button" disabled={busy} onClick={() => void run(() => marketingApi.campaignStatus(camp.id, s))}>{label(`ext.campstatus.${s}`)}</button>
          ))}
        </div>
      )}

      <section className="card">
        <h3>{t("ext.campaign.report")}</h3>
        <dl>
          {METRICS.map((m) => (
            <div key={m} style={{ display: "contents" }}>
              <dt>{label(`ext.metric.${m}`)}</dt><dd>{camp.report?.metrics[m] ?? unknown}</dd>
            </div>
          ))}
          <dt>{t("ext.campaign.roi")}</dt><dd>{camp.report?.roi === null || camp.report?.roi === undefined ? unknown : `${Math.round(camp.report.roi * 100)}%`}</dd>
        </dl>
        <p className="small muted">{t("ext.campaign.roi.hint")}</p>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => { await marketingApi.recordMetric(camp.id, metric, Number(value)); setValue(""); });
          }}
        >
          <label>{t("ext.campaign.metric")}
            <select value={metric} onChange={(e) => setMetric(e.target.value)}>
              {METRICS.map((m) => <option key={m} value={m}>{label(`ext.metric.${m}`)}</option>)}
            </select>
          </label>
          <label>{t("ext.campaign.value")}<input type="number" min={0} value={value} onChange={(e) => setValue(e.target.value)} required /></label>
          <button type="submit" disabled={busy || value === ""}>{t("ext.campaign.record")}</button>
        </form>
      </section>

      <section className="card">
        <h3>{t("ext.campaign.calendar")}</h3>
        {sorted.length === 0 && <p className="muted">{t("ext.content.empty")}</p>}
        <ul>
          {sorted.map((a) => (
            <li key={a.id}>
              <strong>{a.title}</strong> <span className="badge">{a.channel}</span> <span className="badge">{label(`ext.cstatus.${a.status}`)}</span>
              <span className="small muted"> {t("ext.scheduled")}: {a.scheduled_for ? new Date(a.scheduled_for).toLocaleDateString() : t("ext.unscheduled")}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
</PageTransition>
  );
}
