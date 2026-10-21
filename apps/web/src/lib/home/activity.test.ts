import { describe, expect, it } from "vitest";
import type { Dashboard } from "@/lib/dashboardApi";
import { heroActivity, TONE_COLOR } from "./activity";

const base = (over: Partial<Dashboard> & { tasks?: Record<string, number> } = {}): Dashboard => ({
  generated_at: "", projects_active: 0, approvals_pending: 0, needs_decision: [], agents: [],
  marketing: { leads_total: 0, by_status: {}, opportunities_open: 0, content_ready: 0, outreach_ready: 0, outbox_waiting: 0, retention_due: 0 },
  ai: { calls_24h: 0, errors_24h: 0, blocked_24h: 0, paid_calls_24h: 0, tokens_24h: 0, paid_providers_enabled: false },
  worker: { enabled: true, running: true, current_task_id: null },
  ...over,
  tasks: { running: 0, failed: 0, blocked: 0, ...(over.tasks ?? {}) },
});

describe("aktivitas hero mengikuti backend", () => {
  it("tanpa data: tenang (tidak disimulasikan)", () => {
    expect(heroActivity(null)).toEqual({ level: 0, tone: "idle", color: TONE_COLOR.idle, running: 0 });
  });
  it("tingkat aktivitas naik dengan jumlah task berjalan", () => {
    expect([0, 1, 2, 3, 4, 9].map((n) => heroActivity(base({ tasks: { running: n } })).level)).toEqual([0, 1, 2, 2, 3, 3]);
  });
  it("prioritas warna: masalah > approval menunggu > bekerja > tenang", () => {
    expect(heroActivity(base({ tasks: { running: 2, failed: 1 }, approvals_pending: 3 })).tone).toBe("alert");
    expect(heroActivity(base({ tasks: { running: 2 }, approvals_pending: 1 })).tone).toBe("wait");
    expect(heroActivity(base({ tasks: { running: 2 } })).tone).toBe("busy");
    expect(heroActivity(base()).tone).toBe("idle");
    expect(heroActivity(base({ tasks: { blocked: 1 } })).tone).toBe("alert");
  });
});
