import { apiFetch } from "@/lib/api";
import type { AgentSnapshot } from "@/lib/office/model";

export type NeedsDecision = { kind: "approval" | "task_blocked" | "task_failed"; id: string; title: string; href: string; risk?: string; reason?: string | null };

export type Dashboard = {
  generated_at: string;
  projects_active: number;
  tasks: Record<string, number>;
  approvals_pending: number;
  needs_decision: NeedsDecision[];
  marketing: {
    leads_total: number; by_status: Record<string, number>; opportunities_open: number; content_ready: number; outreach_ready: number;
    outbox_waiting: number; retention_due: number;
  };
  ai: { calls_24h: number; errors_24h: number; blocked_24h: number; paid_calls_24h: number; tokens_24h: number; paid_providers_enabled: boolean };
  worker: { enabled: boolean; running: boolean; current_task_id: string | null };
  agents: AgentSnapshot[];
};

export const dashboardApi = { get: () => apiFetch<Dashboard>("/api/dashboard") };
