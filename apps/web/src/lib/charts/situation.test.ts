import { describe, expect, it } from "vitest";
import type { Dashboard } from "@/lib/dashboardApi";
import type { Insights } from "@/lib/insightsApi";
import { situation } from "./situation";

const dash = (over: Partial<Dashboard> & { tasks?: Record<string, number> } = {}): Dashboard => ({
  generated_at: "", projects_active: 1, approvals_pending: 0, needs_decision: [],
  agents: [{ role: "developer", department: "engineering", status: "working", queued: 0, current_task_id: null, current_task_title: null },
           { role: "qa", department: "engineering", status: "idle", queued: 0, current_task_id: null, current_task_title: null }],
  marketing: { leads_total: 0, by_status: {}, opportunities_open: 0, content_ready: 0, outreach_ready: 0, outbox_waiting: 0, retention_due: 0 },
  ai: { calls_24h: 0, errors_24h: 0, blocked_24h: 0, paid_calls_24h: 0, tokens_24h: 0, paid_providers_enabled: false },
  worker: { enabled: true, running: true, current_task_id: null }, ...over, tasks: { running: 0, failed: 0, blocked: 0, ...(over.tasks ?? {}) },
});
const ins = (): Insights => ({
  generated_at: "", days: 14, throughput: [], workload: [], ai_hourly: [], activity: [], funnel: { stages: [], out: {}, note: "" },
  quality: { finished_7d: 8, success_rate_7d: 0.75, avg_minutes: 4 },
  projects: [{ id: "p", name: "Kalkulator", total: 4, percent: 50, current: null, counts: { completed: 2 } }],
});

describe("situasi kantor", () => {
  it("tenang jika tidak ada task berjalan", () => {
    expect(situation(dash(), null)).toEqual({ level: "idle", headline: { key: "sit.idle", params: {} }, details: [] });
  });
  it("aktif: menyebut jumlah task dan agent yang benar-benar bekerja", () => {
    const s = situation(dash({ tasks: { running: 2 } }), null);
    expect(s.level).toBe("busy");
    expect(s.headline).toEqual({ key: "sit.busy", params: { r: 2, a: 1 } });
  });
  it("prioritas: masalah mengalahkan approval, approval mengalahkan aktif", () => {
    expect(situation(dash({ tasks: { running: 1, failed: 1 }, approvals_pending: 2 }), null).level).toBe("alert");
    expect(situation(dash({ tasks: { running: 1 }, approvals_pending: 2 }), null).level).toBe("wait");
  });
  it("detail: progres proyek terdepan, kualitas 7 hari, dan kotak keluar", () => {
    const d = dash({ tasks: { running: 1 }, marketing: { ...dash().marketing, outbox_waiting: 3 } });
    const keys = situation(d, ins()).details.map((x) => x.key);
    expect(keys).toEqual(["sit.d.project", "sit.d.outbox", "sit.d.quality"]);
    expect(situation(d, ins()).details[0].params).toEqual({ name: "Kalkulator", pct: 50, done: 2, total: 4 });
  });
  it("kualitas yang belum diketahui tidak ditampilkan sebagai 0%", () => {
    const i = ins();
    i.quality.success_rate_7d = null;
    expect(situation(dash(), i).details.map((x) => x.key)).toEqual(["sit.d.project"]);
  });
});
