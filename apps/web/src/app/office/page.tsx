"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { DashboardPanel } from "@/components/office/DashboardPanel";
import { ModeControls, OfficeScene, useOfficeMode } from "@/components/office/OfficeView";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function OfficePage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const { data, stale, connected, updatedAt } = useOfficeData();
  const { mode, pref, setPref, caps, failed, onFail } = useOfficeMode();
  const [selected, setSelected] = useState<string | null>(null);
  const [panel, setPanel] = useState(true);
  const stage = useRef<HTMLDivElement>(null);
  const agent = data?.agents.find((a) => a.role === selected) ?? null;

  const toggleFullscreen = () => {
    const el = stage.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  };

  return (
    <main data-office>
      <AppHeader />
      <div className="office-title">
        <h2>{t("office.heading")}</h2>
        <p className="muted small">{t("office.hint")}</p>
      </div>
      {!data && !stale && <p>{t("common.loading")}</p>}
      {!data && stale && <p className="bad" role="alert">{t("office.unavailable")}</p>}
      {data && (
        <div className="stage" data-mode={mode} ref={stage}>
          <OfficeScene data={data} mode={mode} onFail={onFail} selected={selected} onSelect={setSelected} />

          <div className="hud hud-tl glass" role="status">
            <span className="badge" data-task={connected ? "completed" : "failed"}>{connected ? t("office.live") : t("office.polling")}</span>
            {stale && <span className="bad small"> {t("office.stale")}{updatedAt ? ` (${new Date(updatedAt).toLocaleTimeString()})` : ""}</span>}
            {!caps.webgl && <span className="small muted"> {t("office.noWebgl")}</span>}
            {failed && <span className="small bad" role="alert"> {t("office.failed")}</span>}
          </div>

          <div className="hud hud-tr glass">
            <ModeControls pref={pref} setPref={setPref} />
            <button type="button" aria-pressed={panel} onClick={() => setPanel((p) => !p)}>{t("office.panel")}</button>
            <button type="button" onClick={toggleFullscreen}>{t("office.fullscreen")}</button>
          </div>

          {panel && (
            <aside className="hud hud-right glass">
              <DashboardPanel d={data} />
            </aside>
          )}

          <div className="hud hud-bl glass" aria-live="polite">
            <h4>{t("office.agent")}</h4>
            {!agent && <p className="muted small">{t("office.agent.none")} {t("office.legend")}</p>}
            {agent && (
              <dl>
                <dt>{t("office.agent.role")}</dt><dd>{label(`role.${agent.role}`)}</dd>
                <dt>{t("office.agent.status")}</dt><dd><span className="badge" data-agent={agent.status}>{label(`agent.${agent.status}`)}</span></dd>
                <dt>{t("office.agent.task")}</dt>
                <dd>{agent.current_task_id ? <Link href={`/tasks/${agent.current_task_id}`}>{agent.current_task_title}</Link> : "-"}</dd>
                <dt>{t("office.agent.queued")}</dt><dd>{agent.queued}</dd>
              </dl>
            )}
            {agent && <button type="button" onClick={() => setSelected(null)}>{t("office.agent.clear")}</button>}
          </div>
        </div>
      )}
    </main>
  );
}
