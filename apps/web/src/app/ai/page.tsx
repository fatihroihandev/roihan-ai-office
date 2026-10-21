"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { Loading, PageHero } from "@/components/ui/PageHero";
import { aiApi, pct, type Budget, type GenerateResult, type ModelRow, type Provider, type UsageResponse } from "@/lib/aiApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function AiControlCenterPage() {
  const { t } = useLanguage();
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [models, setModels] = useState<ModelRow[]>([]);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const [prompt, setPrompt] = useState("");
  const [maxTokens, setMaxTokens] = useState(256);
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

  async function onSync() {
    setSyncing(true);
    setError(null);
    try {
      setModels(await aiApi.syncModels());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  }

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    const id = crypto.randomUUID();
    requestId.current = id;
    setRunning(true);
    setResult(null);
    setTestError(null);
    try {
      setResult(await aiApi.generate({ prompt, max_tokens: maxTokens, request_id: id }));
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

  return (
    <main data-accent="teal">
      <AppHeader />
      <PageHero
        code="06" route="SYS://AI-CORE" art="ai" title={t("ai.title")} hint={t("hero.ai.hint")}
        stats={[
          { label: t("hero.stat.providers"), value: providers?.filter((p) => p.enabled && p.health?.status === "up").length ?? 0, tone: "ok" },
          { label: t("hero.stat.models"), value: models.length },
          { label: t("hero.stat.calls"), value: usage?.summary.total ?? 0 },
          { label: t("hero.stat.paid"), value: t(budget?.allow_paid_calls ? "hero.stat.on" : "hero.stat.off"), tone: budget?.allow_paid_calls ? "bad" : "ok" },
        ]}
      />
      {error && <p className="bad" role="alert">{error}</p>}

      <div className="duo">
      <section className="card">
        <h3>{t("ai.providers")}</h3>
        {!providers && !error && <Loading />}
        <table>
          <tbody>
            {providers?.map((p) => {
              const state = !p.enabled ? "disabled" : !p.implemented ? "disabled" : p.health?.status ?? "down";
              const label = !p.enabled
                ? t("ai.provider.disabled")
                : !p.implemented
                  ? t("ai.provider.notImplemented")
                  : t(`value.${p.health?.status ?? "down"}` as MessageKey);
              return (
                <tr key={p.name}>
                  <td>
                    <strong>{p.name}</strong>
                    <div className="muted small">{p.is_paid ? t("ai.provider.paid") : t("ai.provider.free")}</div>
                  </td>
                  <td className="actions">
                    <span className="badge" data-state={state === "up" ? "active" : undefined}>{label}</span>
                    {p.health?.status === "up" && (
                      <span className="muted small">{p.health.latency_ms} ms · v{p.health.version}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {budget && (
        <section className="card">
          <h3>{t("ai.budget")}</h3>
          <dl>
            <dt>{t("ai.budget.paidCalls")}</dt>
            <dd data-state={budget.allow_paid_calls ? "down" : "up"}>
              {t(budget.allow_paid_calls ? "status.paidCalls.on" : "status.paidCalls.off")}
            </dd>
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

      <div className="duo">
      <section className="card">
        <h3>{t("ai.models")}</h3>
        <button type="button" onClick={onSync} disabled={syncing}>
          {t(syncing ? "ai.models.syncing" : "ai.models.sync")}
        </button>
        {models.length === 0 ? (
          <p>{t("ai.models.empty")}</p>
        ) : (
          <table>
            <tbody>
              {models.map((m) => (
                <tr key={`${m.provider}/${m.model_id}`}>
                  <td>
                    <strong>{m.model_id}</strong>
                    {!m.available && <span className="badge">{t("ai.models.unavailable")}</span>}
                    <div className="muted small">
                      {t("ai.models.context")}: {m.context_limit?.toLocaleString() ?? "?"} · {t("ai.models.tools")}: {tri(m.supports_tools)} ·{" "}
                      {t("ai.models.vision")}: {tri(m.supports_vision)} · {t("ai.models.structured")}: {tri(m.supports_structured)}
                    </div>
                  </td>
                  <td>
                    <span className="badge" data-state={m.validation_status === "benchmarked" ? "active" : undefined}>
                      {t(`ai.models.${m.validation_status}` as MessageKey)}
                    </span>
                    {m.benchmark && (
                      <div className="muted small">
                        JSON {pct(m.benchmark.json_valid_rate)} · Code {pct(m.benchmark.codegen_pass_rate)} · Bugfix{" "}
                        {pct(m.benchmark.bugfix_pass_rate)} · {m.benchmark.avg_tok_per_s ?? "?"} tok/s
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted small">{t("ai.models.unknownHint")}</p>
      </section>

      <form className="card" onSubmit={onRun}>
        <h3>{t("ai.test")}</h3>
        <label>
          {t("ai.test.prompt")}
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} maxLength={20000} required />
        </label>
        <label>
          {t("ai.test.maxTokens")}
          <input type="number" min={1} max={2048} value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value))} />
        </label>
        <div className="actions">
          <button type="submit" disabled={running || !prompt.trim()}>{t("ai.test.run")}</button>
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

      </div>

      <section className="card">
        <h3>{t("ai.usage")}</h3>
        {usage && usage.summary.total === 0 && <p>{t("ai.usage.empty")}</p>}
        {usage && usage.summary.total > 0 && (
          <>
            <p className="muted small">
              {t("ai.usage.total")} {usage.summary.total} · {t("ai.usage.ok")} {usage.summary.ok} · {t("ai.usage.error")}{" "}
              {usage.summary.error} · {t("ai.usage.blocked")} {usage.summary.blocked} · {t("ai.usage.cancelled")}{" "}
              {usage.summary.cancelled} · {t("ai.usage.tokens")} {usage.summary.prompt_tokens + usage.summary.completion_tokens}
            </p>
            <table>
              <tbody>
                {usage.items.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <strong>{u.model}</strong>
                      <div className="muted small">{new Date(u.created_at).toLocaleString()}</div>
                    </td>
                    <td>
                      <span className="badge" data-state={u.status === "ok" ? "active" : undefined}>
                        {u.status}{u.error_kind ? ` · ${u.error_kind}` : ""}
                      </span>
                      <div className="muted small">
                        {(u.prompt_tokens ?? 0) + (u.completion_tokens ?? 0)} {t("ai.usage.tokens").toLowerCase()} ·{" "}
                        {u.duration_ms != null ? `${(u.duration_ms / 1000).toFixed(1)} s` : "—"} · IDR {u.cost_idr}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </main>
  );
}
