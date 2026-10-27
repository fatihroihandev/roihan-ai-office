"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loading, PageHero } from "@/components/ui/PageHero";
import { WebAccessCard } from "@/components/WebAccessCard";
import { aiApi, pct, type Budget, type GenerateResult, type ModelRow, type Provider, type UsageResponse } from "@/lib/aiApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

type Note = { ok: boolean; text: string };

export function AiFeature() {
  const { t } = useLanguage();
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, Note>>({});
  const [enabledDraft, setEnabledDraft] = useState<Record<string, boolean>>({});
  const [urlDraft, setUrlDraft] = useState<Record<string, string>>({});
  const [keyDraft, setKeyDraft] = useState<Record<string, string>>({});
  const [clearKey, setClearKey] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");

  const [prompt, setPrompt] = useState("");
  const [maxTokens, setMaxTokens] = useState(256);
  const [testModelKey, setTestModelKey] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const requestId = useRef<string | null>(null);

  const loadAll = useCallback(async () => {
    const [p, m, b, u] = await Promise.all([aiApi.providers(), aiApi.models(), aiApi.budgets(), aiApi.usage()]);
    return { p, m, b, u };
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadAll().then(
      ({ p, m, b, u }) => {
        if (cancelled) return;
        setProviders(p);
        setModels(m);
        setBudget(b);
        setUsage(u);
      },
      (e: Error) => !cancelled && setError(e.message),
    );
    return () => {
      cancelled = true;
    };
  }, [loadAll]);

  const setNote = (name: string, note: Note) => setNotes((cur) => ({ ...cur, [name]: note }));

  /** Ambil daftar model satu provider; galat provider (mis. "API key not valid") ditampilkan apa adanya di kartunya. */
  async function syncOne(name: string): Promise<void> {
    try {
      const rows = await aiApi.syncModels(name);
      setModels((cur) => [...cur.filter((m) => m.provider !== name), ...rows]);
      setNote(name, rows.length
        ? { ok: true, text: t("ai.provider.found").replace("{n}", String(rows.length)) }
        : { ok: false, text: t("ai.provider.noModels") });
    } catch (e) {
      setNote(name, { ok: false, text: `${t("ai.provider.syncFailed")}: ${(e as Error).message}` });
    }
  }

  async function onSave(p: Provider, thenSync: boolean) {
    setBusy(p.name);
    setError(null);
    const typedKey = keyDraft[p.name]?.trim();
    const enabled = enabledDraft[p.name] ?? (typedKey ? true : p.enabled); // mengisi kunci otomatis mengaktifkan provider
    try {
      const updated = await aiApi.updateProvider(p.name, {
        enabled,
        ...(p.name === "ollama" ? { base_url: (urlDraft[p.name] ?? p.base_url ?? "").trim() } : {}),
        ...(p.name !== "ollama" && typedKey ? { api_key: typedKey } : {}),
        ...(p.name !== "ollama" && clearKey[p.name] ? { clear_api_key: true } : {}),
      });
      setProviders((cur) => cur?.map((x) => (x.name === updated.name ? updated : x)) ?? [updated]);
      setKeyDraft((cur) => ({ ...cur, [p.name]: "" }));
      setClearKey((cur) => ({ ...cur, [p.name]: false }));
      setEnabledDraft((cur) => Object.fromEntries(Object.entries(cur).filter(([k]) => k !== p.name)));
      if (updated.enabled && thenSync) await syncOne(p.name);
      else setNote(p.name, { ok: true, text: t(updated.enabled ? "ai.provider.state.up" : "ai.provider.state.off") });
    } catch (e) {
      setNote(p.name, { ok: false, text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  async function onRefetch(p: Provider) {
    setBusy(p.name);
    await syncOne(p.name);
    setBusy(null);
  }

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    const id = crypto.randomUUID();
    requestId.current = id;
    setRunning(true);
    setResult(null);
    setTestError(null);
    try {
      const selected = models.find((m) => `${m.provider}/${m.model_id}` === testModelKey);
      setResult(await aiApi.generate({ prompt, max_tokens: maxTokens, request_id: id, ...(selected ? { provider: selected.provider, model: selected.model_id } : {}) }));
    } catch (err) {
      setTestError((err as Error).message);
    } finally {
      setRunning(false);
      requestId.current = null;
      aiApi.usage().then(setUsage, () => undefined);
    }
  }

  function onCancel() {
    if (requestId.current) aiApi.cancel(requestId.current).catch(() => undefined);
  }

  const tri = (v: boolean | null) => t(v === null ? "tri.unknown" : v ? "tri.yes" : "tri.no");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return models.filter((m) => (!filter || m.provider === filter) && (!q || m.model_id.toLowerCase().includes(q)));
  }, [models, filter, query]);
  const providerNames = useMemo(() => [...new Set(models.map((m) => m.provider))], [models]);

  function stateOf(p: Provider): { key: string; label: string } {
    if (p.kind === "cloud" && !p.api_key_configured) return { key: "off", label: t("ai.provider.state.noKey") };
    if (!p.enabled) return { key: "off", label: t("ai.provider.state.off") };
    if (p.health?.status === "up") return { key: "up", label: t("ai.provider.state.up") };
    const reason = p.health?.error_kind ? t(`ai.provider.errkind.${p.health.error_kind}` as MessageKey) : null;
    return { key: "down", label: reason && !reason.startsWith("ai.provider.errkind") ? reason : t("ai.provider.state.down") };
  }

  return (
    <PageTransition>
<main data-accent="teal" className="wide ai-page">
      <PageHero
        code="06" route="SYS://AI-CORE" art="ai" title={t("ai.title")} hint={t("hero.ai.hint")}
        stats={[
          { label: t("hero.stat.providers"), value: providers?.filter((p) => p.enabled && p.health?.status === "up").length ?? 0, tone: "ok" },
          { label: t("hero.stat.models"), value: models.length },
          { label: t("hero.stat.calls"), value: usage?.summary.total ?? 0 },
          { label: t("hero.stat.paid"), value: t(budget?.allow_paid_calls ? "hero.stat.on" : "hero.stat.off"), tone: budget?.allow_paid_calls ? "bad" : "ok" },
        ]}
      />
      {error && <p className="ai-alert" role="alert">{error}</p>}

      <section aria-label={t("ai.providers")}>
        <div className="ai-section-heading">
          <div><span className="ai-eyebrow">{"// PROVIDER"}</span><h2>{t("ai.providers")}</h2></div>
          {budget && (
            <span className="badge" data-task={budget.allow_paid_calls ? "failed" : "completed"}>
              {t(budget.allow_paid_calls ? "status.paidCalls.on" : "status.paidCalls.off")}
            </span>
          )}
        </div>
        {!providers && !error && <Loading />}
        <div className="prov-grid">
          {providers?.map((p) => {
            const st = stateOf(p);
            const typed = keyDraft[p.name]?.trim();
            const enabled = enabledDraft[p.name] ?? (typed ? true : p.enabled);
            const note = notes[p.name];
            const cloud = p.kind === "cloud";
            const hint = t(`ai.provider.hint.${p.name}` as MessageKey);
            return (
              <article key={p.name} className="prov-card" data-state={st.key}>
                <header className="prov-head">
                  <div>
                    <strong className="prov-name">{p.name}</strong>
                    <span className="muted small"> · {p.is_paid ? t("ai.provider.paid") : t("ai.provider.free")}</span>
                  </div>
                  <span className="prov-dot" data-state={st.key} role="status">{st.label}</span>
                </header>
                {p.health?.status === "up" && p.health.latency_ms != null && <p className="muted small">{p.health.latency_ms} ms{p.health.version ? ` · v${p.health.version}` : ""}</p>}
                <p className="muted small prov-hint">{hint.startsWith("ai.provider.hint") ? "" : hint}</p>

                {p.name === "ollama" ? (
                  <label>{t("ai.provider.endpoint")}
                    <input type="url" value={urlDraft[p.name] ?? p.base_url ?? ""} onChange={(e) => setUrlDraft((c) => ({ ...c, [p.name]: e.target.value }))} placeholder="http://127.0.0.1:11434" />
                  </label>
                ) : (
                  <label>{t("ai.provider.apiKey")} <span className="prov-keystate" data-set={p.api_key_configured ? "1" : "0"}>{t(p.api_key_configured ? "ai.provider.keySaved" : "ai.provider.keyMissing")}</span>
                    <input type="password" autoComplete="new-password" value={keyDraft[p.name] ?? ""}
                      onChange={(e) => { setKeyDraft((c) => ({ ...c, [p.name]: e.target.value })); if (e.target.value) setClearKey((c) => ({ ...c, [p.name]: false })); }}
                      placeholder={t(p.api_key_configured ? "ai.provider.apiKeyConfigured" : "ai.provider.apiKeyPlaceholder")} />
                  </label>
                )}

                <div className="prov-switches">
                  <label className="inline"><input type="checkbox" checked={enabled} onChange={(e) => setEnabledDraft((c) => ({ ...c, [p.name]: e.target.checked }))} />{t("ai.provider.enabledForUse")}</label>
                  {cloud && p.api_key_configured && (
                    <label className="inline"><input type="checkbox" checked={clearKey[p.name] ?? false} onChange={(e) => setClearKey((c) => ({ ...c, [p.name]: e.target.checked }))} />{t("ai.provider.clearApiKey")}</label>
                  )}
                </div>
                {cloud && <p className="muted small">{t("ai.provider.paidNote")}</p>}

                <div className="actions">
                  <button type="button" className="primary-btn" disabled={busy !== null} onClick={() => void onSave(p, true)}>
                    {busy === p.name ? t("ai.provider.saving") : t(cloud ? "ai.provider.saveSync" : "ai.provider.save")}
                  </button>
                  {p.enabled && <button type="button" disabled={busy !== null} onClick={() => void onRefetch(p)}>{t("ai.provider.syncOnly")}</button>}
                </div>
                {note && <p className={`prov-note small ${note.ok ? "ok" : "bad"}`} role={note.ok ? "status" : "alert"}>{note.text}</p>}
              </article>
            );
          })}
        </div>
      </section>

      <WebAccessCard />

      <div className="duo ai-overview-grid">
        <section className="card ai-model-panel">
          <div className="ai-section-heading">
            <div><span className="ai-eyebrow">{"// MODEL"}</span><h2>{t("ai.models")}</h2></div>
            <span className="ai-section-meta">{t("ai.models.count").replace("{n}", String(shown.length))}</span>
          </div>
          <div className="model-tools">
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("ai.models.search")} aria-label={t("ai.models.search")} />
            <div className="actions" role="group">
              <button type="button" aria-pressed={filter === ""} onClick={() => setFilter("")}>{t("ai.models.allProviders")}</button>
              {providerNames.map((n) => <button key={n} type="button" aria-pressed={filter === n} onClick={() => setFilter(n)}>{n}</button>)}
            </div>
          </div>
          {models.length === 0 ? <p>{t("ai.models.empty")}</p> : (
            <ul className="model-list">
              {shown.map((m) => (
                <li key={`${m.provider}/${m.model_id}`} className="model-row" data-available={m.available}>
                  <div>
                    <strong>{m.model_id}</strong> <span className="badge">{m.provider}</span>
                    {m.is_paid && <span className="badge" data-risk="medium">{t("ai.provider.paid")}</span>}
                    {!m.available && <span className="badge">{t("ai.models.unavailable")}</span>}
                    <div className="muted small">
                      {t("ai.models.context")}: {m.context_limit?.toLocaleString() ?? "?"} · {t("ai.models.tools")}: {tri(m.supports_tools)} · {t("ai.models.vision")}: {tri(m.supports_vision)} · {t("ai.models.structured")}: {tri(m.supports_structured)}
                    </div>
                    {m.benchmark && <div className="muted small">JSON {pct(m.benchmark.json_valid_rate)} · Code {pct(m.benchmark.codegen_pass_rate)} · Bugfix {pct(m.benchmark.bugfix_pass_rate)} · {m.benchmark.avg_tok_per_s ?? "?"} tok/s</div>}
                  </div>
                  <span className="badge" data-state={m.validation_status === "benchmarked" ? "active" : undefined}>{t(`ai.models.${m.validation_status}` as MessageKey)}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="muted small">{t("ai.models.unknownHint")}</p>
          <p className="muted small">{t("ai.models.managerRoutingHint")}</p>
        </section>

        {budget && (
          <section className="card ai-budget-panel">
            <div className="ai-section-heading"><div><span className="ai-eyebrow">{"// BUDGET"}</span><h2>{t("ai.budget")}</h2></div></div>
            <dl>
              <dt>{t("ai.budget.paidCalls")}</dt>
              <dd data-state={budget.allow_paid_calls ? "down" : "up"}>{t(budget.allow_paid_calls ? "status.paidCalls.on" : "status.paidCalls.off")}</dd>
              <dt>{t("ai.budget.limit")}</dt>
              <dd>{budget.currency} {budget.monthly_limit.toLocaleString()}</dd>
              <dt>{t("ai.budget.spent")}</dt>
              <dd>{budget.currency} {budget.spent_total.toLocaleString()}</dd>
              <dt>{t("ai.budget.approval")}</dt>
              <dd>{t(budget.require_approval_for_paid_calls ? "tri.yes" : "tri.no")}</dd>
            </dl>
          </section>
        )}
      </div>

      <form className="card ai-playground" onSubmit={onRun}>
        <div className="ai-section-heading"><div><span className="ai-eyebrow">{"// TEST"}</span><h2>{t("ai.test")}</h2></div></div>
        <div className="playground-grid">
          <label>{t("ai.test.model")}
            <select value={testModelKey} onChange={(e) => setTestModelKey(e.target.value)}>
              <option value="">{t("ai.test.defaultModel")}</option>
              {models.filter((m) => m.available && providers?.some((p) => p.name === m.provider && p.enabled && p.implemented))
                .map((m) => <option key={`${m.provider}/${m.model_id}`} value={`${m.provider}/${m.model_id}`}>{m.model_id} ({m.provider})</option>)}
            </select>
          </label>
          <label>{t("ai.test.maxTokens")}
            <input type="number" min={1} max={2048} value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value))} />
          </label>
        </div>
        <label>{t("ai.test.prompt")}
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} maxLength={20000} required />
        </label>
        <div className="actions">
          <button type="submit" className="primary-btn" disabled={running || !prompt.trim()}>{t("ai.test.run")}</button>
          {running && <button type="button" className="danger" onClick={onCancel}>{t("ai.test.cancel")}</button>}
        </div>
        {running && <p className="muted">{t("ai.test.running")}</p>}
        {testError && <p className="bad" role="alert">{testError}</p>}
        {result && (
          <>
            <pre className="output">{result.text}</pre>
            <p className="muted small">
              {result.model} · {result.usage.prompt_tokens ?? "?"}+{result.usage.completion_tokens ?? "?"} tokens ·{" "}
              {result.usage.duration_ms != null ? `${(result.usage.duration_ms / 1000).toFixed(1)} s` : "?"}
            </p>
            {result.truncated && <p className="muted small">{t("ai.test.truncated")}</p>}
          </>
        )}
      </form>

      <section className="card ai-usage-panel">
        <div className="ai-section-heading"><div><span className="ai-eyebrow">{"// USAGE"}</span><h2>{t("ai.usage")}</h2></div></div>
        {usage && usage.summary.total === 0 && <p>{t("ai.usage.empty")}</p>}
        {usage && usage.summary.total > 0 && (
          <>
            <p className="muted small">
              {t("ai.usage.total")} {usage.summary.total} · {t("ai.usage.ok")} {usage.summary.ok} · {t("ai.usage.error")} {usage.summary.error} · {t("ai.usage.blocked")} {usage.summary.blocked} · {t("ai.usage.cancelled")} {usage.summary.cancelled} · {t("ai.usage.tokens")} {usage.summary.prompt_tokens + usage.summary.completion_tokens}
            </p>
            <table>
              <tbody>
                {usage.items.map((u) => (
                  <tr key={u.id}>
                    <td><strong>{u.model}</strong><div className="muted small">{new Date(u.created_at).toLocaleString()}</div></td>
                    <td>
                      <span className="badge" data-state={u.status === "ok" ? "active" : undefined}>{u.status}{u.error_kind ? ` · ${u.error_kind}` : ""}</span>
                      <div className="muted small">{(u.prompt_tokens ?? 0) + (u.completion_tokens ?? 0)} {t("ai.usage.tokens").toLowerCase()} · {u.duration_ms != null ? `${(u.duration_ms / 1000).toFixed(1)} s` : "—"} · IDR {u.cost_idr}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </main>
</PageTransition>
  );
}
