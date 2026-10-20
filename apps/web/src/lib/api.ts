export type FileKind = "master" | "requirement" | "reference" | "asset";
export const FILE_KINDS: FileKind[] = ["master", "requirement", "reference", "asset"];

export type Project = {
  id: string;
  name: string;
  description: string | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};

export type ProjectFile = {
  id: string;
  project_id: string;
  kind: FileKind;
  original_name: string;
  stored_name: string;
  relative_path: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
};

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

function detailMessage(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) return first.msg;
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit, fallback = "Terjadi kesalahan"): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/projects${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(fallback, 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(detailMessage(body) ?? fallback, res.status);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listProjects: () => request<Project[]>(""),
  getProject: (id: string) => request<Project>(`/${id}`),
  createProject: (data: { name: string; description?: string }) => request<Project>("", json("POST", data)),
  updateProject: (id: string, data: Partial<Pick<Project, "name" | "description" | "status">>) =>
    request<Project>(`/${id}`, json("PATCH", data)),
  deleteProject: (id: string) => request<void>(`/${id}`, { method: "DELETE" }),
  listFiles: (id: string) => request<ProjectFile[]>(`/${id}/files`),
  uploadFile: (id: string, kind: FileKind, file: File) => {
    const form = new FormData();
    form.set("kind", kind);
    form.set("file", file);
    return request<ProjectFile>(`/${id}/files`, { method: "POST", body: form });
  },
  deleteFile: (id: string, fileId: string) => request<void>(`/${id}/files/${fileId}`, { method: "DELETE" }),
  downloadUrl: (id: string, fileId: string) => `/api/projects/${id}/files/${fileId}/download`,
};

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
