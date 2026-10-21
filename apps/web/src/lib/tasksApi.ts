import { apiFetch, type Project } from "@/lib/api";

export type TaskStatus =
  | "draft" | "pending_approval" | "queued" | "running" | "blocked"
  | "completed" | "failed" | "cancelled" | "interrupted";

export type Task = {
  id: string;
  project_id: string;
  parent_task_id: string | null;
  title: string;
  description: string;
  role: string;
  action_type: string;
  status: TaskStatus;
  priority: number;
  acceptance_criteria: string[];
  risk_level: "low" | "medium" | "high" | "critical";
  requires_approval: boolean;
  difficulty_score: number | null;
  difficulty_category: "light" | "medium" | "heavy" | "critical" | null;
  attempt_count: number;
  max_retries: number;
  available_at: string;
  blocked_reason: string | null;
  last_error: string | null;
  last_error_kind: string | null;
  verification: { method: string; passed: boolean; criteria_checked?: boolean } | null;
  review_status: "approved" | "changes_requested" | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type Attempt = {
  id: string;
  number: number;
  status: string;
  error_kind: string | null;
  error_message: string | null;
  retryable: boolean | null;
  started_at: string;
  finished_at: string | null;
  provider: string | null;
  model: string | null;
  usage: { prompt_tokens?: number; completion_tokens?: number; duration_ms?: number; calls?: number } | null;
};

export type TaskEvent = {
  seq: number;
  type: string;
  from_status: string | null;
  to_status: string | null;
  reason: string | null;
  actor: string;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type RoutingDecision = {
  id: string;
  provider: string;
  model: string;
  num_ctx: number;
  difficulty_score: number | null;
  difficulty_category: string | null;
  risk_level: string;
  reasons: string[];
  candidates: { model: string; eligible: boolean; rejected_because: string[] }[];
};

export type Execution = {
  id: string;
  created_at: string;
  kind: string;
  argv: string[];
  status: "ok" | "failed" | "timeout" | "error";
  exit_code: number | null;
  duration_ms: number | null;
  timed_out: boolean;
  output_truncated: boolean;
  stdout: string;
  stderr: string;
  sandbox: string;
};

export type TestRun = {
  id: string;
  created_at: string;
  status: "passed" | "failed" | "error";
  source: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  duration_ms: number | null;
  results: { name: string; classname: string | null; outcome: string; message: string | null; duration_ms: number | null }[];
};

export type SandboxCheck = { name: string; description: string; passed: boolean; detail: string };
export type SandboxReport = { passed: boolean; checks: SandboxCheck[]; ran_at: string | null; reason?: string; message?: string };
export type SandboxStatus = {
  configured_backend: string;
  backend: string;
  available: boolean;
  reason: string | null;
  message: string | null;
  selftest: SandboxReport | null;
  limits: { timeout_s: number; memory_mb: number; max_output_kb: number; network: boolean };
};

export type WorkspaceOverview = {
  files: { path: string; size: number }[];
  commits: { commit: string; author: string; date: string; message: string }[];
};

export type Approval = {
  id: string;
  created_at: string;
  task_id: string;
  project_id: string;
  action_type: string;
  risk_level: "low" | "medium" | "high" | "critical";
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled";
  payload: { title: string; description: string; role: string; action_type: string; acceptance_criteria: string[]; depends_on: string[]; params?: Record<string, unknown> };
  requested_by: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_reason: string | null;
  expires_at: string;
  used_at: string | null;
};

export type ReviewFinding = {
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  file?: string | null;
  line?: number | null;
  description: string;
  suggestion?: string | null;
  source: "static" | "model";
};

export type CodeReview = {
  id: string;
  task_id: string;
  reviewed_task_ids: string[];
  commit: string | null;
  verdict: "approved" | "changes_requested";
  summary: string;
  verdict_reasons: string[];
  criteria: { id: string; criterion: string; met: boolean | null; evidence: string; grounded: boolean }[];
  findings: ReviewFinding[];
  unresolved_risks: string[];
  evidence: { rerun?: { status: string; passed: number; failed: number; errors: number } | null };
};

export type TaskDetail = Task & {
  result: {
    output?: string;
    artifact?: string;
    created_task_ids?: string[];
    files?: { path: string; bytes: number; new: boolean }[];
    commit?: string | null;
  } | null;
  depends_on: string[];
  attempts: Attempt[];
  events: TaskEvent[];
  routing: RoutingDecision[];
  executions: Execution[];
  test_runs: TestRun[];
  approvals: Approval[];
  reviews: CodeReview[];
};

export type Agent = {
  role: string;
  department: string;
  status: string;
  queued: number;
  current_task_id: string | null;
  current_task_title: string | null;
};

export type WorkerStatus = {
  enabled: boolean;
  running: boolean;
  current_task_id: string | null;
  max_concurrent_tasks: number;
  counts: Record<TaskStatus, number>;
};

const post = (url: string, body?: unknown): RequestInit => ({
  method: "POST",
  ...(body !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
});

export const tasksApi = {
  projects: () => apiFetch<Project[]>("/api/projects"),
  list: (projectId?: string) => apiFetch<Task[]>(`/api/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  get: (id: string) => apiFetch<TaskDetail>(`/api/tasks/${id}`),
  agents: (projectId?: string) => apiFetch<Agent[]>(`/api/agents${projectId ? `?project_id=${projectId}` : ""}`),
  worker: () => apiFetch<WorkerStatus>("/api/worker"),
  plan: (projectId: string, goal: string) => apiFetch<Task>(`/api/projects/${projectId}/plan`, post("", { goal })),
  queue: (id: string) => apiFetch<Task>(`/api/tasks/${id}/queue`, post("")),
  queueDrafts: (projectId: string) => apiFetch<Task[]>(`/api/projects/${projectId}/tasks/queue-drafts`, post("")),
  cancel: (id: string) => apiFetch<Task>(`/api/tasks/${id}/cancel`, post("")),
  retry: (id: string) => apiFetch<Task>(`/api/tasks/${id}/retry`, post("")),
  approvals: () => apiFetch<Approval[]>("/api/approvals?limit=100"),
  approve: (id: string, reason?: string) => apiFetch<Approval>(`/api/approvals/${id}/approve`, post("", { reason: reason || null })),
  reject: (id: string, reason?: string) => apiFetch<Approval>(`/api/approvals/${id}/reject`, post("", { reason: reason || null })),
  taskReport: (id: string) => apiFetch<{ markdown: string; generated_at: string }>(`/api/tasks/${id}/report`),
  projectReport: (id: string) => apiFetch<{ markdown: string; summary: string; tasks: number }>(`/api/projects/${id}/report`),
  sandbox: () => apiFetch<SandboxStatus>("/api/sandbox"),
  sandboxSelftest: () => apiFetch<SandboxReport>("/api/sandbox/selftest", post("")),
  workspace: (projectId: string) => apiFetch<WorkspaceOverview>(`/api/projects/${projectId}/workspace`),
  workspaceFile: (projectId: string, path: string) =>
    apiFetch<{ path: string; size: number; content: string }>(
      `/api/projects/${projectId}/workspace/file?path=${encodeURIComponent(path)}`),
};

// Kolom papan task. failed dan interrupted digabung karena keduanya memerlukan keputusan manusia.
export const BOARD_COLUMNS: { key: string; statuses: TaskStatus[] }[] = [
  { key: "draft", statuses: ["draft"] },
  { key: "pending_approval", statuses: ["pending_approval"] },
  { key: "queued", statuses: ["queued"] },
  { key: "running", statuses: ["running"] },
  { key: "blocked", statuses: ["blocked"] },
  { key: "failed", statuses: ["failed", "interrupted"] },
  { key: "completed", statuses: ["completed"] },
  { key: "cancelled", statuses: ["cancelled"] },
];
