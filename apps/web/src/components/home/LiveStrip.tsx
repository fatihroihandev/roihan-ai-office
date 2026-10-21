"use client";

import Link from "next/link";
import type { Dashboard } from "@/lib/dashboardApi";
import type { Insights } from "@/lib/insightsApi";
import { situation } from "@/lib/charts/situation";
import { poseOf, toneOf } from "@/lib/office/model";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export function LiveStrip({ data, stale, ins }: { data: Dashboard | null; stale: boolean; ins: Insights | null }) {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  if (!data) {
    return (
      <section className="card live" aria-label={t("home.live.title")}>
        <h3>{t("home.live.title")}</h3>
        <p className={stale ? "bad" : "muted"}>{stale ? t("office.unavailable") : t("common.loading")}</p>
      </section>
    );
  }
  const active = (data.tasks.queued ?? 0) + (data.tasks.running ?? 0) + (data.tasks.pending_approval ?? 0);
  const problems = (data.tasks.failed ?? 0) + (data.tasks.blocked ?? 0);
  const kpis: { key: MessageKey; value: number; alert?: boolean; href: string }[] = [
    { key: "office.stat.projects", value: data.projects_active, href: "/projects" },
    { key: "office.stat.activeTasks", value: active, href: "/tasks" },
    { key: "office.stat.approvals", value: data.approvals_pending, alert: data.approvals_pending > 0, href: "/approvals" },
    { key: "office.stat.problems", value: problems, alert: problems > 0, href: "/tasks" },
    { key: "office.stat.leads", value: data.marketing.leads_total, href: "/marketing" },
    { key: "office.stat.outbox", value: data.marketing.outbox_waiting, alert: data.marketing.outbox_waiting > 0, href: "/marketing/content" },
  ];
  const waiting = data.needs_decision.slice(0, 4);
  const fill = (key: string, params: Record<string, string | number>) => Object.entries(params).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), label(key));
  const sit = situation(data, ins);
  return (
    <section className="live" aria-label={t("home.live.title")}>
      <div className="sitrep" data-level={sit.level} role="status">
        <i aria-hidden="true" />
        <div>
          <strong>{fill(sit.headline.key, sit.headline.params)}</strong>
          {sit.details.length > 0 && <ul>{sit.details.map((x) => <li key={x.key}>{fill(x.key, x.params)}</li>)}</ul>}
        </div>
      </div>
      {stale && <p className="bad small" role="status">{t("office.stale")}</p>}
      <div className="kpis">
        {kpis.map((k) => (
          <Link key={k.key} href={k.href} className="kpi" data-alert={k.alert ? "true" : "false"}>
            <strong>{k.value}</strong>
            <span>{t(k.key)}</span>
          </Link>
        ))}
      </div>
      <div className="livegrid">
        <div className="card">
          <h3>{t("home.live.agents")}</h3>
          <ul className="agentrow">
            {data.agents.map((a) => (
              <li key={a.role}>
                <Link href="/office" className="agentdot" data-tone={toneOf(a.status)} data-pose={poseOf(a.status)}>
                  <i aria-hidden="true" />
                  <span>{label(`role.${a.role}`)}</span>
                  <em>{label(`agent.${a.status}`)}</em>
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3>{t("office.needs")}</h3>
          {waiting.length === 0 && <p className="muted">{t("office.needs.none")}</p>}
          <ul className="needs">
            {waiting.map((n) => (
              <li key={`${n.kind}-${n.id}`}>
                <span className="badge" data-risk={n.risk}>{label(`office.kind.${n.kind}`)}</span> <Link href={n.href}>{n.title}</Link>
              </li>
            ))}
          </ul>
          <p className="small muted">
            {t("office.ai.line").replace("{c}", String(data.ai.calls_24h)).replace("{k}", String(data.ai.tokens_24h)).replace("{e}", String(data.ai.errors_24h))}
          </p>
        </div>
      </div>
    </section>
  );
}
