import { apiFetch } from "@/lib/api";

export type LeadStatus = "new" | "qualified" | "contacted" | "meeting" | "opportunity" | "won" | "lost" | "disqualified" | "do_not_contact";
export const PIPELINE: LeadStatus[] = ["new", "qualified", "contacted", "meeting", "opportunity", "won", "lost", "disqualified", "do_not_contact"];
// Cermin dari LEAD_TRANSITIONS di backend (hanya yang dapat diubah langsung); backend tetap penentu akhir.
export const NEXT_LEAD: Record<string, LeadStatus[]> = {
  new: ["qualified", "disqualified"],
  qualified: ["contacted", "disqualified"],
  contacted: ["meeting", "disqualified"],
  meeting: ["disqualified"],
  disqualified: ["new"],
};
export const NEXT_STAGE: Record<string, string[]> = {
  qualification: ["proposal", "lost"],
  proposal: ["negotiation", "won", "lost"],
  negotiation: ["won", "lost"],
};
export const SOURCE_TYPES = ["public_website", "public_registry", "referral", "inbound", "event", "manual"] as const;
export const INTERACTION_KINDS = ["note", "email_out", "email_in", "call", "meeting"] as const;

export type ScoreRow = { factor: string; points: number; max: number; note: string };
export type Contact = { name: string | null; title: string | null; email: string | null; phone: string | null; masked: boolean };
export type Interaction = { id: string; kind: string; occurred_at: string; summary: string; recorded_by: string };
export type Requirement = { id: string; text: string; priority: string; recorded_by: string };
export type Opportunity = {
  id: string; lead_id: string; title: string; stage: string; value_estimate_idr: number | null; won_value_idr: number | null;
  summary: string | null; outcome_reason: string | null; requirements: Requirement[];
};
export type Finding = { type: string; severity: string; detail: string; match: string };
export type Outreach = {
  id: string; lead_id: string; subject: string; body: string; status: string; claim_check: { ok: boolean; findings: Finding[] } | null;
  sent_at: string | null; task_id: string | null;
};
export type Lead = {
  id: string; status: LeadStatus; score: number | null; score_breakdown: ScoreRow[] | null; basis: string; owner: string;
  do_not_contact: boolean; anonymized: boolean; forwarded_at: string | null; collected_at: string; contact: Contact;
  company: { id: string; name: string; industry: string | null; size_band: string; city: string | null; website: string | null };
  source: { id: string; type: string; url: string | null; title: string | null; collected_at: string; collected_by: string; method: string };
  interactions?: Interaction[]; outreach?: Outreach[]; opportunities?: Opportunity[];
  outreach_task?: { task_id: string };
};
export type Policy = {
  allowed_sources: { type: string; label: string; needs_url: boolean; basis: string }[];
  forbidden_sources: { type: string; reason: string }[];
  retention: { no_interaction_days: number; after_last_interaction_days: number; auto_apply: boolean; action: string };
  min_score_for_sales: number;
};
export type Analytics = {
  leads_total: number; by_status: Record<string, number>; by_source: Record<string, number>; lead_to_meeting_rate: number | null;
  opportunities_open: number; win_rate: number | null; revenue_recorded_idr: number | null; customer_acquisition_cost_idr: number | null;
};
export type Research = { id: string; topic: string; summary: string; items: { statement: string; basis: string; verified: boolean; evidence_quote: string }[]; verified_count: number; unverified_count: number };
export type Retention = { policy: Policy["retention"]; due: { lead_id: string; reason: string }[] };
export type QueuedTask = { task_id: string; project_id: string; status: string };

export type LeadInput = {
  company: { name: string; industry?: string; size_band?: string };
  contact?: { name?: string; title?: string; email?: string; phone?: string };
  source: { source_type: string; url?: string };
};

const body = (method: string, data?: unknown): RequestInit => ({
  method,
  ...(data !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) } : {}),
});
const clean = <T extends Record<string, unknown>>(o: T) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v !== undefined && v !== null));

export const marketingApi = {
  policy: () => apiFetch<Policy>("/api/marketing/policy"),
  analytics: () => apiFetch<Analytics>("/api/marketing/analytics"),
  leads: () => apiFetch<Lead[]>("/api/marketing/leads"),
  lead: (id: string, reveal = false) => apiFetch<Lead>(`/api/marketing/leads/${id}${reveal ? "?reveal=true" : ""}`),
  createLead: (data: LeadInput) =>
    apiFetch<Lead>("/api/marketing/leads", body("POST", { ...data, company: clean(data.company), contact: data.contact ? clean(data.contact) : undefined, source: clean(data.source) })),
  setStatus: (id: string, status: string, reason?: string, override_reason?: string) =>
    apiFetch<Lead>(`/api/marketing/leads/${id}/status`, body("POST", clean({ status, reason, override_reason }))),
  forward: (id: string, override_reason?: string, draft_outreach_product_id?: string) =>
    apiFetch<Lead>(`/api/marketing/leads/${id}/forward`, body("POST", clean({ override_reason, draft_outreach_product_id }))),
  optOut: (id: string, reason?: string) => apiFetch<Lead>(`/api/marketing/leads/${id}/opt-out`, body("POST", clean({ reason }))),
  erase: (id: string, reason?: string) => apiFetch<Lead>(`/api/marketing/leads/${id}/erase`, body("POST", clean({ reason }))),
  interact: (id: string, kind: string, summary: string) => apiFetch<Interaction>(`/api/marketing/leads/${id}/interactions`, body("POST", { kind, summary })),
  convert: (id: string, title: string, value?: number) =>
    apiFetch<Opportunity>(`/api/marketing/leads/${id}/convert`, body("POST", clean({ title, value_estimate_idr: value }))),
  stage: (oid: string, stage: string, reason?: string, won_value_idr?: number) =>
    apiFetch<Opportunity>(`/api/marketing/opportunities/${oid}/stage`, body("POST", clean({ stage, reason, won_value_idr }))),
  requirement: (oid: string, text: string) => apiFetch<Opportunity>(`/api/marketing/opportunities/${oid}/requirements`, body("POST", { text })),
  opportunities: () => apiFetch<Opportunity[]>("/api/marketing/opportunities"),
  outreach: () => apiFetch<Outreach[]>("/api/marketing/outreach"),
  markSent: (id: string) => apiFetch<Outreach>(`/api/marketing/outreach/${id}/mark-sent`, body("POST", {})),
  cancelOutreach: (id: string) => apiFetch<Outreach>(`/api/marketing/outreach/${id}/cancel`, body("POST", {})),
  research: () => apiFetch<Research[]>("/api/marketing/research"),
  runResearch: (topic: string, material: string, product_id?: string) =>
    apiFetch<QueuedTask>("/api/marketing/tasks/research", body("POST", clean({ topic, material, product_id }))),
  runIntake: (source: { source_type: string; url?: string; title?: string }, raw_text: string) =>
    apiFetch<QueuedTask>("/api/marketing/tasks/intake", body("POST", { source: clean(source), raw_text })),
  suppression: () => apiFetch<{ id: string }[]>("/api/marketing/suppression"),
  retention: () => apiFetch<Retention>("/api/marketing/retention"),
  runRetention: () => apiFetch<{ anonymized: number }>("/api/marketing/retention/run?dry_run=false", body("POST", {})),
};
