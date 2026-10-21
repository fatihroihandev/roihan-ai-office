"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHero } from "@/components/ui/PageHero";
import { tasksApi, type Approval } from "@/lib/tasksApi";
import { useTaskEvents } from "@/lib/useTaskEvents";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function ApprovalsPage() {
  const { t } = useLanguage();
  const [items, setItems] = useState<Approval[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setItems(await tasksApi.approvals());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const live = useTaskEvents(refresh);

  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const poll = live ? undefined : setInterval(refresh, 5000);
    return () => {
      clearTimeout(first);
      if (poll) clearInterval(poll);
    };
  }, [live, refresh]);

  async function decide(a: Approval, kind: "approve" | "reject") {
    if (!window.confirm(t(kind === "approve" ? "approvals.confirmApprove" : "approvals.confirmReject"))) return;
    setBusy(true);
    setError(null);
    try {
      await (kind === "approve" ? tasksApi.approve(a.id, reasons[a.id]) : tasksApi.reject(a.id, reasons[a.id]));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      await refresh();
    }
  }

  const label = (key: string) => t(key as MessageKey);
  const pending = items.filter((a) => a.status === "pending");
  const history = items.filter((a) => a.status !== "pending");

  return (
    <PageTransition>
<main className="wide" data-accent="amber">
      <PageHero
        code="05" route="SYS://APPROVALS" art="approvals" title={t("approvals.title")} hint={t("approvals.hint")}
        stats={[
          { label: t("hero.stat.pending"), value: pending.length, tone: pending.length > 0 ? "warn" : undefined },
          { label: t("hero.stat.critical"), value: pending.filter((a) => a.risk_level === "critical").length, tone: "bad" },
          { label: t("hero.stat.history"), value: history.length },
        ]}
      />
      {error && <p className="bad" role="alert">{error}</p>}

      <h3>{t("approvals.pending")} ({pending.length})</h3>
      {pending.length === 0 && <p>{t("approvals.none")}</p>}
      {pending.map((a) => (
        <section className="card approval" key={a.id} data-risk={a.risk_level}>
          <div className="chips">
            <span className="badge" data-risk={a.risk_level}>{label(`risk.${a.risk_level}`)}</span>
            <span className="badge">{label(`role.${a.payload.role}`)}</span>
            <span className="badge">{a.payload.action_type}</span>
          </div>
          <h4>{t("approvals.whatYouApprove")}: {a.payload.title}</h4>
          {a.payload.description && <p>{a.payload.description}</p>}
          {a.payload.params && (
            <div>
              <p className="small muted">{t("approvals.params")}</p>
              <dl>
                {Object.entries(a.payload.params).map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt>{k}</dt><dd className="small" style={{ fontWeight: 400, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{typeof v === "string" ? v : JSON.stringify(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
          {a.payload.acceptance_criteria.length > 0 && <ul>{a.payload.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>}
          <p className="muted small">
            {t("approvals.requestedBy")} {a.requested_by} · {t("approvals.expires")} {new Date(a.expires_at + "Z").toLocaleString()} ·{" "}
            <Link href={`/tasks/${a.task_id}`}>{t("approvals.openTask")}</Link>
          </p>
          <label>
            {t("approvals.reason")}
            <input value={reasons[a.id] ?? ""} maxLength={1000} onChange={(e) => setReasons((r) => ({ ...r, [a.id]: e.target.value }))} />
          </label>
          <div className="actions">
            <button type="button" disabled={busy} onClick={() => decide(a, "approve")}>{t("approvals.approve")}</button>
            <button type="button" className="danger" disabled={busy} onClick={() => decide(a, "reject")}>{t("approvals.reject")}</button>
          </div>
        </section>
      ))}

      <h3>{t("approvals.history")}</h3>
      {history.length === 0 ? <p className="muted">{t("approvals.noHistory")}</p> : (
        <section className="card">
          <table><tbody>
            {history.map((a) => (
              <tr key={a.id}>
                <td>
                  <span className="badge" data-task={a.status === "approved" ? "completed" : "failed"}>{label(`approval.status.${a.status}`)}</span>{" "}
                  <strong>{a.payload.title}</strong> <span className="badge" data-risk={a.risk_level}>{label(`risk.${a.risk_level}`)}</span>
                  <div className="muted small">
                    {a.decided_by ? `${t("approvals.decidedBy")} ${a.decided_by}` : ""}{a.decided_at ? ` · ${new Date(a.decided_at + "Z").toLocaleString()}` : ""}
                    {a.used_at ? ` · ${t("approvals.usedOnce")}` : ""} · <Link href={`/tasks/${a.task_id}`}>{t("approvals.openTask")}</Link>
                  </div>
                  {a.decision_reason && <div className="muted small">{a.decision_reason}</div>}
                </td>
              </tr>
            ))}
          </tbody></table>
        </section>
      )}
    </main>
</PageTransition>
  );
}
