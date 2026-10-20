"use client";

import { useCallback, useEffect, useState } from "react";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

type Health = {
  status: "ok" | "degraded" | "error";
  version: string;
  components: { database: "up" | "down"; ollama: "up" | "down" | "disabled" };
  paid_calls_allowed: boolean;
};

async function fetchHealth(): Promise<Health | null> {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    return res.ok ? ((await res.json()) as Health) : null;
  } catch {
    return null;
  }
}

export function HealthStatus() {
  const { t } = useLanguage();
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  const apply = useCallback((result: Health | null) => {
    setHealth(result);
    setFailed(result === null);
    setLoading(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = () =>
      fetchHealth().then((result) => {
        if (!cancelled) apply(result);
      });
    poll();
    const id = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [apply]);

  const onRefresh = () => {
    setLoading(true);
    fetchHealth().then(apply);
  };

  const val = (v: string) => t(`value.${v}` as MessageKey);

  return (
    <section className="card" aria-live="polite">
      <h2>{t("status.title")}</h2>
      {loading && !health && !failed && <p>{t("status.loading")}</p>}
      {failed && <p className="bad">{t("status.unreachable")}</p>}
      {health && (
        <dl>
          <dt>{t("status.overall")}</dt>
          <dd data-state={health.status}>{val(health.status)} · v{health.version}</dd>
          <dt>{t("status.database")}</dt>
          <dd data-state={health.components.database}>{val(health.components.database)}</dd>
          <dt>{t("status.ollama")}</dt>
          <dd data-state={health.components.ollama}>{val(health.components.ollama)}</dd>
          <dt>{t("status.paidCalls")}</dt>
          <dd data-state={health.paid_calls_allowed ? "down" : "up"}>
            {t(health.paid_calls_allowed ? "status.paidCalls.on" : "status.paidCalls.off")}
          </dd>
        </dl>
      )}
      <button type="button" onClick={onRefresh} disabled={loading}>{t("status.refresh")}</button>
    </section>
  );
}
