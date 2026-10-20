"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { api, FILE_KINDS, formatBytes, type FileKind, type Project, type ProjectFile } from "@/lib/api";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function ProjectDetailPage() {
  const { t } = useLanguage();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<FileKind>("requirement");
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getProject(id), api.listFiles(id)]).then(
      ([p, f]) => {
        if (cancelled) return;
        setProject(p);
        setFiles(f);
      },
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [id]);

  const run = useCallback(async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const onUpload = (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    run(async () => {
      const created = await api.uploadFile(id, kind, file);
      setFiles((prev) => [created, ...prev]);
      if (fileInput.current) fileInput.current.value = "";
    });
  };

  const onToggleArchive = () =>
    run(async () => {
      if (!project) return;
      setProject(await api.updateProject(id, { status: project.status === "active" ? "archived" : "active" }));
    });

  const onDeleteProject = () => {
    if (!window.confirm(t("projects.confirmDelete"))) return;
    run(async () => {
      await api.deleteProject(id);
      router.push("/projects");
    });
  };

  const onDeleteFile = (fileId: string) => {
    if (!window.confirm(t("file.confirmDelete"))) return;
    run(async () => {
      await api.deleteFile(id, fileId);
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
    });
  };

  return (
    <main>
      <AppHeader />
      <p><Link href="/projects">← {t("projects.back")}</Link></p>
      {error && <p className="bad" role="alert">{error}</p>}
      {!project && !error && <p>{t("common.loading")}</p>}

      {project && (
        <>
          <section className="card">
            <h2>{project.name}</h2>
            <span className="badge" data-state={project.status}>
              {t(`projects.status.${project.status}` as MessageKey)}
            </span>
            {project.description && <p className="muted">{project.description}</p>}
            <div className="actions">
              <button type="button" onClick={onToggleArchive} disabled={busy}>
                {t(project.status === "active" ? "projects.archive" : "projects.unarchive")}
              </button>
              <button type="button" className="danger" onClick={onDeleteProject} disabled={busy}>
                {t("projects.delete")}
              </button>
            </div>
          </section>

          <section className="card">
            <h3>{t("project.files")}</h3>
            <form onSubmit={onUpload}>
              <label>
                {t("project.kind")}
                <select value={kind} onChange={(e) => setKind(e.target.value as FileKind)}>
                  {FILE_KINDS.map((k) => (
                    <option key={k} value={k}>{t(`kind.${k}` as MessageKey)}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("project.chooseFile")}
                <input ref={fileInput} type="file" required />
              </label>
              <button type="submit" disabled={busy}>{t("project.upload")}</button>
              <p className="muted small">{t("project.uploadHint")}</p>
            </form>

            {files.length === 0 ? (
              <p>{t("project.noFiles")}</p>
            ) : (
              <table>
                <tbody>
                  {files.map((f) => (
                    <tr key={f.id}>
                      <td>
                        <strong>{f.stored_name}</strong>
                        <div className="muted small">
                          {t(`kind.${f.kind}` as MessageKey)} · {formatBytes(f.size_bytes)} · {f.sha256.slice(0, 12)}
                        </div>
                      </td>
                      <td className="actions">
                        <a className="button" href={api.downloadUrl(id, f.id)}>{t("file.download")}</a>
                        <button type="button" className="danger" onClick={() => onDeleteFile(f.id)} disabled={busy}>
                          {t("file.delete")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}
