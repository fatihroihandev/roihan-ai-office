// Logika murni Office Power Control di sisi UI. Backend adalah sumber kebenaran: UI hanya menampilkan dan meminta.
import type { PowerSnapshot, PowerState, Resolution } from "../powerApi";

export const TRANSITIONAL: PowerState[] = ["PAUSING", "RESUMING"];

export const isTransitional = (s: PowerState) => TRANSITIONAL.includes(s);

/** OFF tersedia saat sistem menjadwalkan pekerjaan atau perlu dijeda; ON tersedia saat sistem berhenti atau error. */
export function availableAction(p: Pick<PowerSnapshot, "state" | "scheduling">): "off" | "on" | null {
  switch (p.state) {
    case "RUNNING":
      return "off";
    case "RECOVERY_REQUIRED":
      return p.scheduling ? "off" : "on";
    case "PAUSED":
    case "ERROR":
      return "on";
    default:
      return null; // PAUSING / RESUMING: menunggu backend
  }
}

/** Interval polling: cepat saat transisi (progres), lambat saat stabil. */
export const pollInterval = (s: PowerState) => (isTransitional(s) ? 1200 : 8000);

/** Saat PAUSED, avatar tidak boleh tampak bekerja: status kerja ditampilkan sebagai istirahat (kecuali error yang tetap terlihat). */
export function agentsForPower<T extends { status: string }>(agents: T[], state: PowerState | undefined): T[] {
  if (state !== "PAUSED") return agents;
  return agents.map((a) => (a.status === "error" ? a : { ...a, status: "idle" }));
}

const BY_KIND: Record<string, Resolution[]> = {
  risky_task_interrupted: ["requeue", "cancel"],
  external_unknown: ["confirmed_not_done", "confirmed_done"],
  files_missing: ["requeue", "cancel"],
  stop_unconfirmed: ["acknowledged", "requeue", "cancel"],
  checkpoint_invalid: ["requeue", "cancel", "acknowledged"],
  retries_exhausted: ["requeue", "cancel"],
};

export const resolutionsFor = (kind: string): Resolution[] => BY_KIND[kind] ?? ["acknowledged", "cancel"];
