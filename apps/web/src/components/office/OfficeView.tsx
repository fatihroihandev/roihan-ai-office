"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Component, useCallback, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import type { Dashboard } from "@/lib/dashboardApi";
import { chooseMode, isModePref, layoutAvatars, ROOM_ORDER, type Capabilities, type ModePref, type RoomId } from "@/lib/office/model";
import { Office2D } from "@/components/office/Office2D";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const Office3D = dynamic(() => import("@/components/office/Office3D"), { ssr: false, loading: () => null });

// Kemampuan perangkat dan preferensi dibaca lewat useSyncExternalStore (aman untuk SSR, tanpa setState di effect).
const SERVER_CAPS: Capabilities = { webgl: false, reducedMotion: false };
let cachedCaps: Capabilities | null = null;

function detectCaps(): Capabilities {
  if (cachedCaps) return cachedCaps;
  let webgl = false;
  try {
    const c = document.createElement("canvas");
    webgl = !!(c.getContext("webgl2") ?? c.getContext("webgl"));
  } catch {
    webgl = false;
  }
  let reducedMotion = false;
  try {
    reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    reducedMotion = false;
  }
  cachedCaps = { webgl, reducedMotion };
  return cachedCaps;
}

const PREF_KEY = "roihan.office.mode";
const prefListeners = new Set<() => void>();
let memoryPref: ModePref | null = null;

function readPref(): ModePref {
  if (memoryPref) return memoryPref;
  try {
    const v = window.localStorage.getItem(PREF_KEY);
    return isModePref(v) ? v : "auto";
  } catch {
    return "auto";
  }
}

function writePref(v: ModePref) {
  memoryPref = v; // juga berlaku jika penyimpanan browser tidak tersedia
  try {
    window.localStorage.setItem(PREF_KEY, v);
  } catch {
    /* hanya berlaku selama sesi */
  }
  prefListeners.forEach((l) => l());
}

const subscribePref = (cb: () => void) => {
  prefListeners.add(cb);
  return () => void prefListeners.delete(cb);
};

class Boundary extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function OfficeView({ data, selected, onSelect }: { data: Dashboard; selected: string | null; onSelect: (role: string) => void }) {
  const { t } = useLanguage();
  const caps = useSyncExternalStore(() => () => undefined, detectCaps, () => SERVER_CAPS);
  const pref = useSyncExternalStore(subscribePref, readPref, () => "auto" as ModePref);
  const [failed, setFailed] = useState(false);
  const onFail = useCallback(() => setFailed(true), []);
  const mode = failed ? "2d" : chooseMode(pref, caps);
  const avatars = useMemo(() => layoutAvatars(data.agents), [data.agents]);
  const roomLabels = useMemo(
    () => Object.fromEntries(ROOM_ORDER.map((r) => [r, t(`office.room.${r}` as MessageKey)])) as Record<RoomId, string>,
    [t],
  );
  const problems = (data.tasks.failed ?? 0) + (data.tasks.blocked ?? 0);
  const hologram = [
    { text: `${t("office.stat.approvals")}: ${data.approvals_pending}`, color: data.approvals_pending > 0 ? "#ffb020" : "#39ff88" },
    { text: `${t("office.stat.activeTasks")}: ${(data.tasks.queued ?? 0) + (data.tasks.running ?? 0) + (data.tasks.pending_approval ?? 0)}`, color: "#00e5ff" },
    { text: `${t("office.stat.problems")}: ${problems}`, color: problems > 0 ? "#ff3860" : "#39ff88" },
  ];

  return (
    <section className="card" aria-label={t("office.title")}>
      <div className="row">
        <h3 style={{ margin: 0 }}>{t("office.title")}</h3>
        <div className="actions" role="group" aria-label={t("office.mode")}>
          {(["auto", "3d", "2d"] as const).map((m) => (
            <button key={m} type="button" aria-pressed={pref === m} onClick={() => { setFailed(false); writePref(m); }}>{t(`office.mode.${m}` as MessageKey)}</button>
          ))}
        </div>
      </div>
      {!caps.webgl && <p className="small muted">{t("office.noWebgl")}</p>}
      {failed && <p className="small bad" role="alert">{t("office.failed")}</p>}
      {mode === "3d" ? (
        <div className="office3d" data-testid="office-3d">
          <Boundary onError={onFail}>
            <Office3D avatars={avatars} selected={selected} onSelect={onSelect} hologram={hologram} roomLabels={roomLabels} onFail={onFail} />
          </Boundary>
        </div>
      ) : (
        <Office2D avatars={avatars} selected={selected} onSelect={onSelect} />
      )}
      <p className="small muted">{t("office.legend")} <Link href="/tasks">{t("nav.tasks")}</Link></p>
    </section>
  );
}
