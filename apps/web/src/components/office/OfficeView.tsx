"use client";

import dynamic from "next/dynamic";
import { Component, useCallback, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import type { Dashboard } from "@/lib/dashboardApi";
import { chooseMode, isModePref, layoutAvatars, ROOM_ORDER, type Capabilities, type ModePref, type RoomId } from "@/lib/office/model";
import type { Nearby } from "@/lib/office/walk";
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

// ---- kualitas efek (bayangan dan bloom): tinggi secara bawaan, rendah jika perangkat meminta gerak berkurang
type Quality = "high" | "low";
const QUALITY_KEY = "roihan.office.quality";
const qualityListeners = new Set<() => void>();
let memoryQuality: Quality | null = null;

function readQuality(): Quality {
  if (memoryQuality) return memoryQuality;
  try {
    const v = window.localStorage.getItem(QUALITY_KEY);
    if (v === "high" || v === "low") return v;
  } catch {
    /* penyimpanan tidak tersedia */
  }
  return detectCaps().reducedMotion ? "low" : "high";
}

export function useOfficeQuality(): [Quality, (q: Quality) => void] {
  const q = useSyncExternalStore(
    (cb) => {
      qualityListeners.add(cb);
      return () => void qualityListeners.delete(cb);
    },
    readQuality,
    () => "high" as Quality,
  );
  const set = useCallback((v: Quality) => {
    memoryQuality = v;
    try {
      window.localStorage.setItem(QUALITY_KEY, v);
    } catch {
      /* hanya berlaku selama sesi */
    }
    qualityListeners.forEach((l) => l());
  }, []);
  return [q, set];
}

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

/** Mode tampilan (3D atau fallback 2D) beserta kemampuan perangkat dan pilihan pengguna. */
export function useOfficeMode() {
  const caps = useSyncExternalStore(() => () => undefined, detectCaps, () => SERVER_CAPS);
  const pref = useSyncExternalStore(subscribePref, readPref, () => "auto" as ModePref);
  const [failed, setFailed] = useState(false);
  const onFail = useCallback(() => setFailed(true), []);
  const setPref = useCallback((v: ModePref) => {
    setFailed(false);
    writePref(v);
  }, []);
  const mode: "3d" | "2d" = failed ? "2d" : chooseMode(pref, caps);
  return { mode, pref, setPref, caps, failed, onFail };
}

export function ModeControls({ pref, setPref }: { pref: ModePref; setPref: (v: ModePref) => void }) {
  const { t } = useLanguage();
  return (
    <div className="actions" role="group" aria-label={t("office.mode")}>
      {(["auto", "3d", "2d"] as const).map((m) => (
        <button key={m} type="button" aria-pressed={pref === m} onClick={() => setPref(m)}>{t(`office.mode.${m}` as MessageKey)}</button>
      ))}
    </div>
  );
}

/** Area adegan: 3D memenuhi induknya; 2D menjadi kisi kartu biasa. */
export type WalkProps = {
  walking: boolean; start?: [number, number]; view: "third" | "first"; quality: Quality; onSlow?: () => void;
  onNearby: (n: Nearby | null) => void; onInteract: (n: Nearby) => void; onToggleView: () => void; onExit: () => void;
};

export function OfficeScene({ data, mode, onFail, selected, onSelect, walk }: {
  data: Dashboard; mode: "3d" | "2d"; onFail: () => void; selected: string | null; onSelect: (role: string) => void; walk: WalkProps;
}) {
  const { t } = useLanguage();
  const avatars = useMemo(() => layoutAvatars(data.agents), [data.agents]);
  const roomLabels = useMemo(
    () => Object.fromEntries(ROOM_ORDER.map((r) => [r, t(`office.room.${r}` as MessageKey)])) as Record<RoomId, string>,
    [t],
  );
  const roleLabels = useMemo(() => Object.fromEntries(data.agents.map((a) => [a.role, t(`role.${a.role}` as MessageKey)])), [data.agents, t]);
  const statusLabels = useMemo(() => Object.fromEntries(data.agents.map((a) => [a.status, t(`agent.${a.status}` as MessageKey)])), [data.agents, t]);
  const problems = (data.tasks.failed ?? 0) + (data.tasks.blocked ?? 0);
  const hologram = [
    { text: `${t("office.stat.approvals")}: ${data.approvals_pending}`, color: data.approvals_pending > 0 ? "#ffb020" : "#39ff88" },
    { text: `${t("office.stat.activeTasks")}: ${(data.tasks.queued ?? 0) + (data.tasks.running ?? 0) + (data.tasks.pending_approval ?? 0)}`, color: "#00e5ff" },
    { text: `${t("office.stat.problems")}: ${problems}`, color: problems > 0 ? "#ff3860" : "#39ff88" },
  ];
  if (mode === "2d") return <Office2D avatars={avatars} selected={selected} onSelect={onSelect} />;
  return (
    <div className="scene" data-testid="office-3d">
      <Boundary onError={onFail}>
        <Office3D
          avatars={avatars} selected={selected} onSelect={onSelect} hologram={hologram}
          roomLabels={roomLabels} roleLabels={roleLabels} statusLabels={statusLabels} onFail={onFail} quality={walk.quality} onSlow={walk.onSlow}
          ceo={{ walking: walk.walking, start: walk.start, view: walk.view, label: t("office.ceo"), onNearby: walk.onNearby, onInteract: walk.onInteract, onToggleView: walk.onToggleView, onExit: walk.onExit }}
        />
      </Boundary>
    </div>
  );
}
