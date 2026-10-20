import { apiFetch } from "@/lib/api";

export type Line = "owned_product" | "service";
export type DevStatus = "draft" | "in_development" | "internal_testing" | "beta" | "released" | "deprecated" | "archived";
export type Permission = "not_allowed" | "beta_only" | "allowed";
export type FeatureStatus = "verified" | "attested" | "unverified" | "disputed" | "withdrawn";

// Cermin dari TRANSITIONS di backend; backend tetap menjadi penentu akhir.
export const NEXT_STATUS: Record<DevStatus, DevStatus[]> = {
  draft: ["in_development", "archived"],
  in_development: ["internal_testing", "draft", "deprecated", "archived"],
  internal_testing: ["beta", "in_development", "deprecated", "archived"],
  beta: ["released", "internal_testing", "deprecated", "archived"],
  released: ["deprecated", "archived"],
  deprecated: ["archived"],
  archived: [],
};

export type Product = {
  id: string;
  name: string;
  line: Line;
  description: string | null;
  target_customers: string | null;
  pricing_model: string | null;
  pricing_approved: boolean;
  pricing_approved_by: string | null;
  project_id: string | null;
  status: DevStatus;
  current_version: string | null;
  effective_permission: Permission;
  versions?: Version[];
};

export type Feature = {
  id: string;
  text: string;
  status: FeatureStatus;
  evidence: { task_ids?: string[]; tasks?: { id: string; title: string; commit: string | null }[]; problems?: string[] };
  attested_by: string | null;
  attestation_reason: string | null;
};

export type Version = {
  id: string;
  version: string;
  status: DevStatus;
  release_notes: string | null;
  commit: string | null;
  limitations: string[];
  limitations_confirmed: boolean;
  materials_reviewed: boolean;
  granted_permission: Permission;
  effective_permission: Permission;
  revoked_reasons: string[];
  features: Feature[];
};

export type GateItem = { key: string; label: string; required: boolean; passed: boolean; detail: string };
export type Gate = { target: "beta_only" | "allowed"; ready: boolean; items: GateItem[] };

export type Brief = {
  effective_permission: Permission;
  usable_for_promotion: boolean;
  promotion_label: string | null;
  blocked_reasons: string[];
  claims: { id: string; text: string; basis: string }[];
  unverified_claims: { id: string; text: string; status: string; label: string; problems: string[] }[];
  limitations: string[];
  pricing: string | null;
  required_disclaimers: string[];
};

export type Candidate = { id: string; title: string; role: string; commit: string | null; last_test_status: string | null; review_status: string | null };
export type LintResult = { ok: boolean; findings: { type: string; severity: string; detail: string; match: string }[] };

const body = (method: string, data?: unknown): RequestInit => ({
  method,
  ...(data !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) } : {}),
});

export const productsApi = {
  list: () => apiFetch<Product[]>("/api/products"),
  get: (id: string) => apiFetch<Product>(`/api/products/${id}`),
  create: (data: { name: string; line: Line; description?: string; target_customers?: string; pricing_model?: string; project_id?: string }) =>
    apiFetch<Product>("/api/products", body("POST", data)),
  update: (id: string, data: Partial<Pick<Product, "description" | "target_customers" | "pricing_model">>) =>
    apiFetch<Product>(`/api/products/${id}`, body("PATCH", data)),
  approvePricing: (id: string) => apiFetch<Product>(`/api/products/${id}/approve-pricing`, body("POST", {})),
  candidates: (id: string) => apiFetch<Candidate[]>(`/api/products/${id}/evidence-candidates`),
  createVersion: (id: string, version: string, pin: boolean) =>
    apiFetch<Version>(`/api/products/${id}/versions`, body("POST", { version, pin_commit: pin })),
  updateVersion: (id: string, vid: string, data: Partial<{ status: DevStatus; limitations: string[]; limitations_confirmed: boolean; materials_reviewed: boolean }>) =>
    apiFetch<Version>(`/api/products/${id}/versions/${vid}`, body("PATCH", data)),
  pin: (id: string, vid: string) => apiFetch<Version>(`/api/products/${id}/versions/${vid}/pin-commit`, body("POST")),
  addFeature: (id: string, vid: string, text: string, taskIds: string[]) =>
    apiFetch<Feature>(`/api/products/${id}/versions/${vid}/features`, body("POST", { text, task_ids: taskIds })),
  featureAction: (id: string, vid: string, fid: string, action: "reverify" | "attest" | "dispute" | "withdraw", reason?: string) =>
    apiFetch<Feature>(`/api/products/${id}/versions/${vid}/features/${fid}/${action}`, body("POST", { reason })),
  attach: (id: string, vid: string, fid: string, taskIds: string[]) =>
    apiFetch<Feature>(`/api/products/${id}/versions/${vid}/features/${fid}/evidence`, body("POST", { task_ids: taskIds })),
  gate: (id: string, vid: string, target: "beta_only" | "allowed") =>
    apiFetch<Gate>(`/api/products/${id}/versions/${vid}/release-gate?target=${target}`),
  setPermission: (id: string, vid: string, permission: Permission, reason?: string) =>
    apiFetch<Version>(`/api/products/${id}/versions/${vid}/marketing-permission`, body("POST", { permission, reason })),
  brief: (id: string, vid: string) => apiFetch<Brief>(`/api/products/${id}/versions/${vid}/marketing-brief`),
  check: (id: string, vid: string, text: string) => apiFetch<LintResult>(`/api/products/${id}/versions/${vid}/check-claims`, body("POST", { text })),
};
