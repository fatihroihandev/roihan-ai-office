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

export type TaskDetail = Task & {
  result: { output?: string; artifact?: string; created_task_ids?: string[] } | null;
  depends_on: string[];
  attempts: Attempt[];
  events: TaskEvent[];
  routing: RoutingDecision[];
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
