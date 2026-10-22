import { apiFetch } from "@/lib/api";

export type PowerState = "RUNNING" | "PAUSING" | "PAUSED" | "RESUMING" | "RECOVERY_REQUIRED" | "ERROR";

export type RecoveryItem = {
  id: string; task_id: string | null; project_id: string | null; kind: string; reason: string; status: "open" | "resolved";
  created_at: string; resolved_at: string | null; resolution: string | null;
};

export type PowerSnapshot = {
  state: PowerState;
  reason: string | null;
  changed_at: string | null;
  scheduling: boolean;
  detail: { step?: string; status?: string; [k: string]: unknown };
  active_command: { id: string; action: string; status: string; progress: { step: string; status: string }[]; error: string | null } | null;
  counts: { projects_active: number; running: number; queued: number; completed: number; failed_or_blocked: number; interrupted: number; pending_approval: number };
  checkpoints_saved: number;
  last_checkpoint_at: string | null;
  recovery_required: number;
  recovery_items: RecoveryItem[];
};

export type Resolution = "requeue" | "cancel" | "confirmed_done" | "confirmed_not_done" | "acknowledged";

const post = (body?: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });

export const powerApi = {
  status: () => apiFetch<PowerSnapshot>("/api/power"),
  off: () => apiFetch<{ accepted: boolean; already: boolean; state: PowerState }>("/api/power/off", post()),
  on: () => apiFetch<{ accepted: boolean; already: boolean; state: PowerState }>("/api/power/on", post()),
  resolve: (id: string, resolution: Resolution) => apiFetch<RecoveryItem>(`/api/power/recovery/${id}/resolve`, post({ resolution })),
};
