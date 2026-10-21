"use client";

import Link from "next/link";
import type { Dashboard } from "@/lib/dashboardApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const IDR = new Intl.NumberFormat("id-ID");

export function DashboardPanel({ d }: { d: Dashboard }) {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const active = (d.tasks.queued ?? 0) + (d.tasks.running ?? 0) + (d.tasks.pending_approval ?? 0);
  const problems = (d.tasks.failed ?? 0) + (d.tasks.blocked ?? 0);
  const paid = d.ai.paid_calls_24h > 0 || d.ai.paid_providers_enabled;
  return (
    <section className="card" aria-label={t("office.ceo.title")}>
      <h3>{t("office.ceo.title")}</h3>
      <div className="stats">
        <div><strong>{d.projects_active}</strong><span>{t("office.stat.projects")}</span></div>
        <div><strong>{active}</strong><span>{t("office.stat.activeTasks")}</span></div>
        <div data-alert={d.approvals_pending > 0}><strong>{d.approvals_pending}</strong><span>{t("office.stat.approvals")}</span></div>
        <div data-alert={problems > 0}><strong>{problems}</strong><span>{t("office.stat.problems")}</span></div>
        <div><strong>{d.marketing.leads_total}</strong><span>{t("office.stat.leads")}</span></div>
        <div data-alert={d.marketing.outbox_waiting > 0}><strong>{d.marketing.outbox_waiting}</strong><span>{t("office.stat.outbox")}</span></div>
      </div>

      <h4>{t("office.needs")}</h4>
      {d.needs_decision.length === 0 && d.marketing.content_ready + d.marketing.outreach_ready + d.marketing.retention_due === 0 && <p className="muted">{t("office.needs.none")}</p>}
      <ul className="needs">
        {d.needs_decision.map((n) => (
          <li key={`${n.kind}-${n.id}`}>
            <span className="badge" data-risk={n.risk}>{label(`office.kind.${n.kind}`)}</span>{" "}
            <Link href={n.href}>{n.title}</Link>{n.reason ? <span className="small muted"> ({n.reason})</span> : null}
          </li>
        ))}
        {d.marketing.content_ready > 0 && <li><Link href="/marketing/content">{t("office.kind.content_ready")}: {d.marketing.content_ready}</Link></li>}
        {d.marketing.outreach_ready > 0 && <li><Link href="/marketing">{t("office.kind.outreach_ready")}: {d.marketing.outreach_ready}</Link></li>}
        {d.marketing.retention_due > 0 && <li><Link href="/marketing">{t("office.kind.retention_due")}: {d.marketing.retention_due}</Link></li>}
      </ul>

      <h4>{t("office.ai")}</h4>
      <p className="small">
        {t("office.ai.line").replace("{c}", IDR.format(d.ai.calls_24h)).replace("{k}", IDR.format(d.ai.tokens_24h)).replace("{e}", String(d.ai.errors_24h))}
        {" · "}
        <span className="badge" data-task={paid ? "failed" : "completed"}>{paid ? t("office.ai.paidOn") : t("office.ai.paidOff")}</span>
        {" · "}
        <span className="badge" data-task={d.worker.running ? "completed" : "failed"}>{d.worker.running ? t("office.worker.on") : t("office.worker.off")}</span>
      </p>
    </section>
  );
}
