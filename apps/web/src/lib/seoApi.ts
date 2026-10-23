import { apiFetch } from "@/lib/api";

export type Severity = "critical" | "warning" | "info";
export type Finding = { id: string; severity: Severity; message: string; recommendation: string; evidence: string; page?: string };
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

export type SeoKeyword = {
  id: string; campaign_id: string; keyword: string; intent: string; source: "manual" | "ai" | "gsc";
  rationale: string; target_page: string | null; volume: number | null; competition: string | null;
  evidence_quote: string; approval_status: "pending" | "approved" | "rejected"; approved_at: string | null; created_at: string;
};
export type SeoCampaign = {
  id: string; name: string; website_url: string; allowed_domains: string[]; site_id: string | null; project_id: string | null;
  target_country: string | null; target_language: string | null; target_location: string | null; primary_keywords: string[];
  objective: "keyword_rank" | "organic_traffic" | "clicks" | "leads" | "conversions"; target_value: number | null;
  baseline: Record<string, number | null>; baseline_source: string; starts_on: string | null; review_on: string | null;
  api_budget_idr: number; external_budget_idr: number; autonomy: "read_only" | "staging_write" | "approved_production_write";
  approval_policy: Record<string, boolean>; status: "draft" | "auditing" | "planning" | "active" | "paused" | "target_review" | "completed" | "failed" | "archived";
  created_at: string; updated_at: string; keywords?: SeoKeyword[];
  recommendations?: SeoRecommendation[];
  history?: { id: string; kind: string; actor: string; details: Record<string, unknown>; created_at: string }[];
  external_integrations?: { search_console: string; analytics: string };
};
export type SeoRecommendation = {
  id: string; artifact_id: string; finding_id: string; category: string; title: string; severity: Severity;
  evidence: Record<string, string | null>; recommendation: string; impact_basis: string; confidence: string;
  effort: string; risk: string; dependencies: string[]; acceptance_criteria: string[]; verification_method: string;
  priority_order: number; status: "proposed" | "approved" | "rejected" | "in_progress" | "completed"; decision_note: string | null;
  created_at: string;
};

export const SEO_METRICS = ["impressions", "clicks", "organic_sessions", "conversions", "position"] as const;

const post = (body?: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
type Queued = { task_id: string; project_id: string; status: string };

export const seoApi = {
  campaigns: () => apiFetch<SeoCampaign[]>("/api/marketing/seo/campaigns"),
  campaign: (id: string) => apiFetch<SeoCampaign>(`/api/marketing/seo/campaigns/${id}`),
  campaignReport: (id: string) => apiFetch<Record<string, unknown>>(`/api/marketing/seo/campaigns/${id}/report`),
  createCampaign: (data: { name: string; website_url: string; site_id?: string; target_country?: string; target_language?: string; target_location?: string; primary_keywords: string[]; objective: SeoCampaign["objective"]; target_value?: number; baseline?: Record<string, number | null>; baseline_source?: string; starts_on?: string; review_on?: string; api_budget_idr: number; external_budget_idr: number; autonomy: SeoCampaign["autonomy"] }) =>
    apiFetch<SeoCampaign>("/api/marketing/seo/campaigns", post(data)),
  updateCampaignStatus: (id: string, status: SeoCampaign["status"]) => apiFetch<SeoCampaign>(`/api/marketing/seo/campaigns/${id}/status`, post({ status })),
  campaignAudit: (id: string) => apiFetch<Queued>(`/api/marketing/seo/campaigns/${id}/tasks/audit`, post()),
  suggestCampaignKeywords: (id: string, data: { topic?: string; material?: string }) => apiFetch<Queued>(`/api/marketing/seo/campaigns/${id}/tasks/keywords`, post(data)),
  campaignContentPlan: (id: string, data: { keyword_id: string; material?: string }) => apiFetch<Queued>(`/api/marketing/seo/campaigns/${id}/tasks/content-plan`, post(data)),
  addCampaignKeyword: (id: string, data: { keyword: string; intent: string; rationale?: string; target_page?: string }) => apiFetch<SeoKeyword>(`/api/marketing/seo/campaigns/${id}/keywords`, post(data)),
  decideCampaignKeyword: (id: string, keywordId: string, status: SeoKeyword["approval_status"]) => apiFetch<SeoKeyword>(`/api/marketing/seo/campaigns/${id}/keywords/${keywordId}/decision`, post({ status })),
  decideCampaignKeywords: (id: string, keywordIds: string[], status: SeoKeyword["approval_status"]) => apiFetch<SeoKeyword[]>(`/api/marketing/seo/campaigns/${id}/keywords/decisions`, post({ keyword_ids: keywordIds, status })),
  deleteCampaignKeyword: (id: string, keywordId: string) => apiFetch<void>(`/api/marketing/seo/campaigns/${id}/keywords/${keywordId}`, { method: "DELETE" }),
  decideCampaignRecommendation: (id: string, recommendationId: string, status: SeoRecommendation["status"], note?: string) => apiFetch<SeoRecommendation>(`/api/marketing/seo/campaigns/${id}/recommendations/${recommendationId}/decision`, post({ status, note })),
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
