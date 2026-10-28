"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Loading, PageHero } from "@/components/ui/PageHero";
import { api, type Project } from "@/lib/api";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";
import { Icon } from "@/components/ui/Icons";

export function ProjectsFeature() {
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
    <PageTransition>
      <main data-accent="blue">
        <PageHero
          code="01"
          route="SYS://PROJECTS"
          art="projects"
          title={t("projects.title")}
          hint={t("hero.projects.hint")}
          stats={[
            { label: t("hero.stat.projects"), value: projects?.length ?? 0 },
            { label: t("hero.stat.active"), value: projects?.filter((p) => p.status === "active").length ?? 0, tone: "ok" },
            { label: t("hero.stat.archived"), value: projects?.filter((p) => p.status === "archived").length ?? 0 },
          ]}
        />

        <form className="card grid2" onSubmit={onCreate}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, gridColumn: "1 / -1", marginBottom: 4 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="plus" size={17} />
            </span>
            <h3 style={{ margin: 0 }}>{t("projects.new")}</h3>
          </div>
          <label>
            {t("projects.name")}
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
          </label>
          <label>
            {t("projects.description")}
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} rows={2} />
          </label>
          <button
            type="submit"
            disabled={busy || !name.trim()}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, justifySelf: "start" }}
          >
            <Icon name="plus" size={14} />
            <span>{t("projects.create")}</span>
          </button>
        </form>

        {error && <p className="bad" role="alert">{error}</p>}
        {projects === null && !error && <Loading />}
        {projects?.length === 0 && <p>{t("projects.empty")}</p>}

        <ul className="list tiles">
          {projects?.map((p) => (
            <li key={p.id} className="card">
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ color: "var(--accent)", display: "flex" }}>
                    <Icon name="folder" size={18} />
                  </span>
                  <strong>{p.name}</strong>
                </div>
                <span className="badge" data-state={p.status}>{t(`projects.status.${p.status}` as MessageKey)}</span>
                {p.description && <p className="muted">{p.description}</p>}
              </div>
              <Link
                className="button"
                href={`/projects/${p.id}`}
                style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
              >
                <span>{t("projects.open")}</span>
                <Icon name="arrow-right" size={12} />
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </PageTransition>
  );
}
