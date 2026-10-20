"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { api, type Project } from "@/lib/api";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function ProjectsPage() {
  const { t } = useLanguage();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.listProjects().then(
      (list) => !cancelled && setProjects(list),
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createProject({ name, description: description || undefined });
      setProjects((prev) => [created, ...(prev ?? [])]);
      setName("");
      setDescription("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <AppHeader />
      <h2>{t("projects.title")}</h2>

      <form className="card" onSubmit={onCreate}>
        <h3>{t("projects.new")}</h3>
        <label>
          {t("projects.name")}
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
        </label>
        <label>
          {t("projects.description")}
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={2} />
        </label>
        <button type="submit" disabled={busy || !name.trim()}>{t("projects.create")}</button>
      </form>

      {error && <p className="bad" role="alert">{error}</p>}
      {projects === null && !error && <p>{t("common.loading")}</p>}
      {projects?.length === 0 && <p>{t("projects.empty")}</p>}

      <ul className="list">
        {projects?.map((p) => (
          <li key={p.id} className="card">
            <div>
              <strong>{p.name}</strong>
              <span className="badge" data-state={p.status}>{t(`projects.status.${p.status}` as MessageKey)}</span>
              {p.description && <p className="muted">{p.description}</p>}
            </div>
            <Link className="button" href={`/projects/${p.id}`}>{t("projects.open")}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
