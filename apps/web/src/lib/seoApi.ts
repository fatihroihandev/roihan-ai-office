import { apiFetch } from "@/lib/api";

export type Severity = "critical" | "warning" | "info";
export type Finding = { id: string; severity: Severity; message: string; recommendation: string; evidence: string };
export type AuditData = {
  url: string; findings: Finding[]; counts: Record<Severity, number>; not_checked: string[];
  page: { title: string; description: string; h1: number; images: number; internal_links: number };
};
export type KeywordItem = {
  keyword: string; intent: string; priority: string; rationale: string; volume: number | null; competition: string | null;
  data_available: boolean; flagged_claims: string[];
};
export type BriefData = { title_options: string[]; search_intent: string; outline: { heading: string; points: string[] }[]; faq: string[]; internal_links: string[]; avoid_claims: string[] };
export type AnalysisData = { kpis: Kpis; observations: string[] };

export type Artifact = {
  id: string; kind: "audit" | "keywords" | "brief" | "analysis"; title: string; summary: string; task_id: string | null; created_at: string;
  verified_count: number; unverified_count: number; handed_off_to: string | null;
  data?: AuditData & { site_id?: string } & { items?: KeywordItem[] } & Partial<BriefData> & Partial<AnalysisData>;
};

export type Kpis = {
  organic: { impressions: number | null; clicks: number | null; ctr: number | null; avg_position: number | null; organic_sessions: number | null; page_conversions: number | null };
  leads: { total: number; qualified: number; inbound: number };
  funnel: { lead_to_meeting_rate: number | null; opportunity_conversion_rate: number | null; win_rate: number | null; avg_hours_to_first_interaction: number | null };
  money: { cost_idr: number | null; revenue_idr: number | null; roi: number | null };
  notes: string[];
};

export type SiteInfo = {
  id: string; name: string; url: string; project_id: string; language: string; status: string;
  last_audit: { id: string; created_at: string; counts: Record<Severity, number> | null } | null;
  pages?: { path: string; url: string; bytes: number }[]; has_robots?: boolean; has_sitemap?: boolean;
};

export const SEO_METRICS = ["impressions", "clicks", "organic_sessions", "conversions", "position"] as const;

const post = (body?: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
type Queued = { task_id: string; project_id: string; status: string };

export const seoApi = {
  sites: () => apiFetch<SiteInfo[]>("/api/marketing/seo/sites"),
  site: (id: string) => apiFetch<SiteInfo>(`/api/marketing/seo/sites/${id}`),
  siteAudit: (id: string) => apiFetch<Queued>(`/api/marketing/seo/sites/${id}/tasks/audit`, post()),
  siteKeywords: (id: string, d: { topic?: string; material?: string }) => apiFetch<Queued>(`/api/marketing/seo/sites/${id}/tasks/keywords`, post(d)),
  siteBrief: (id: string, d: { topic?: string; material?: string }) => apiFetch<Queued>(`/api/marketing/seo/sites/${id}/tasks/brief`, post(d)),
  kpis: () => apiFetch<Kpis>("/api/marketing/seo/kpis"),
  artifacts: () => apiFetch<Artifact[]>("/api/marketing/seo/artifacts"),
  artifact: (id: string) => apiFetch<Artifact>(`/api/marketing/seo/artifacts/${id}`),
  audit: (d: { url: string; html: string; robots_txt?: string; sitemap_xml?: string }) => apiFetch<Queued>("/api/marketing/seo/tasks/audit", post(d)),
  keywords: (d: { topic: string; material: string; product_id?: string }) => apiFetch<Queued>("/api/marketing/seo/tasks/keywords", post(d)),
  brief: (d: { topic: string; keyword?: string; material?: string; product_id?: string }) => apiFetch<Queued>("/api/marketing/seo/tasks/brief", post(d)),
  analysis: () => apiFetch<Queued>("/api/marketing/seo/tasks/analysis", post()),
  metric: (d: { metric: string; value: number; period: string; page?: string }) => apiFetch<{ id: string }>("/api/marketing/seo/metrics", post(d)),
  handoff: (id: string, project_id?: string) => apiFetch<{ task_id: string }>(`/api/marketing/seo/artifacts/${id}/handoff`, post({ project_id: project_id || null })),
};
