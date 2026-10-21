"use client";

import Link from "next/link";
import { useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { DashboardPanel } from "@/components/office/DashboardPanel";
import { OfficeView } from "@/components/office/OfficeView";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function OfficePage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const { data, stale, connected, updatedAt } = useOfficeData();
  const [selected, setSelected] = useState<string | null>(null);
  const agent = data?.agents.find((a) => a.role === selected) ?? null;

  return (
    <main data-wide>
      <AppHeader />
      <h2>{t("office.heading")}</h2>
      <p className="muted">{t("office.hint")}</p>
      <p className="small" role="status">
        <span className="badge" data-task={connected ? "completed" : "failed"}>{connected ? t("office.live") : t("office.polling")}</span>
        {stale && <span className="bad"> {t("office.stale")}{updatedAt ? ` (${new Date(updatedAt).toLocaleTimeString()})` : ""}</span>}
      </p>
      {!data && !stale && <p>{t("common.loading")}</p>}
      {!data && stale && <p className="bad" role="alert">{t("office.unavailable")}</p>}
      {data && (
        <div className="officegrid">
          <div>
            <OfficeView data={data} selected={selected} onSelect={setSelected} />
            <section className="card" aria-live="polite">
              <h3>{t("office.agent")}</h3>
              {!agent && <p className="muted">{t("office.agent.none")}</p>}
              {agent && (
                <dl>
                  <dt>{t("office.agent.role")}</dt><dd>{label(`role.${agent.role}`)} ({agent.department})</dd>
                  <dt>{t("office.agent.status")}</dt><dd><span className="badge" data-agent={agent.status}>{label(`agent.${agent.status}`)}</span></dd>
                  <dt>{t("office.agent.task")}</dt>
                  <dd>{agent.current_task_id ? <Link href={`/tasks/${agent.current_task_id}`}>{agent.current_task_title}</Link> : "-"}</dd>
                  <dt>{t("office.agent.queued")}</dt><dd>{agent.queued}</dd>
                </dl>
              )}
            </section>
          </div>
          <DashboardPanel d={data} />
        </div>
      )}
    </main>
  );
}
