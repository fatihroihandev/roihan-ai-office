import { apiFetch } from "@/lib/api";

export type Day = { date: string; created: number; completed: number; failed: number };
export type ProjectRow = {
  id: string; name: string; total: number; percent: number | null; current: string | null;
  counts: Record<string, number>;
};
export type WorkloadRow = { role: string; running: number; queued: number; blocked: number; completed_7d: number; failed_7d: number };
export type Hour = { hour: string; calls: number; tokens: number; errors: number };
export type FunnelStage = { stage: string; now: number; reached: number };
export type ActivityItem = {
  seq: number; type: string; to_status: string | null; actor: string; reason: string | null; at: string;
  task_id: string; title: string | null; role: string | null; project: string | null;
};
export type Insights = {
  generated_at: string;
  days: number;
  throughput: Day[];
  projects: ProjectRow[];
  workload: WorkloadRow[];
  quality: { finished_7d: number; success_rate_7d: number | null; avg_minutes: number | null };
  ai_hourly: Hour[];
  funnel: { stages: FunnelStage[]; out: Record<string, number>; note: string };
  activity: ActivityItem[];
};

export const insightsApi = { get: (days = 14) => apiFetch<Insights>(`/api/dashboard/insights?days=${days}`) };
