"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { PageHero } from "@/components/ui/PageHero";
import type { Project } from "@/lib/api";
import { BOARD_COLUMNS, tasksApi, type Agent, type Task, type WorkerStatus } from "@/lib/tasksApi";
import { useTaskEvents } from "@/lib/useTaskEvents";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";
import { Icon } from "@/components/ui/Icons";

export function TasksFeature() {
  const { t, tOr } = useLanguage();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const projectRef = useRef(projectId);

  useEffect(() => {
    projectRef.current = projectId;
  }, [projectId]);

  const refresh = useCallback(async () => {
    const pid = projectRef.current || undefined;
    try {
      const [tk, ag, wk] = await Promise.all([tasksApi.list(pid), tasksApi.agents(pid), tasksApi.worker()]);
      setTasks(tk);
      setAgents(ag.filter((a) => a.department !== "engineering"));
      setWorker(wk);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  const live = useTaskEvents(refresh);

  useEffect(() => {
    let cancelled = false;
    tasksApi.projects().then((p) => !cancelled && setProjects(p), () => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Muat ulang saat proyek diganti; polling berkala hanya jika WebSocket terputus
  useEffect(() => {
    const first = setTimeout(refresh, 0);
    const poll = live ? undefined : setInterval(refresh, 5000);
    return () => {
      clearTimeout(first);
      if (poll) clearInterval(poll);
    };
  }, [projectId, live, refresh]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const onPlan = (e: React.FormEvent) => {
    e.preventDefault();
    act(async () => {
      await tasksApi.plan(projectId, goal);
      setGoal("");
    });
  };

  const hasDrafts = tasks.some((x) => x.status === "draft");
  const label = (key: string) => t(key as MessageKey);

  return (
    <PageTransition>
      <main className="wide" data-accent="cyan">
        <PageHero
          code="02"
          route="SYS://TASKS"
          art="tasks"
          title={t("tasks.title")}
          hint={t("hero.tasks.hint")}
          stats={[
            { label: t("hero.stat.running"), value: tasks.filter((x) => x.status === "running").length, tone: "ok" },
            { label: t("hero.stat.queued"), value: tasks.filter((x) => ["queued", "draft"].includes(x.status)).length },
            { label: t("hero.stat.waiting"), value: tasks.filter((x) => x.status === "pending_approval").length, tone: "warn" },
            { label: t("hero.stat.done"), value: tasks.filter((x) => x.status === "completed").length },
            { label: t("hero.stat.problems"), value: tasks.filter((x) => ["failed", "blocked", "interrupted"].includes(x.status)).length, tone: "bad" },
          ]}
        />
        {error && <p className="bad" role="alert">{error}</p>}
        {tasks.some((x) => x.status === "pending_approval") && (
          <p className="banner">
            {tasks.filter((x) => x.status === "pending_approval").length} {t("tasks.approvalsWaiting")} ·{" "}
            <Link href="/approvals">{t("tasks.openApprovals")}</Link>
          </p>
        )}

        <div className="duo">
          <section className="card">
            <div className="row" style={{ alignItems: "center" }}>
              <label>
                {t("tasks.project")}
                <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                  <option value="">{t("tasks.allProjects")}</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </label>
              <span className="badge" data-state={live ? "active" : undefined}>
                {t(live ? "tasks.live.on" : "tasks.live.off")}
              </span>
              <span className="muted small">
                {t("tasks.worker")}:{" "}
                {!worker?.running ? t("tasks.worker.off") : worker.current_task_id ? t("tasks.worker.busy") : t("tasks.worker.idle")}
              </span>
            </div>

            <form onSubmit={onPlan}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, marginBottom: 8 }}>
                <span style={{ color: "var(--accent)", display: "flex" }}>
                  <Icon name="sparkles" size={17} />
                </span>
                <h3 style={{ margin: 0 }}>{t("tasks.plan.title")}</h3>
              </div>
              {!projectId && <p className="muted">{t("tasks.noProject")}</p>}
              <label>
                {t("tasks.plan.goal")}
                <textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={2} maxLength={2000} disabled={!projectId} />
              </label>
              <div className="actions">
                <button
                  type="submit"
                  disabled={busy || !projectId || !goal.trim()}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <Icon name="plus" size={14} />
                  <span>{t("tasks.plan.run")}</span>
                </button>
                <button
                  type="button"
                  disabled={busy || !projectId || !hasDrafts}
                  onClick={() => act(() => tasksApi.queueDrafts(projectId))}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                >
                  <Icon name="send" size={14} />
                  <span>{t("tasks.queueAll")}</span>
                </button>
              </div>
              <p className="muted small">{t("tasks.plan.hint")}</p>
            </form>
          </section>
        </div>

        <section className="card">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "var(--info)", display: "flex" }}>
              <Icon name="bot" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>{t("tasks.agents")}</h3>
          </div>
          <div className="agents">
            {agents.map((a) => (
              <div key={a.role} className="agent" data-state={a.status}>
                <strong>{label(`role.${a.role}`)}</strong>
                <span className="badge" data-agent={a.status}>{label(`agent.${a.status}`)}</span>
                {a.current_task_title && <div className="muted small">{a.current_task_title}</div>}
                {a.queued > 0 && <div className="muted small">{a.queued} {t("tasks.queued")}</div>}
              </div>
            ))}
          </div>
        </section>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 24, marginBottom: 8 }}>
          <span style={{ color: "var(--accent)", display: "flex" }}>
            <Icon name="list-todo" size={18} />
          </span>
          <h3 style={{ margin: 0 }}>{t("tasks.board")}</h3>
        </div>
        {tasks.length === 0 && <p>{t("tasks.empty")}</p>}
        <div className="board">
          {BOARD_COLUMNS.map((col) => {
            const items = tasks.filter((x) => col.statuses.includes(x.status));
            return (
              <section key={col.key} className="column" data-col={col.key}>
                <h4>{label(`col.${col.key}`)} <span className="muted">({items.length})</span></h4>
                {items.map((x) => (
                  <article key={x.id} className="task" data-risk={x.risk_level} data-status={x.status}>
                    <Link href={`/tasks/${x.id}`}><strong>{x.title}</strong></Link>
                    <div className="muted small">{label(`role.${x.role}`)} · {x.action_type}</div>
                    <div className="chips">
                      <span className="badge" data-risk={x.risk_level}>{label(`risk.${x.risk_level}`)}</span>
                      {x.difficulty_category && <span className="badge">{label(`diff.${x.difficulty_category}`)}</span>}
                      {x.review_status && (
                        <span className="badge" data-task={x.review_status === "approved" ? "completed" : "failed"}>{label(`review.status.${x.review_status}`)}</span>
                      )}
                      {x.attempt_count > 1 && <span className="badge">#{x.attempt_count}</span>}
                    </div>
                    {x.blocked_reason && <div className="muted small">{tOr(`block.${x.blocked_reason}`, x.blocked_reason)}</div>}
                    {x.status === "queued" && (
                      <button
                        type="button"
                        className="danger"
                        disabled={busy}
                        onClick={() => window.confirm(t("task.confirmCancel")) && act(() => tasksApi.cancel(x.id))}
                        style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                      >
                        <Icon name="close" size={13} />
                        <span>{t("task.cancel")}</span>
                      </button>
                    )}
                    {x.status === "draft" && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => act(() => tasksApi.queue(x.id))}
                        style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                      >
                        <Icon name="arrow-right" size={13} />
                        <span>{t("task.queue")}</span>
                      </button>
                    )}
                  </article>
                ))}
              </section>
            );
          })}
        </div>
      </main>
    </PageTransition>
  );
}
