"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { availableAction, pollInterval, resolutionsFor } from "@/lib/office/power";
import { powerApi, type PowerSnapshot, type Resolution } from "@/lib/powerApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

/** Status daya dari backend (sumber kebenaran). Polling cepat saat transisi agar progres terlihat; UI tidak menebak hasilnya. */
export function usePowerStatus(): { power: PowerSnapshot | null; failed: boolean; refresh: () => void } {
  const [power, setPower] = useState<PowerSnapshot | null>(null);
  const [failed, setFailed] = useState(false);
  const tick = useRef<() => void>(() => undefined);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = () => {
      clearTimeout(timer);
      powerApi.status().then(
        (s) => {
          if (cancelled) return;
          setPower(s);
          setFailed(false);
          timer = setTimeout(run, pollInterval(s.state));
        },
        () => {
          if (cancelled) return;
          setFailed(true);
          timer = setTimeout(run, 8000);
        },
      );
    };
    tick.current = run;
    run();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  const refresh = useCallback(() => tick.current(), []);
  return { power, failed, refresh };
}

/** Tombol OFF/ON beserta lencana status. Aksi hanya dianggap berhasil setelah backend melaporkan status barunya. */
export function PowerControl({ power, failed, refresh }: { power: PowerSnapshot | null; failed: boolean; refresh: () => void }) {
  const { t } = useLanguage();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const action = power ? availableAction(power) : null;

  async function send(kind: "off" | "on") {
    setBusy(true);
    setError(null);
    setConfirming(false);
    try {
      await powerApi[kind]();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("power.error"));
    } finally {
      setBusy(false);
      refresh();
    }
  }

  return (
    <div className="power-ctl" role="group" aria-label={t("power.label")}>
      {power && <span className="power-badge" data-power={power.state} role="status">{t(`power.state.${power.state}` as MessageKey)}</span>}
      {failed && !power && <span className="small bad">{t("power.error")}</span>}
      {action === "off" && !confirming && (
        <button type="button" className="danger" disabled={busy} onClick={() => setConfirming(true)}>{t("power.off")}</button>
      )}
      {action === "off" && confirming && (
        <span className="power-confirm" role="alertdialog" aria-label={t("power.confirm.off")}>
          <span className="small">{t("power.confirm.off")}</span>
          <button type="button" className="danger" disabled={busy} onClick={() => void send("off")}>{t("power.confirm.yes")}</button>
          <button type="button" onClick={() => setConfirming(false)}>{t("power.confirm.no")}</button>
        </span>
      )}
      {action === "on" && <button type="button" className="primary-btn" disabled={busy} onClick={() => void send("on")}>{t("power.on")}</button>}
      {power && action === null && <span className="small muted" aria-live="polite">{t("power.waiting")}</span>}
      {error && <span className="small bad" role="alert">{error}</span>}
    </div>
  );
}

const STEP_KEYS = new Set(["accepted", "scheduler_stopped", "waiting_active_tasks", "saving_checkpoints", "tasks_stopped", "checkpoints_verified", "database_verified",
  "database_validated", "workspaces_validated", "dependencies_validated", "tasks_recovered"]);

/** Spanduk status di kantor: PAUSING/RESUMING menampilkan progres, PAUSED menampilkan ringkasan terakhir, masalah menampilkan aksesnya. */
export function PowerBanner({ power, onOpenPanel }: { power: PowerSnapshot | null; onOpenPanel: () => void }) {
  const { t } = useLanguage();
  if (!power || power.state === "RUNNING") return null;
  const step = power.detail.step && STEP_KEYS.has(power.detail.step) ? t(`power.step.${power.detail.step}` as MessageKey) : null;
  const c = power.counts;
  return (
    <div className="hud hud-power glass" data-power={power.state} role="status" aria-live="polite">
      <strong>{t(`power.state.${power.state}` as MessageKey)}</strong>
      <span className="small"> {t(`power.banner.${power.state}` as MessageKey).replace("{n}", String(power.recovery_required))}</span>
      {(power.state === "PAUSING" || power.state === "RESUMING") && step && <span className="small muted"> · {step}</span>}
      {power.state !== "PAUSING" && power.state !== "RESUMING" && (
        <div className="small muted">
          {t("power.summary").replace("{c}", String(c.completed)).replace("{q}", String(c.queued)).replace("{i}", String(c.interrupted))
            .replace("{f}", String(c.failed_or_blocked)).replace("{k}", String(power.checkpoints_saved))}
        </div>
      )}
      {power.recovery_required > 0 && <button type="button" onClick={onOpenPanel}>{t("power.items")} ({power.recovery_required})</button>}
    </div>
  );
}

/** Item yang butuh keputusan manusia (tugas berisiko terputus, operasi eksternal tak pasti, dsb.) beserta pilihan penyelesaiannya. */
export function PowerPanel({ power, refresh }: { power: PowerSnapshot | null; refresh: () => void }) {
  const { t } = useLanguage();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!power || power.recovery_items.length === 0) return null;

  async function resolve(id: string, r: Resolution) {
    setBusy(id);
    setError(null);
    try {
      await powerApi.resolve(id, r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("power.error"));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  return (
    <>
      <h4>{t("power.items")}</h4>
      <ul className="needs power-items">
        {power.recovery_items.map((i) => (
          <li key={i.id}>
            <span className="badge" data-risk="high">{t(`power.item.kind.${i.kind}` as MessageKey)}</span> <span className="small">{i.reason}</span>
            <div className="actions">
              {resolutionsFor(i.kind).map((r) => (
                <button key={r} type="button" className={r === "cancel" ? "danger tab" : "tab"} disabled={busy === i.id} onClick={() => void resolve(i.id, r)}>
                  {t(`power.resolve.${r}` as MessageKey)}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      {error && <p className="bad small" role="alert">{error}</p>}
    </>
  );
}
