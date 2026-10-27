"use client";

import type { Dashboard } from "@/lib/dashboardApi";
import type { SeoCampaign } from "@/lib/seoApi";
import type { DashboardView } from "@/lib/dashboard/dock";

const ROLE_LABEL: Record<string, string> = {
  manager: "Marketing Manager",
  seo_specialist: "SEO & Website Growth",
  content_promotion: "Content Marketing",
  lead_generation: "Lead Generation",
  sales_client_relations: "CRM & Client Relations",
  market_research: "Riset Pasar",
  marketing_analytics: "Marketing Analytics",
};

type Props = {
  data: Dashboard | null;
  campaigns: SeoCampaign[];
  onNavigate: (v: DashboardView) => void;
  onLead: () => void;
};

// Panel kanan: hanya data marketing nyata (tim agen, pemakaian AI 24 jam, agenda tinjau kampanye).
export function MarketingSidePanel({ data, campaigns, onNavigate, onLead }: Props) {
  const agenda = campaigns
    .filter((c) => c.review_on && !["completed", "archived", "failed"].includes(c.status))
    .sort((a, b) => (a.review_on! < b.review_on! ? -1 : 1))
    .slice(0, 6);

  return (
    <aside className="inspired-sidebar-panel" aria-label="Panel Tim dan Agenda Marketing">
      <div className="profile-card-header">
        <div className="profile-identity">
          <div className="profile-name-group">
            <strong>Roihan AI Office</strong>
            <span>Marketing Operations</span>
          </div>
        </div>
        <button type="button" className="profile-more-btn" title="Tambah Prospek Cepat" onClick={onLead}>+</button>
      </div>

      <div className="profile-stats-row">
        <div className="profile-stat-col">
          <strong>{data ? data.ai.calls_24h : "—"}</strong>
          <span>Panggilan AI 24j</span>
        </div>
        <div className="profile-stat-col">
          <strong>{data ? data.ai.errors_24h : "—"}</strong>
          <span>Galat AI 24j</span>
        </div>
        <div className="profile-stat-col">
          <strong>{data ? data.marketing.content_ready : "—"}</strong>
          <span>Konten siap</span>
        </div>
      </div>

      <div>
        <div className="section-head-title" style={{ marginBottom: 8 }}><span className="section-head-bar">|</span><span>Tim Marketing AI</span></div>
        {!data || data.agents.length === 0 ? (
          <p className="hint">Belum ada data agen.</p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
            {data.agents.filter((a) => a.department !== "engineering").map((a) => (
              <li key={a.role} style={{ fontSize: "0.78rem", padding: "6px 10px", background: "var(--dash-pill-bg)", borderRadius: 10 }}>
                <strong>{ROLE_LABEL[a.role] ?? a.role}</strong>
                <span style={{ display: "block", color: "var(--dash-card-muted)", fontSize: "0.7rem" }}>
                  {a.current_task_title ? `${a.status} • ${a.current_task_title}` : `${a.status} • antrean ${a.queued}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="section-head-title" style={{ marginBottom: 8 }}><span className="section-head-bar">|</span><span>Agenda Tinjau Kampanye</span></div>
        {agenda.length === 0 ? (
          <p className="hint">Belum ada tanggal tinjau kampanye.</p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
            {agenda.map((c) => (
              <li key={c.id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", padding: "6px 10px", background: "var(--dash-pill-bg)", borderRadius: 10, cursor: "pointer" }} onClick={() => onNavigate("campaigns")}>
                <span>{c.name}</span>
                <strong>{c.review_on}</strong>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
