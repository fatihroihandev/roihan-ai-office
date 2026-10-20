"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { tasksApi, type TaskDetail } from "@/lib/tasksApi";
import { useTaskEvents } from "@/lib/useTaskEvents";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const fmtMs = (ms?: number | null) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)} s`);

export default function TaskDetailPage() {
  const { t, tOr } = useLanguage();
  const { id } = useParams<{ id: string }>();
  const [task, setTask] = useState<TaskDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setTask(await tasksApi.get(id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  const live = useTaskEvents(refresh);

  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const poll = live ? undefined : setInterval(refresh, 5000);
    return () => {
      clearTimeout(first);
      if (poll) clearInterval(poll);
    };
  }, [live, refresh]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const label = (key: string) => t(key as MessageKey);
  const canQueue = task?.status === "draft";
  const canRetry = task && ["failed", "blocked", "interrupted"].includes(task.status);
  const canCancel = task && !["completed", "cancelled"].includes(task.status);

  return (
    <main className="wide">
      <AppHeader />
      <p><Link href="/tasks">← {t("task.back")}</Link></p>
      {error && <p className="bad" role="alert">{error}</p>}
      {!task && !error && <p>{t("common.loading")}</p>}

      {task && (
        <>
          <section className="card">
            <h2>{task.title}</h2>
            <div className="chips">
              <span className="badge" data-task={task.status}>{label(`status.task.${task.status}`)}</span>
              <span className="badge">{label(`role.${task.role}`)}</span>
              <span className="badge">{task.action_type}</span>
              <span className="badge" data-risk={task.risk_level}>{label(`risk.${task.risk_level}`)}</span>
              {task.difficulty_category && (
                <span className="badge">{label(`diff.${task.difficulty_category}`)} ({task.difficulty_score})</span>
              )}
            </div>
            {task.description && <p>{task.description}</p>}
            {task.blocked_reason && (
              <p className="muted">{t("task.blockedBecause")}: {tOr(`block.${task.blocked_reason}`, task.blocked_reason)}</p>
            )}
            {task.status === "pending_approval" && <p className="muted">{t("task.approvalNote")}</p>}
            {task.last_error && <p className="bad">{t("task.error")}: {task.last_error}</p>}
            {task.status === "queued" && task.attempt_count > 0 && (
              <p className="muted small">{t("task.retryAt")} {new Date(task.available_at + "Z").toLocaleTimeString()}</p>
            )}
            <div className="actions">
              {canQueue && <button type="button" disabled={busy} onClick={() => act(() => tasksApi.queue(id))}>{t("task.queue")}</button>}
              {canRetry && <button type="button" disabled={busy} onClick={() => act(() => tasksApi.retry(id))}>{t("task.retry")}</button>}
              {canCancel && (
                <button type="button" className="danger" disabled={busy}
                  onClick={() => window.confirm(t("task.confirmCancel")) && act(() => tasksApi.cancel(id))}>
                  {t("task.cancel")}
                </button>
              )}
            </div>
          </section>

          {task.acceptance_criteria.length > 0 && (
            <section className="card">
              <h3>{t("task.criteria")}</h3>
              <ul>{task.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
            </section>
          )}

          {task.depends_on.length > 0 && (
            <section className="card">
              <h3>{t("task.deps")}</h3>
              <ul>{task.depends_on.map((d) => <li key={d}><Link href={`/tasks/${d}`}>{d.slice(0, 8)}</Link></li>)}</ul>
            </section>
          )}

          {task.result && (
            <section className="card">
              <h3>{t("task.result")}</h3>
              {task.verification && (
                <p className="muted small">
                  {task.verification.criteria_checked === false ? t("task.notVerified") : task.verification.method}
                </p>
              )}
              {task.result.output && <pre className="output">{task.result.output}</pre>}
              {task.result.artifact && <p className="muted small">{t("task.artifact")}: {task.result.artifact}</p>}
              {task.result.files && task.result.files.length > 0 && (
                <p className="muted small">
                  {t("task.files")}: {task.result.files.map((f) => f.path).join(", ")}
                  {task.result.commit ? ` · ${t("task.commit")} ${task.result.commit}` : ""}
                </p>
              )}
              {task.result.created_task_ids && (
                <>
                  <p className="muted small">{t("task.createdTasks")}: {task.result.created_task_ids.length}</p>
                  <ul>
                    {task.result.created_task_ids.map((c) => <li key={c}><Link href={`/tasks/${c}`}>{c.slice(0, 8)}</Link></li>)}
                  </ul>
                </>
              )}
            </section>
          )}

          <section className="card">
            <h3>{t("task.attempts")}</h3>
            {task.attempts.length === 0 ? <p>{t("task.noAttempts")}</p> : (
              <table><tbody>
                {task.attempts.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <strong>#{a.number}</strong> <span className="badge">{a.status}</span>
                      {a.error_kind && <span className="badge" data-risk="high">{a.error_kind}</span>}
                      <div className="muted small">
                        {a.model ?? "—"} · {a.usage?.calls ?? 0} calls · {(a.usage?.prompt_tokens ?? 0) + (a.usage?.completion_tokens ?? 0)} tokens · {fmtMs(a.usage?.duration_ms)}
                      </div>
                      {a.error_message && <div className="bad small">{a.error_message}</div>}
                    </td>
                  </tr>
                ))}
              </tbody></table>
            )}
          </section>

          {task.routing.length > 0 && (
            <section className="card">
              <h3>{t("task.routing")}</h3>
              <table><tbody>
                {task.routing.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.provider}/{r.model}</strong>
                      <div className="muted small">{t("task.context")} {r.num_ctx} · {r.reasons.join(" · ")}</div>
                      <div className="muted small">
                        {r.candidates.map((c) => `${c.model}${c.eligible ? " ✓" : ` ✗ (${c.rejected_because.join(", ")})`}`).join(" | ")}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody></table>
            </section>
          )}

          {task.test_runs.length > 0 && (
            <section className="card">
              <h3>{t("task.tests")}</h3>
              {task.test_runs.map((r) => (
                <div key={r.id}>
                  <div className="chips">
                    <span className="badge" data-task={r.status === "passed" ? "completed" : "failed"}>{r.status}</span>
                    <span className="muted small">
                      {r.passed} {t("task.tests.passed")} · {r.failed} {t("task.tests.failed")} · {r.errors} {t("task.tests.errors")} · {r.skipped} {t("task.tests.skipped")}
                    </span>
                  </div>
                  <table><tbody>
                    {r.results.map((x, i) => (
                      <tr key={i}>
                        <td>
                          <span className="badge" data-task={x.outcome === "passed" ? "completed" : x.outcome === "skipped" ? undefined : "failed"}>{x.outcome}</span>{" "}
                          {x.name}
                          {x.message && <div className="bad small">{x.message}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody></table>
                </div>
              ))}
            </section>
          )}

          {task.executions.length > 0 && (
            <section className="card">
              <h3>{t("task.executions")}</h3>
              {task.executions.map((e) => (
                <details key={e.id}>
                  <summary>
                    <span className="badge" data-task={e.status === "ok" ? "completed" : "failed"}>{e.status}</span>{" "}
                    <strong>{e.kind}</strong> · {t("task.exec.exit")} {e.exit_code ?? "—"} · {fmtMs(e.duration_ms)} · {e.sandbox}
                  </summary>
                  <p className="muted small"><code>{e.argv.join(" ")}</code></p>
                  {e.stdout && <pre className="output">{e.stdout}</pre>}
                  {e.stderr && <pre className="output">{e.stderr}</pre>}
                </details>
              ))}
            </section>
          )}

          <section className="card">
            <h3>{t("task.events")}</h3>
            <table><tbody>
              {task.events.map((e) => (
                <tr key={e.seq}>
                  <td className="muted small">{new Date(e.created_at + "Z").toLocaleTimeString()}</td>
                  <td>
                    {e.from_status ? `${e.from_status} → ` : ""}<strong>{e.to_status}</strong>
                    {e.reason && <span className="muted small"> · {e.reason}</span>}
                  </td>
                </tr>
              ))}
            </tbody></table>
          </section>
        </>
      )}
    </main>
  );
}
