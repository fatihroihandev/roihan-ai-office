"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { webApi, type ProspectingQueued, type ResearchQueued } from "@/lib/webApi";
import { productsApi, type Product } from "@/lib/productsApi";
import { tasksApi } from "@/lib/tasksApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

/** Cari prospek atau riset pasar langsung dari web: backend mencari dan mengambil halaman, agent hanya mengekstrak/menyusun dari teksnya. */
export function WebFinder({ onQueued }: { onQueued: () => void }) {
  const { t } = useLanguage();
  const [industry, setIndustry] = useState("");
  const [city, setCity] = useState("");
  const [need, setNeed] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("");
  const [pages, setPages] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ text: string; hint: boolean } | null>(null);
  const [pros, setPros] = useState<ProspectingQueued | null>(null);
  const [res, setRes] = useState<ResearchQueued | null>(null);
  const [tracking, setTracking] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    productsApi.list().then(setProducts, () => undefined);
    return () => { mounted.current = false; };
  }, []);

  const query = [industry, city, need].filter((part) => part.trim()).join(" ");
  const clearInputs = () => { setIndustry(""); setCity(""); setNeed(""); setProductId(""); setPages(3); };

  async function followProspecting(taskIds: string[]) {
    setTracking(true);
    const intakeIds = [...taskIds];
    const draftIds = new Set<string>();
    try {
      for (let attempt = 0; attempt < 180; attempt += 1) {
        const intakeTasks = await Promise.all(intakeIds.map((id) => tasksApi.get(id)));
        for (const task of intakeTasks) for (const id of task.result?.draft_task_ids ?? []) draftIds.add(id);
        const allTasks = await Promise.all([...intakeIds, ...draftIds].map((id) => tasksApi.get(id)));
        if (attempt % 3 === 0) onQueued();
        if (allTasks.every((task) => ["completed", "failed", "blocked", "cancelled", "interrupted"].includes(task.status))) break;
        await new Promise((resolve) => window.setTimeout(resolve, 2500));
      }
    } catch { /* status tetap bisa diperbarui lewat pemuatan ulang halaman */ }
    finally {
      if (mounted.current) {
        setTracking(false);
        onQueued();
      }
    }
  }

  async function go(kind: "prospecting" | "research") {
    setBusy(true);
    setError(null);
    setPros(null);
    setRes(null);
    try {
      if (kind === "prospecting") {
        const queued = await webApi.prospecting({ query, source_type: "public_website", max_pages: pages, product_id: productId || undefined });
        setPros(queued);
        void followProspecting(queued.queued.map((item) => item.task_id));
      }
      else setRes(await webApi.research({ topic: query, query, max_pages: pages, product_id: productId || undefined }));
      onQueued();
    } catch (e) {
      const text = (e as Error).message;
      setError({ text, hint: /nonaktif|Aktifkan/i.test(text) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-label={t("webfinder.title")}>
      <h3>{t("webfinder.title")}</h3>
      <p className="small muted">{t("webfinder.hint")}</p>
      <div className="row">
        <label>{t("webfinder.industry")}<input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder={t("webfinder.industryPlaceholder")} /></label>
        <label>{t("webfinder.city")}<input value={city} onChange={(e) => setCity(e.target.value)} placeholder={t("webfinder.cityPlaceholder")} /></label>
        <label>{t("webfinder.need")}<input value={need} onChange={(e) => setNeed(e.target.value)} placeholder={t("webfinder.needPlaceholder")} /></label>
        <label>{t("webfinder.pages")}<select value={pages} onChange={(e) => setPages(Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
        <label>{t("webfinder.product")}<select value={productId} onChange={(e) => setProductId(e.target.value)}><option value="">{t("webfinder.noProduct")}</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name} · {t(`perm.${p.effective_permission}` as MessageKey)}</option>)}</select></label>
      </div>
      <p className="small muted">{t("webfinder.sourceNote")}</p>
      <div className="actions">
        <button type="button" className="primary-btn" disabled={busy || query.trim().length < 3 || !productId} onClick={() => void go("prospecting")}>{busy ? t("webfinder.working") : t("webfinder.prospect")}</button>
        <button type="button" disabled={busy || query.trim().length < 3} onClick={() => void go("research")}>{t("webfinder.research")}</button>
        <button type="button" disabled={busy || (!industry && !city && !need)} onClick={clearInputs}>{t("webfinder.clearInputs")}</button>
      </div>
      {!productId && <p className="small muted">{t("webfinder.productRequired")}</p>}
      {productId && products.find((p) => p.id === productId)?.effective_permission === "not_allowed" && <p className="small muted">{t("webfinder.productNotReady")} <Link href={`/products/${productId}`}>{t("webfinder.prepareProduct")}</Link></p>}
      {error && <p className="bad small" role="alert">{error.text} {error.hint && <Link href="/ai">{t("webfinder.openAi")}</Link>}</p>}
      {tracking && <p className="small" role="status">{t("webfinder.processing")}</p>}
      {pros && (
        <div role="status">
          <p className="ok small">{t("webfinder.queued").replace("{n}", String(pros.queued.length))}</p>
          <ul className="small">{pros.queued.map((q) => <li key={q.task_id}>{q.title || q.url} <span className="muted">· {q.url}</span>{q.injection_suspected && <span className="badge" data-risk="high">{t("webfinder.suspect")}</span>}</li>)}</ul>
          {pros.skipped.length > 0 && <p className="small muted">{t("webfinder.skipped")}: {pros.skipped.map((s) => `${s.url} (${s.message})`).join("; ")}</p>}
        </div>
      )}
      {res && (
        <div role="status">
          <p className="ok small">{t("webfinder.researchQueued").replace("{n}", String(res.sources.length))}</p>
          <ul className="small">{res.sources.map((s) => <li key={s.url}>{s.title || s.url} <span className="muted">· {s.url}</span></li>)}</ul>
        </div>
      )}
    </section>
  );
}
