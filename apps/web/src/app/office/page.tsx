"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";
import { DashboardPanel } from "@/components/office/DashboardPanel";
import { ModeControls, OfficeScene, useOfficeMode, useOfficeQuality } from "@/components/office/OfficeView";
import { useOfficeData } from "@/lib/office/useOfficeData";
import type { Nearby } from "@/lib/office/walk";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function OfficePage() {
  const { t } = useLanguage();
  const router = useRouter();
  const params = useSearchParams(); // ?walk=1 langsung masuk mode jalan; ?view=first orang pertama
  const label = (key: string) => t(key as MessageKey);
  const { data, stale, connected, updatedAt } = useOfficeData();
  const { mode, pref, setPref, caps, failed, onFail } = useOfficeMode();
  const [quality, setQuality] = useOfficeQuality();
  const [selected, setSelected] = useState<string | null>(null);
  const [walking, setWalking] = useState(params.get("walk") === "1");
  const [panel, setPanel] = useState(params.get("walk") !== "1");
  const [view, setView] = useState<"third" | "first">(params.get("view") === "first" ? "first" : "third");
  const [nearby, setNearby] = useState<Nearby | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const startParam = params.get("pos")?.split(",").map(Number); // ?pos=x,z memindahkan CEO langsung ke titik itu (tautan/uji)
  const start = startParam && startParam.length === 2 && startParam.every(Number.isFinite) ? ([startParam[0], startParam[1]] as [number, number]) : undefined;
  const agent = data?.agents.find((a) => a.role === selected) ?? null;
  const walkOn = walking && mode === "3d";

  const onToggleView = useCallback(() => setView((v) => (v === "third" ? "first" : "third")), []);
  const onExit = useCallback(() => {
    setWalking(false);
    setNearby(null);
  }, []);
  const onInteract = useCallback((n: Nearby) => {
    if (n.kind === "agent") setSelected(n.role);
    else router.push(n.href);
  }, [router]);

  const toggleFullscreen = () => {
    const el = stage.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  };

  const prompt = nearby
    ? nearby.kind === "agent" ? t("office.walk.talk").replace("{name}", label(`role.${nearby.role}`)) : label(`office.walk.place.${nearby.id}`)
    : null;

  return (
    <PageTransition>
<main data-office>
      <div className="office-title">
        <h2>{t("office.heading")}</h2>
        <p className="muted small">{t("office.hint")}</p>
      </div>
      {!data && !stale && <p>{t("common.loading")}</p>}
      {!data && stale && <p className="bad" role="alert">{t("office.unavailable")}</p>}
      {data && (
        <div className="stage" data-mode={mode} data-walk={walkOn ? "on" : "off"} data-view={view} ref={stage}>
          <OfficeScene
            data={data} mode={mode} onFail={onFail} selected={selected} onSelect={setSelected}
            walk={{ walking: walkOn, start, view, quality, onNearby: setNearby, onInteract, onToggleView, onExit }}
          />

          <div className="hud hud-tl glass" role="status">
            <span className="badge" data-task={connected ? "completed" : "failed"}>{connected ? t("office.live") : t("office.polling")}</span>
            {stale && <span className="bad small"> {t("office.stale")}{updatedAt ? ` (${new Date(updatedAt).toLocaleTimeString()})` : ""}</span>}
            {!caps.webgl && <span className="small muted"> {t("office.noWebgl")}</span>}
            {failed && <span className="small bad" role="alert"> {t("office.failed")}</span>}
          </div>

          <div className="hud hud-tr glass">
            {mode === "3d" && (
              <button type="button" className={walkOn ? "danger" : "primary-btn"} onClick={() => { if (walkOn) onExit(); else { setWalking(true); setPanel(false); } }}>
                {walkOn ? t("office.walk.exit") : t("office.walk.enter")}
              </button>
            )}
            <ModeControls pref={pref} setPref={setPref} />
            {mode === "3d" && (
              <button type="button" aria-pressed={quality === "high"} onClick={() => setQuality(quality === "high" ? "low" : "high")}>
                {t("office.quality")}: {t(quality === "high" ? "office.quality.high" : "office.quality.low")}
              </button>
            )}
            <button type="button" aria-pressed={panel} onClick={() => setPanel((p) => !p)}>{t("office.panel")}</button>
            <button type="button" onClick={toggleFullscreen}>{t("office.fullscreen")}</button>
          </div>

          {panel && !walkOn && (
            <aside className="hud hud-right glass">
              <DashboardPanel d={data} />
            </aside>
          )}

          {walkOn && (
            <>
              {view === "first" && <div className="crosshair" aria-hidden="true" />}
              <div className="hud hud-walk glass" role="note">
                <span className="small">{t("office.walk.help")}</span>
                <span className="small muted"> · {t(view === "first" ? "office.walk.view.first" : "office.walk.view.third")}</span>
              </div>
              {prompt && <div className="hud hud-prompt glass" role="status"><kbd>E</kbd> {prompt.replace(/^E: /, "")}</div>}
            </>
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
      <p className="small muted credits">{t("office.credits")}</p>
    </main>
</PageTransition>
  );
}
