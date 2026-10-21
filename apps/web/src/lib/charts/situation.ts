// Ringkasan situasi kantor dalam satu kalimat, dihitung deterministik dari potret backend (tidak ada teks karangan).
import type { Dashboard } from "@/lib/dashboardApi";
import type { Insights } from "@/lib/insightsApi";
import { poseOf } from "../office/model";

export type SituationLevel = "idle" | "busy" | "wait" | "alert";
export type SituationLine = { key: string; params: Record<string, string | number> };
export type Situation = { level: SituationLevel; headline: SituationLine; details: SituationLine[] };

export function situation(d: Dashboard, ins: Insights | null): Situation {
  const running = d.tasks.running ?? 0;
  const problems = (d.tasks.failed ?? 0) + (d.tasks.blocked ?? 0);
  const working = d.agents.filter((a) => poseOf(a.status) === "working").length;
  const level: SituationLevel = problems > 0 ? "alert" : d.approvals_pending > 0 ? "wait" : running > 0 ? "busy" : "idle";
  const headline: SituationLine =
    level === "alert" ? { key: "sit.alert", params: { n: problems } }
    : level === "wait" ? { key: "sit.wait", params: { n: d.approvals_pending } }
    : level === "busy" ? { key: "sit.busy", params: { r: running, a: working } }
    : { key: "sit.idle", params: {} };

  const details: SituationLine[] = [];
  if (level === "alert" && d.approvals_pending > 0) details.push({ key: "sit.d.approvals", params: { n: d.approvals_pending } });
  if (level !== "idle" && running > 0 && level !== "busy") details.push({ key: "sit.d.running", params: { r: running, a: working } });
  const lead = ins?.projects.find((p) => p.percent !== null);
  if (lead) details.push({ key: "sit.d.project", params: { name: lead.name, pct: lead.percent ?? 0, done: lead.counts.completed ?? 0, total: lead.total } });
  if (d.marketing.outbox_waiting > 0) details.push({ key: "sit.d.outbox", params: { n: d.marketing.outbox_waiting } });
  if (ins && ins.quality.success_rate_7d !== null) details.push({ key: "sit.d.quality", params: { pct: Math.round(ins.quality.success_rate_7d * 100), n: ins.quality.finished_7d } });
  return { level, headline, details };
}
