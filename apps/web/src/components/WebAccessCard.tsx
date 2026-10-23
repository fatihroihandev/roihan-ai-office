"use client";

import { useCallback, useEffect, useState } from "react";
import { webApi, type SearchHit, type WebLogRow, type WebStatus } from "@/lib/webApi";
import { useLanguage } from "@/i18n/LanguageProvider";

/** Kartu pengaturan akses web agent (AI Control Center): saklar, batas harian, kunci pencarian, uji pencarian, dan log permintaan. */
export function WebAccessCard() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<WebStatus | null>(null);
  const [provider, setProvider] = useState<"brave" | "tavily">("brave");
  const [log, setLog] = useState<WebLogRow[]>([]);
  const [key, setKey] = useState("");
  const [limit, setLimit] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const providerSelectionAvailable = Boolean(status?.search_provider && status.api_keys_configured);
  const providerKeyConfigured = status?.api_keys_configured?.[provider]
    ?? (provider === (status?.search_provider ?? "brave") && Boolean(status?.api_key_configured));

  const load = useCallback(() => {
    webApi.status().then((s) => {
      setStatus(s);
      setProvider(s.search_provider === "tavily" ? "tavily" : "brave");
    }, (e: Error) => setMsg({ ok: false, text: e.message }));
    webApi.requests().then(setLog, () => undefined);
  }, []);
  useEffect(() => load(), [load]);

  async function save(patch: Parameters<typeof webApi.update>[0], ok: string) {
    setBusy(true);
    setMsg(null);
    try {
      setStatus(await webApi.update(patch));
      setKey("");
      setMsg({ ok: true, text: ok });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setMsg(null);
    setHits(null);
    try {
      setHits((await webApi.search(query)).results);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
      load();
    }
  }

  return (
    <section className="card web-card" aria-label={t("web.title")}>
      <div className="ai-section-heading">
        <div><span className="ai-eyebrow">{"// WEB"}</span><h2>{t("web.title")}</h2></div>
        {status && <span className="badge" data-task={status.enabled ? "failed" : "completed"}>{t(status.enabled ? "web.on" : "web.off")}</span>}
      </div>
      <p className="muted small">{t("web.hint")}</p>
      {status && (
        <>
          <p className="small">{t("web.usage").replace("{u}", String(status.used_today)).replace("{l}", String(status.daily_limit))}</p>
          <div className="prov-switches">
            <label className="inline">
              <input type="checkbox" checked={status.enabled} disabled={busy} onChange={(e) => void save({ enabled: e.target.checked }, t(e.target.checked ? "web.enabledMsg" : "web.disabledMsg"))} />
              {t("web.enable")}
            </label>
          </div>
          <label>{t("web.searchProvider")}
            <select value={provider} disabled={busy || !providerSelectionAvailable} onChange={(e) => setProvider(e.target.value as "brave" | "tavily")}>
              <option value="brave">Brave Search</option>
              <option value="tavily">Tavily</option>
            </select>
          </label>
          {!providerSelectionAvailable && <p className="muted small">{t("web.restartBackendForProvider")}</p>}
          {provider === "tavily" && <p className="muted small">{t("web.tavilyFree")} <a href="https://www.tavily.com/pricing" target="_blank" rel="noreferrer">{t("web.tavilyPricing")}</a></p>}
          <div className="playground-grid">
            <label>{provider === "tavily" ? t("web.tavilyApiKey") : t("web.apiKey")} <span className="prov-keystate" data-set={providerKeyConfigured ? "1" : "0"}>{t(providerKeyConfigured ? "ai.provider.keySaved" : "ai.provider.keyMissing")}</span>
              <input type="password" autoComplete="new-password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={t(providerKeyConfigured ? "ai.provider.apiKeyConfigured" : "ai.provider.apiKeyPlaceholder")} />
            </label>
            <label>{t("web.limit")}
              <input type="number" min={1} max={5000} value={limit || String(status.daily_limit)} onChange={(e) => setLimit(e.target.value)} />
            </label>
          </div>
          <div className="actions">
            <button type="button" className="primary-btn" disabled={busy || (!providerSelectionAvailable && provider !== "brave")} onClick={() => void save({ ...(providerSelectionAvailable ? { web_search_provider: provider } : {}), ...(key.trim() ? provider === "tavily" ? { tavily_api_key: key.trim() } : { brave_api_key: key.trim() } : {}), ...(limit ? { daily_limit: Number(limit) } : {}) }, t("web.saved"))}>{t("ai.provider.save")}</button>
            {providerKeyConfigured && providerSelectionAvailable && <button type="button" className="danger" disabled={busy} onClick={() => void save({ web_search_provider: provider, clear_api_key: true }, t("web.keyCleared"))}>{t("ai.provider.clearApiKey")}</button>}
          </div>
          <div className="model-tools">
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("web.testPlaceholder")} aria-label={t("web.test")} />
            <button type="button" disabled={busy || query.trim().length < 2} onClick={() => void test()}>{t("web.test")}</button>
          </div>
        </>
      )}
      {msg && <p className={`prov-note small ${msg.ok ? "ok" : "bad"}`} role={msg.ok ? "status" : "alert"}>{msg.text}</p>}
      {hits && <ul className="model-list">{hits.map((h) => <li key={h.url} className="model-row"><div><strong>{h.title}</strong><div className="muted small">{h.url}</div><div className="small">{h.snippet}</div></div></li>)}</ul>}
      {log.length > 0 && (
        <details>
          <summary className="small muted">{t("web.log")}</summary>
          <ul className="small muted">{log.map((r) => <li key={r.id}>{new Date(r.created_at).toLocaleTimeString()} · {r.kind} · {r.status}{r.detail ? ` (${r.detail})` : ""} · {r.target.slice(0, 70)}</li>)}</ul>
        </details>
      )}
    </section>
  );
}
