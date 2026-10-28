"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { Icon } from "@/components/ui/Icons";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  NEXT_STATUS, productsApi, type Brief, type Candidate, type Gate, type LintResult, type Product, type Version,
} from "@/lib/productsApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function ProductDetailPage() {
  const { t } = useLanguage();
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [versionId, setVersionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [target, setTarget] = useState<"beta_only" | "allowed">("beta_only");
  const [gate, setGate] = useState<Gate | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [lint, setLint] = useState<LintResult | null>(null);
  const [draft, setDraft] = useState("");

  const [newVersion, setNewVersion] = useState("");
  const [pinOnCreate, setPinOnCreate] = useState(true);
  const [featureText, setFeatureText] = useState("");
  const [featureTasks, setFeatureTasks] = useState<string[]>([]);
  const [limitText, setLimitText] = useState("");
  const [pricing, setPricing] = useState("");
  const [desc, setDesc] = useState("");
  const [customers, setCustomers] = useState("");
  const [attach, setAttach] = useState<Record<string, string[]>>({});

  const version: Version | undefined = product?.versions?.find((v) => v.id === versionId) ?? product?.versions?.[0];

  const applyProduct = useCallback((p: Product) => {
    setProduct(p);
    setPricing(p.pricing_model ?? "");
    setDesc(p.description ?? "");
    setCustomers(p.target_customers ?? "");
  }, []);

  const load = useCallback(async () => {
    const p = await productsApi.get(id);
    applyProduct(p);
    setCandidates(await productsApi.candidates(id));
    return p;
  }, [id, applyProduct]);

  useEffect(() => {
    let cancelled = false;
    productsApi.get(id).then(
      async (p) => {
        if (cancelled) return;
        applyProduct(p);
        setVersionId((cur) => cur ?? p.versions?.[0]?.id ?? null);
        const c = await productsApi.candidates(id);
        if (!cancelled) setCandidates(c);
      },
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [id, applyProduct]);

  // Reset state turunan saat versi (atau batasan tersimpan) berganti: pola "reset saat render" resmi React, bukan effect
  const syncKey = `${version?.id ?? ""}:${JSON.stringify(version?.limitations ?? [])}`;
  const [trackedKey, setTrackedKey] = useState(syncKey);
  if (trackedKey !== syncKey) {
    setTrackedKey(syncKey);
    setLimitText((version?.limitations ?? []).join("\n"));
    setGate(null);
    setBrief(null);
    setLint(null);
  }

  async function act(fn: () => Promise<unknown>, reload = true) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      if (reload) await load();
    } catch (e) {
      setError((e as Error).message);
      if (reload) await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  const label = (key: string) => t(key as MessageKey);
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  async function onEvaluate(next = target) {
    setTarget(next);
    if (version) await act(async () => setGate(await productsApi.gate(id, version.id, next)), false);
  }

  async function onGrant() {
    if (!version) return;
    setBusy(true);
    setError(null);
    try {
      await productsApi.setPermission(id, version.id, target, "diberikan lewat antarmuka");
      await load();
      setGate(await productsApi.gate(id, version.id, target));
    } catch (e) {
      setError((e as Error).message);
      setGate(await productsApi.gate(id, version.id, target).catch(() => null));
      await load().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  const askReason = () => window.prompt(t("feature.reasonPrompt")) ?? "";

  return (
    <PageTransition>
<main className="wide">
      <p><Link href="/products" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}><Icon name="arrow-left" size={14} /> {t("product.back")}</Link></p>
      {error && <p className="bad" role="alert">{error}</p>}
      {!product && !error && <p>{t("common.loading")}</p>}

      {product && (
        <>
          <section className="card">
            <h2>{product.name}</h2>
            <div className="chips">
              <span className="badge">{label(`products.line.${product.line}`)}</span>
              <span className="badge">{label(`pstatus.${product.status}`)}</span>
              <span className="badge" data-task={product.effective_permission === "not_allowed" ? "failed" : "completed"}>{label(`perm.${product.effective_permission}`)}</span>
            </div>
            <label>{t("products.description")}<textarea rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
            <label>{t("products.targetCustomers")}<input value={customers} onChange={(e) => setCustomers(e.target.value)} /></label>
            <label>{t("products.pricing")}<input value={pricing} onChange={(e) => setPricing(e.target.value)} /></label>
            <div className="actions">
              <button type="button" disabled={busy} onClick={() => act(() => productsApi.update(id, { description: desc, target_customers: customers, pricing_model: pricing }))}>{t("product.save")}</button>
              <button type="button" disabled={busy || !product.pricing_model || product.pricing_approved} onClick={() => act(() => productsApi.approvePricing(id))}>{t("product.pricing.approve")}</button>
              <span className="badge" data-task={product.pricing_approved ? "completed" : "failed"}>{t(product.pricing_approved ? "product.pricing.approved" : "product.pricing.notApproved")}</span>
            </div>
          </section>

          <section className="card">
            <h3>{t("product.versions")}</h3>
            <div className="chips">
              {product.versions?.map((v) => (
                <button key={v.id} type="button" aria-pressed={v.id === version?.id} className={v.id === version?.id ? "tab on" : "tab"} onClick={() => setVersionId(v.id)}>
                  {v.version} · {label(`pstatus.${v.status}`)}
                </button>
              ))}
            </div>
            <div className="row">
              <label>{t("product.version.name")}<input value={newVersion} onChange={(e) => setNewVersion(e.target.value)} /></label>
              <label className="inline"><input type="checkbox" checked={pinOnCreate} onChange={(e) => setPinOnCreate(e.target.checked)} /> {t("product.version.pinOnCreate")}</label>
              <button type="button" disabled={busy || !newVersion.trim()} onClick={() => act(async () => { const v = await productsApi.createVersion(id, newVersion.trim(), pinOnCreate); setVersionId(v.id); setNewVersion(""); })}>{t("product.version.create")}</button>
            </div>
          </section>

          {version && (
            <>
              <section className="card">
                <h3>{version.version}</h3>
                <p className="muted small">
                  {t("product.status")}: <strong>{label(`pstatus.${version.status}`)}</strong> · {t("product.version.commit")}: <code>{version.commit ?? t("product.version.notPinned")}</code>
                </p>
                <div className="actions">
                  {NEXT_STATUS[version.status].map((s) => (
                    <button key={s} type="button" disabled={busy} onClick={() => act(() => productsApi.updateVersion(id, version.id, { status: s }))}>{t("product.status.moveTo")} {label(`pstatus.${s}`)}</button>
                  ))}
                  <button type="button" disabled={busy || !product.project_id} onClick={() => act(() => productsApi.pin(id, version.id))}>{t("product.version.pin")}</button>
                </div>
                <h4>{t("product.limitations")}</h4>
                <textarea rows={3} value={limitText} placeholder={t("product.limitations.hint")} onChange={(e) => setLimitText(e.target.value)} />
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => act(() => productsApi.updateVersion(id, version.id, { limitations: limitText.split("\n").map((x) => x.trim()).filter(Boolean) }))}>{t("product.save")}</button>
                  <label className="inline"><input type="checkbox" checked={version.limitations_confirmed} disabled={busy} onChange={(e) => act(() => productsApi.updateVersion(id, version.id, { limitations_confirmed: e.target.checked }))} /> {t("product.limitations.none")}</label>
                  <label className="inline"><input type="checkbox" checked={version.materials_reviewed} disabled={busy} onChange={(e) => act(() => productsApi.updateVersion(id, version.id, { materials_reviewed: e.target.checked }))} /> {t("product.materials")}</label>
                </div>
              </section>

              <section className="card">
                <h3>{t("product.features")}</h3>
                {version.features.length === 0 ? <p className="muted">{t("product.features.empty")}</p> : (
                  <table><tbody>
                    {version.features.map((f) => (
                      <tr key={f.id}>
                        <td>
                          <span className="badge" data-task={f.status === "verified" || f.status === "attested" ? "completed" : f.status === "unverified" ? "pending_approval" : "failed"}>{label(`feature.status.${f.status}`)}</span>{" "}
                          <strong>{f.text}</strong>
                          {f.attestation_reason && <div className="muted small">{f.attested_by}: {f.attestation_reason}</div>}
                          {(f.evidence.tasks?.length ?? 0) > 0 && <div className="muted small">{f.evidence.tasks!.map((x) => x.title).join(" · ")}</div>}
                          {(f.evidence.problems?.length ?? 0) > 0 && f.status === "unverified" && (
                            <ul className="small bad">{f.evidence.problems!.map((p, i) => <li key={i}>{p}</li>)}</ul>
                          )}
                          {f.status !== "withdrawn" && f.status !== "attested" && f.status !== "disputed" && candidates.length > 0 && (
                            <div className="muted small">
                              {candidates.map((c) => (
                                <label key={c.id} className="inline">
                                  <input type="checkbox" checked={(attach[f.id] ?? []).includes(c.id)} onChange={() => setAttach((a) => ({ ...a, [f.id]: toggle(a[f.id] ?? [], c.id) }))} /> {c.title}
                                </label>
                              ))}
                            </div>
                          )}
                        </td>
                        <td className="actions">
                          {(attach[f.id] ?? []).length > 0 && <button type="button" disabled={busy} onClick={() => act(async () => { await productsApi.attach(id, version.id, f.id, attach[f.id]); setAttach((a) => ({ ...a, [f.id]: [] })); })}>{t("feature.attach")}</button>}
                          <button type="button" disabled={busy} onClick={() => act(() => productsApi.featureAction(id, version.id, f.id, "reverify"))}>{t("feature.reverify")}</button>
                          <button type="button" disabled={busy} onClick={() => act(() => productsApi.featureAction(id, version.id, f.id, "attest", askReason()))}>{t("feature.attest")}</button>
                          <button type="button" className="danger" disabled={busy} onClick={() => act(() => productsApi.featureAction(id, version.id, f.id, "dispute", askReason()))}>{t("feature.dispute")}</button>
                          <button type="button" className="danger" disabled={busy} onClick={() => act(() => productsApi.featureAction(id, version.id, f.id, "withdraw", askReason()))}>{t("feature.withdraw")}</button>
                        </td>
                      </tr>
                    ))}
                  </tbody></table>
                )}
                <h4>{t("product.features.add")}</h4>
                <label>{t("product.features.text")}<input value={featureText} maxLength={500} onChange={(e) => setFeatureText(e.target.value)} /></label>
                <p className="muted small">{t("product.features.evidence")}</p>
                {candidates.length === 0 ? <p className="muted small">{t("product.features.noEvidence")}</p> : candidates.map((c) => (
                  <label key={c.id} className="inline">
                    <input type="checkbox" checked={featureTasks.includes(c.id)} onChange={() => setFeatureTasks((l) => toggle(l, c.id))} /> {c.title}{" "}
                    <span className="muted small">({c.role}{c.last_test_status ? `, tes ${c.last_test_status}` : ""}{c.review_status ? `, review ${c.review_status}` : ""})</span>
                  </label>
                ))}
                <div className="actions">
                  <button type="button" disabled={busy || !featureText.trim()} onClick={() => act(async () => { await productsApi.addFeature(id, version.id, featureText.trim(), featureTasks); setFeatureText(""); setFeatureTasks([]); })}>{t("product.features.add")}</button>
                </div>
              </section>

              <section className="card">
                <h3>{t("gate.title")}</h3>
                <div className="chips">
                  <span className="badge" data-task={version.effective_permission === "not_allowed" ? "failed" : "completed"}>{t("gate.effective")}: {label(`perm.${version.effective_permission}`)}</span>
                  {version.granted_permission !== version.effective_permission && <span className="badge">{t("gate.stored")}: {label(`perm.${version.granted_permission}`)}</span>}
                </div>
                {version.revoked_reasons.length > 0 && (
                  <><h4>{t("gate.revokedReasons")}</h4><ul className="small bad">{version.revoked_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul></>
                )}
                <div className="actions">
                  <label className="inline">
                    {t("gate.target")}
                    <select value={target} onChange={(e) => onEvaluate(e.target.value as "beta_only" | "allowed")}>
                      <option value="beta_only">{t("gate.target.beta_only")}</option>
                      <option value="allowed">{t("gate.target.allowed")}</option>
                    </select>
                  </label>
                  <button type="button" disabled={busy} onClick={() => onEvaluate()}>{t("gate.title")}</button>
                  <button type="button" disabled={busy} onClick={onGrant}>{t("gate.grant")}</button>
                  <button type="button" className="danger" disabled={busy || version.granted_permission === "not_allowed"} onClick={() => act(() => productsApi.setPermission(id, version.id, "not_allowed", "dicabut lewat antarmuka"))}>{t("gate.revoke")}</button>
                </div>
                {gate && (
                  <>
                    <p><span className="badge" data-task={gate.ready ? "completed" : "failed"}>{t(gate.ready ? "gate.ready" : "gate.notReady")}</span></p>
                    <table><tbody>
                      {gate.items.map((i) => (
                        <tr key={i.key}>
                          <td>
                            <span className="badge" data-task={i.passed ? "completed" : i.required ? "failed" : undefined}>{i.passed ? "✓" : "✗"}</span>{" "}
                            <strong>{i.label}</strong> <span className="muted small">({t(i.required ? "gate.required" : "gate.optional")})</span>
                            <div className="muted small">{i.detail}</div>
                          </td>
                        </tr>
                      ))}
                    </tbody></table>
                  </>
                )}
              </section>

              <section className="card">
                <h3>{t("brief.title")}</h3>
                <button type="button" disabled={busy} onClick={() => act(async () => setBrief(brief ? null : await productsApi.brief(id, version.id)), false)}>{t("brief.show")}</button>
                {brief && (
                  <>
                    <p>
                      <span className="badge" data-task={brief.usable_for_promotion ? "completed" : "failed"}>{brief.usable_for_promotion ? `${label(`perm.${brief.effective_permission}`)}` : t("brief.blocked")}</span>
                      {brief.promotion_label && <span className="badge">{brief.promotion_label}</span>}
                    </p>
                    {brief.blocked_reasons.length > 0 && <ul className="small bad">{brief.blocked_reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
                    <h4>{t("brief.claims")}</h4>
                    {brief.claims.length === 0 ? <p className="muted">{t("brief.none")}</p> : <ul>{brief.claims.map((c) => <li key={c.id}>{c.text} <span className="muted small">({c.basis})</span></li>)}</ul>}
                    <h4>{t("brief.unverified")}</h4>
                    {brief.unverified_claims.length === 0 ? <p className="muted">{t("brief.none")}</p> : <ul className="bad">{brief.unverified_claims.map((c) => <li key={c.id}>{c.text} <span className="small">({c.status})</span></li>)}</ul>}
                    <h4>{t("brief.limitations")}</h4>
                    {brief.limitations.length === 0 ? <p className="muted">{t("brief.none")}</p> : <ul>{brief.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>}
                    {brief.required_disclaimers.length > 0 && <><h4>{t("brief.disclaimers")}</h4><ul>{brief.required_disclaimers.map((d, i) => <li key={i}>{d}</li>)}</ul></>}
                    <p className="muted small">{t("brief.pricing")}: {brief.pricing ?? t("brief.none")}</p>
                  </>
                )}
              </section>

              <section className="card">
                <h3>{t("lint.title")}</h3>
                <textarea rows={4} value={draft} placeholder={t("lint.placeholder")} maxLength={5000} onChange={(e) => setDraft(e.target.value)} />
                <div className="actions">
                  <button type="button" disabled={busy || !draft.trim()} onClick={() => act(async () => setLint(await productsApi.check(id, version.id, draft)), false)}>{t("lint.run")}</button>
                </div>
                {lint && (lint.ok ? <p className="badge" data-task="completed">{t("lint.ok")}</p> : (
                  <>
                    <p className="bad">{t("lint.blocked")}</p>
                    <ul className="small bad">{lint.findings.map((f, i) => <li key={i}><strong>{f.type}</strong>{f.match ? ` “${f.match}”` : ""} — {f.detail}</li>)}</ul>
                  </>
                ))}
              </section>
            </>
          )}
        </>
      )}
    </main>
</PageTransition>
  );
}
