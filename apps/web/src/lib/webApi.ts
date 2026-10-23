import { apiFetch } from "@/lib/api";

export type WebStatus = { enabled: boolean; search_provider?: "brave" | "tavily"; search_available: boolean; api_key_configured: boolean; api_keys_configured?: { brave: boolean; tavily: boolean }; daily_limit: number; used_today: number; remaining_today: number };
export type WebLogRow = { id: string; created_at: string; kind: "search" | "fetch"; target: string; status: string; bytes: number; detail: string | null };
export type SearchHit = { title: string; url: string; snippet: string };
export type WebSource = { url: string; title: string; injection_suspected: boolean };
export type Failure = { url: string; code: string; message: string };
export type ResearchQueued = { task_id: string; sources: WebSource[]; failed: Failure[] };
export type ProspectingQueued = { queued: (WebSource & { task_id: string })[]; skipped: Failure[] };

const send = (method: string, body?: unknown): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });

export const webApi = {
  status: () => apiFetch<WebStatus>("/api/web"),
  update: (d: { enabled?: boolean; daily_limit?: number; web_search_provider?: "brave" | "tavily"; brave_api_key?: string; tavily_api_key?: string; clear_api_key?: boolean }) => apiFetch<WebStatus>("/api/web", send("PATCH", d)),
  requests: () => apiFetch<WebLogRow[]>("/api/web/requests?limit=8"),
  search: (query: string) => apiFetch<{ results: SearchHit[] }>("/api/web/search", send("POST", { query })),
  research: (d: { topic: string; query?: string; max_pages: number; product_id?: string }) => apiFetch<ResearchQueued>("/api/web/tasks/research", send("POST", d)),
  prospecting: (d: { query: string; source_type: string; max_pages: number; product_id?: string }) => apiFetch<ProspectingQueued>("/api/web/tasks/prospecting", send("POST", d)),
};
