import { apiFetch } from "@/lib/api";

export type ProviderHealth = { status: "up" | "down"; latency_ms: number | null; version: string | null; error_kind: string | null };

export type Provider = {
  name: string;
  kind: "local" | "cloud";
  is_paid: boolean;
  enabled: boolean;
  implemented: boolean;
  base_url?: string | null;
  api_key_configured?: boolean | null;
  health: ProviderHealth | null;
};

export type Benchmark = {
  json_valid_rate: number | null;
  codegen_pass_rate: number | null;
  bugfix_pass_rate: number | null;
  avg_tok_per_s: number | null;
};

export type ModelRow = {
  provider: string;
  model_id: string;
  available: boolean;
  is_paid: boolean;
  context_limit: number | null;
  supports_tools: boolean | null;
  supports_vision: boolean | null;
  supports_structured: boolean | null;
  validation_status: "unvalidated" | "benchmarked";
  benchmark: Benchmark | null;
};

export type Budget = {
  currency: string;
  monthly_limit: number;
  allow_paid_calls: boolean;
  require_approval_for_paid_calls: boolean;
  spent_total: number;
};

export type UsageItem = {
  id: string;
  created_at: string;
  provider: string;
  model: string;
  status: "ok" | "error" | "blocked" | "cancelled";
  error_kind: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  duration_ms: number | null;
  cost_idr: number;
};

export type UsageResponse = {
  summary: {
    total: number; ok: number; error: number; blocked: number; cancelled: number;
    prompt_tokens: number; completion_tokens: number; total_cost_idr: number;
  };
  items: UsageItem[];
};

export type GenerateResult = {
  request_id: string;
  provider: string;
  model: string;
  text: string;
  truncated: boolean;
  usage: { prompt_tokens: number | null; completion_tokens: number | null; duration_ms: number | null };
};

export const aiApi = {
  providers: () => apiFetch<Provider[]>("/api/providers"),
  updateProvider: (name: string, data: { enabled: boolean; base_url?: string; api_key?: string; clear_api_key?: boolean }) =>
    apiFetch<Provider>(`/api/providers/${encodeURIComponent(name)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  models: () => apiFetch<ModelRow[]>("/api/models"),
  syncModels: (provider?: string) => apiFetch<ModelRow[]>(`/api/models/sync${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`, { method: "POST" }),
  budgets: () => apiFetch<Budget>("/api/budgets"),
  usage: (limit = 20) => apiFetch<UsageResponse>(`/api/usage?limit=${limit}`),
  generate: (data: { prompt: string; max_tokens: number; request_id: string; provider?: string; model?: string }) =>
    apiFetch<GenerateResult>("/api/ai/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  cancel: (requestId: string) =>
    apiFetch<{ cancelled: boolean }>(`/api/ai/requests/${requestId}/cancel`, { method: "POST" }),
};

export const pct = (v: number | null | undefined) => (v == null ? "?" : `${Math.round(v * 100)}%`);
