"use client";

import type { Dashboard } from "@/lib/dashboardApi";
import type { Kpis, SeoCampaign } from "@/lib/seoApi";
import type { DashboardView } from "@/lib/dashboard/dock";

const NA = "Belum terhubung";
const num = (v: number | null | undefined, digits = 0) =>
  v == null ? NA : v.toLocaleString("id-ID", { maximumFractionDigits: digits });
const pct = (v: number | null | undefined) =>
  v == null ? NA : `${(v * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
const idr = (v: number | null | undefined) =>
  v == null ? NA : `Rp ${v.toLocaleString("id-ID")}`;

const STATUS_LABEL: Record<string, string> = {
  new: "Baru",
  qualified: "Terkualifikasi",
  contacted: "Dihubungi",
  meeting: "Meeting",
  disqualified: "Gugur",
};

const OBJECTIVE_LABEL: Record<SeoCampaign["objective"], string> = {
  keyword_rank: "Peringkat Keyword",
  organic_traffic: "Trafik Organik",
  clicks: "Klik",
  leads: "Leads",
  conversions: "Konversi",
};

const CAMPAIGN_STATUS_LABEL: Record<SeoCampaign["status"], string> = {
  draft: "Draf",
  auditing: "Audit",
  planning: "Perencanaan",
  active: "Aktif",
  paused: "Dijeda",
  target_review: "Tinjau Target",
  completed: "Selesai",
  failed: "Gagal",
  archived: "Arsip",
};

const ROLE_LABEL: Record<string, string> = {
  manager: "Marketing Director / Orchestrator",
  seo_specialist: "SEO & Website Growth",
  content_promotion: "Content Strategist & Writer",
  lead_generation: "Lead Generation Specialist",
  sales_client_relations: "CRM & Lifecycle Specialist",
  market_research: "Market Research Analyst",
  marketing_analytics: "Marketing Data Analyst",
};

type Props = {
  data: Dashboard | null;
  kpis: Kpis | null;
  campaigns: SeoCampaign[];
  pendingApprovals: number;
  onNavigate: (v: DashboardView) => void;
  onAudit: () => void;
  onLead: () => void;
};

export function MarketingOverview({
  data,
  kpis,
  campaigns,
  pendingApprovals,
  onNavigate,
  onAudit,
  onLead,
}: Props) {
  const m = data?.marketing;
  const byStatus = Object.entries(m?.by_status ?? {});
  const maxStatus = Math.max(1, ...byStatus.map(([, n]) => n));
  const activeCampaigns = campaigns.filter(
    (c) => !["completed", "archived", "failed"].includes(c.status)
  );
  const decisions = data?.needs_decision ?? [];
  const marketingAgents = (data?.agents ?? []).filter(
    (a) => a.department !== "engineering"
  );

  const cards: {
    title: string;
    value: string;
    hint: string;
    view: DashboardView;
    accentColor: string;
  }[] = [
    {
      title: "Total Prospek (Leads)",
      value: num(m?.leads_total),
      hint: `${num(kpis?.leads.qualified)} terkualifikasi • ${num(m?.opportunities_open)} peluang terbuka`,
      view: "leads",
      accentColor: "var(--accent)",
    },
    {
      title: "Klik Organik",
      value: num(kpis?.organic.clicks),
      hint: `Impresi ${num(kpis?.organic.impressions)} • CTR ${pct(kpis?.organic.ctr)}`,
      view: "seo",
      accentColor: "var(--ok)",
    },
    {
      title: "Posisi Rata-rata SEO",
      value: num(kpis?.organic.avg_position, 1),
      hint: `Sesi organik ${num(kpis?.organic.organic_sessions)}`,
      view: "seo",
      accentColor: "var(--info)",
    },
    {
      title: "Menunggu Persetujuan",
      value: num(pendingApprovals),
      hint: `${num(m?.outbox_waiting)} pesan keluar menunggu tinjauan`,
      view: "operations",
      accentColor: pendingApprovals > 0 ? "var(--warn)" : "var(--text)",
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Page Header & Primary Actions */}
      <div className="workspace-header">
        <div className="workspace-greeting">
          <h2>Marketing Command Center</h2>
          <p>
            Ringkasan performa akuisisi, pertumbuhan organik, pipeline CRM, dan antrean kerja agen AI.
          </p>
        </div>
        <div className="workspace-header-actions">
          <button type="button" className="btn-secondary" onClick={onAudit}>
            Audit SEO Cepat
          </button>
          <button type="button" className="btn-primary-orange" onClick={onLead}>
            + Catat Prospek B2B
          </button>
        </div>
      </div>

      {/* 4 Primary KPI Metrics */}
      <div className="workspace-kpi-grid">
        {cards.map((c) => (
          <div
            key={c.title}
            className="kpi-card"
            onClick={() => onNavigate(c.view)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") onNavigate(c.view);
            }}
          >
            <div className="kpi-card-top">
              <span className="kpi-card-title">{c.title}</span>
            </div>
            <div className="kpi-card-stat stacked">
              <strong
                style={{
                  color: c.accentColor,
                  fontSize: c.value === NA ? "1rem" : undefined,
                }}
              >
                {c.value}
              </strong>
              <span>{c.hint}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Middle Row: CRM Lead Pipeline + Pending Decisions */}
      <div className="workspace-middle-grid">
        <div className="white-panel">
          <div className="white-panel-header">
            <span className="white-panel-title">Distribusi Pipeline Prospek</span>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("leads")}
            >
              Buka CRM →
            </button>
          </div>
          {byStatus.length === 0 ? (
            <p className="hint" style={{ margin: 0 }}>
              Belum ada data prospek tercatat. Tambahkan prospek baru untuk memulai kualifikasi.
            </p>
          ) : (
            <div style={{ display: "grid", gap: 10 }}>
              {byStatus.map(([s, n]) => (
                <div
                  key={s}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "120px 1fr 40px",
                    alignItems: "center",
                    gap: 12,
                    fontSize: "0.82rem",
                  }}
                >
                  <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>
                    {STATUS_LABEL[s] ?? s}
                  </span>
                  <div
                    style={{
                      background: "var(--surface-subtle)",
                      borderRadius: 6,
                      height: 8,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${(n / maxStatus) * 100}%`,
                        height: "100%",
                        borderRadius: 6,
                        background: "var(--accent)",
                      }}
                    />
                  </div>
                  <strong style={{ textAlign: "right" }}>{n}</strong>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="white-panel">
          <div className="white-panel-header">
            <span className="white-panel-title">Tindakan Perlu Keputusan</span>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("operations")}
            >
              Pusat Operasi →
            </button>
          </div>
          {decisions.length === 0 ? (
            <p className="hint" style={{ margin: 0 }}>
              Tidak ada tindakan yang tertahan. Seluruh alur kerja berjalan normal.
            </p>
          ) : (
            <ul
              style={{
                listStyle: "none",
                margin: 0,
                padding: 0,
                display: "grid",
                gap: 8,
              }}
            >
              {decisions.slice(0, 5).map((d) => (
                <li
                  key={`${d.kind}-${d.id}`}
                  style={{
                    fontSize: "0.82rem",
                    padding: "10px 12px",
                    background: "var(--surface-subtle)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <strong>{d.title}</strong>
                  <span
                    style={{
                      display: "block",
                      color: "var(--text-secondary)",
                      fontSize: "0.74rem",
                      marginTop: 2,
                    }}
                  >
                    {d.kind === "approval"
                      ? "Menunggu persetujuan"
                      : d.kind === "task_blocked"
                        ? "Tugas terblokir"
                        : "Tugas gagal"}
                    {d.reason ? ` • ${d.reason}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Active SEO & Marketing Campaigns Table */}
      <div className="white-panel">
        <div className="white-panel-header">
          <span className="white-panel-title">Kampanye SEO &amp; Pertumbuhan Berjalan</span>
          <button
            type="button"
            className="section-head-link"
            onClick={() => onNavigate("seo")}
          >
            Kelola Kampanye SEO →
          </button>
        </div>
        {activeCampaigns.length === 0 ? (
          <p className="hint" style={{ margin: 0 }}>
            Belum ada kampanye aktif. Buat kampanye dengan target terukur pada modul Website &amp; Growth.
          </p>
        ) : (
          <table className="feature-data-table">
            <thead>
              <tr>
                <th>Kampanye</th>
                <th>Objektif</th>
                <th>Status</th>
                <th>Target</th>
                <th>Jadwal Tinjau</th>
              </tr>
            </thead>
            <tbody>
              {activeCampaigns.slice(0, 6).map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong>{c.name}</strong>
                  </td>
                  <td>{OBJECTIVE_LABEL[c.objective]}</td>
                  <td>
                    <span className="badge-sev info">
                      {CAMPAIGN_STATUS_LABEL[c.status]}
                    </span>
                  </td>
                  <td>{num(c.target_value)}</td>
                  <td>{c.review_on ? c.review_on.slice(0, 10) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {kpis && kpis.money.cost_idr != null && (
          <p className="hint" style={{ marginTop: 12, marginBottom: 0 }}>
            Biaya tercatat: {idr(kpis.money.cost_idr)} • Pendapatan:{" "}
            {idr(kpis.money.revenue_idr)} • ROI: {num(kpis.money.roi, 2)}
          </p>
        )}
      </div>

      {/* Marketing AI Team & Telemetry Summary (Consolidated from former right panel) */}
      <div className="workspace-middle-grid">
        <div className="white-panel">
          <div className="white-panel-header">
            <span className="white-panel-title">Status Tim Agen Marketing AI</span>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("operations")}
            >
              Lihat Antrean Tugas →
            </button>
          </div>
          {marketingAgents.length === 0 ? (
            <p className="hint" style={{ margin: 0 }}>
              Menunggu sinkronisasi status agen dari server...
            </p>
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))",
                gap: 10,
              }}
            >
              {marketingAgents.map((a) => (
                <div
                  key={a.role}
                  style={{
                    padding: "10px 12px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--border)",
                    background: "var(--surface-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <strong style={{ fontSize: "0.8rem" }}>
                      {ROLE_LABEL[a.role] ?? a.role}
                    </strong>
                    <span className="badge" data-agent={a.status}>
                      {a.status}
                    </span>
                  </div>
                  <span
                    style={{
                      display: "block",
                      fontSize: "0.72rem",
                      color: "var(--text-secondary)",
                      marginTop: 4,
                    }}
                  >
                    {a.current_task_title
                      ? a.current_task_title
                      : `Antrean: ${a.queued} tugas`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="white-panel">
          <div className="white-panel-header">
            <span className="white-panel-title">Telemetri AI &amp; Konten (24 Jam)</span>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("settings")}
            >
              Pengaturan AI →
            </button>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 10,
            }}
          >
            <div
              style={{
                padding: 12,
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border)",
                background: "var(--surface-subtle)",
              }}
            >
              <span
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-secondary)",
                  display: "block",
                }}
              >
                Panggilan AI 24j
              </span>
              <strong style={{ fontSize: "1.25rem" }}>
                {data ? data.ai.calls_24h : "—"}
              </strong>
            </div>
            <div
              style={{
                padding: 12,
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border)",
                background: "var(--surface-subtle)",
              }}
            >
              <span
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-secondary)",
                  display: "block",
                }}
              >
                Galat AI 24j
              </span>
              <strong
                style={{
                  fontSize: "1.25rem",
                  color:
                    data && data.ai.errors_24h > 0
                      ? "var(--bad)"
                      : "var(--text)",
                }}
              >
                {data ? data.ai.errors_24h : "—"}
              </strong>
            </div>
            <div
              style={{
                padding: 12,
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border)",
                background: "var(--surface-subtle)",
              }}
            >
              <span
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-secondary)",
                  display: "block",
                }}
              >
                Konten Siap Tinjau
              </span>
              <strong style={{ fontSize: "1.25rem", color: "var(--ok)" }}>
                {data ? data.marketing.content_ready : "—"}
              </strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
