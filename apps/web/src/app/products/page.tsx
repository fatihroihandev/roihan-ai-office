"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import type { Project } from "@/lib/api";
import { productsApi, type Line, type Product } from "@/lib/productsApi";
import { tasksApi } from "@/lib/tasksApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function ProductsPage() {
  const { t } = useLanguage();
  const [products, setProducts] = useState<Product[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [line, setLine] = useState<Line>("owned_product");
  const [description, setDescription] = useState("");
  const [target, setTarget] = useState("");
  const [projectId, setProjectId] = useState("");

  useEffect(() => {
    let cancelled = false;
    productsApi.list().then((p) => !cancelled && setProducts(p), (e: Error) => !cancelled && setError(e.message));
    tasksApi.projects().then((p) => !cancelled && setProjects(p), () => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await productsApi.create({
        name, line, description: description || undefined, target_customers: target || undefined, project_id: projectId || undefined,
      });
      setProducts((prev) => [created, ...(prev ?? [])]);
      setName("");
      setDescription("");
      setTarget("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const label = (key: string) => t(key as MessageKey);

  return (
    <main>
      <AppHeader />
      <h2>{t("products.title")}</h2>
      <p className="muted">{t("products.hint")}</p>

      <form className="card" onSubmit={onCreate}>
        <h3>{t("products.new")}</h3>
        <label>{t("products.name")}<input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} required /></label>
        <label>
          {t("products.line")}
          <select value={line} onChange={(e) => setLine(e.target.value as Line)}>
            <option value="owned_product">{t("products.line.owned_product")}</option>
            <option value="service">{t("products.line.service")}</option>
          </select>
        </label>
        <label>{t("products.description")}<textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label>{t("products.targetCustomers")}<input value={target} onChange={(e) => setTarget(e.target.value)} /></label>
        <label>
          {t("products.project")}
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">{t("products.noProject")}</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <button type="submit" disabled={busy || !name.trim()}>{t("products.create")}</button>
      </form>

      {error && <p className="bad" role="alert">{error}</p>}
      {products === null && !error && <p>{t("common.loading")}</p>}
      {products?.length === 0 && <p>{t("products.empty")}</p>}
      <ul className="list">
        {products?.map((p) => (
          <li key={p.id} className="card">
            <div>
              <strong>{p.name}</strong>
              <span className="badge">{label(`products.line.${p.line}`)}</span>
              <div className="chips">
                <span className="badge">{label(`pstatus.${p.status}`)}{p.current_version ? ` · ${p.current_version}` : ` · ${t("products.noVersion")}`}</span>
                <span className="badge" data-task={p.effective_permission === "not_allowed" ? "failed" : "completed"}>{label(`perm.${p.effective_permission}`)}</span>
              </div>
              {p.description && <p className="muted">{p.description}</p>}
            </div>
            <Link className="button" href={`/products/${p.id}`}>{t("products.open")}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
