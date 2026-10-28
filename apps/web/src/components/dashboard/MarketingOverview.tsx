"use client";

import type { Dashboard } from "@/lib/dashboardApi";
import type { Kpis, SeoCampaign } from "@/lib/seoApi";
import type { DashboardView } from "@/lib/dashboard/dock";
import { Icon } from "@/components/ui/Icons";

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

const ROLE_ICONS: Record<string, string> = {
  manager: "bot",
  seo_specialist: "globe",
  content_promotion: "pen",
  lead_generation: "users",
  sales_client_relations: "mail",
  market_research: "search",
  marketing_analytics: "chart",
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
    bgTint: string;
    icon: string;
  }[] = [
    {
      title: "Total Prospek (Leads)",
      value: num(m?.leads_total),
      hint: `${num(kpis?.leads.qualified)} terkualifikasi • ${num(m?.opportunities_open)} peluang terbuka`,
      view: "leads",
      accentColor: "var(--accent)",
      bgTint: "rgba(234, 88, 12, 0.1)",
      icon: "users",
    },
    {
      title: "Klik Organik",
      value: num(kpis?.organic.clicks),
      hint: `Impresi ${num(kpis?.organic.impressions)} • CTR ${pct(kpis?.organic.ctr)}`,
      view: "seo",
      accentColor: "var(--ok)",
      bgTint: "rgba(22, 163, 74, 0.1)",
      icon: "trend-up",
    },
    {
      title: "Posisi Rata-rata SEO",
      value: num(kpis?.organic.avg_position, 1),
      hint: `Sesi organik ${num(kpis?.organic.organic_sessions)}`,
      view: "seo",
      accentColor: "var(--info)",
      bgTint: "rgba(37, 99, 235, 0.1)",
      icon: "globe",
    },
    {
      title: "Menunggu Persetujuan",
      value: num(pendingApprovals),
      hint: `${num(m?.outbox_waiting)} pesan keluar menunggu tinjauan`,
      view: "operations",
      accentColor: pendingApprovals > 0 ? "var(--warn)" : "var(--text-secondary)",
      bgTint: pendingApprovals > 0 ? "rgba(217, 119, 6, 0.1)" : "var(--surface-subtle)",
      icon: "shield",
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
          <button
            type="button"
            className="btn-secondary"
            onClick={onAudit}
            style={{ display: "inline-flex", alignItems: "center", gap: 7 }}
          >
            <Icon name="globe" size={15} />
            <span>Audit SEO Cepat</span>
          </button>
          <button
            type="button"
            className="btn-primary-orange"
            onClick={onLead}
            style={{ display: "inline-flex", alignItems: "center", gap: 7 }}
          >
            <Icon name="plus" size={15} />
            <span>Catat Prospek B2B</span>
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
            <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="kpi-card-title">{c.title}</span>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "var(--radius-md)",
                  background: c.bgTint,
                  color: c.accentColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <Icon name={c.icon} size={16} />
              </div>
            </div>
            <div className="kpi-card-stat stacked">
              <strong
                style={{
                  color: c.accentColor,
                  fontSize: c.value === NA ? "1.05rem" : undefined,
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
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "var(--accent)", display: "flex" }}>
                <Icon name="users" size={17} />
              </span>
              <span className="white-panel-title">Distribusi Pipeline Prospek</span>
            </div>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("leads")}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <span>Buka CRM</span>
              <Icon name="arrow-right" size={13} />
            </button>
          </div>
          {byStatus.length === 0 ? (
            <div style={{ textAlign: "center", padding: "28px 16px" }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: "var(--surface-subtle)",
                  color: "var(--text-secondary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 10px",
                }}
              >
                <Icon name="users" size={20} />
              </div>
              <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: "0.88rem" }}>
                Belum ada data prospek tercatat
              </p>
              <p className="hint" style={{ margin: "0 auto 14px", maxWidth: 320 }}>
                Tambahkan prospek baru untuk memulai analisis kesiapan sales dan otomatisasi outreach.
              </p>
              <button
                type="button"
                className="btn-secondary"
                onClick={onLead}
                style={{ fontSize: "0.8rem", padding: "6px 14px", display: "inline-flex", alignItems: "center", gap: 6 }}
              >
                <Icon name="plus" size={14} />
                <span>Tambah Prospek Sekarang</span>
              </button>
            </div>
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
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "var(--warn)", display: "flex" }}>
                <Icon name="shield" size={17} />
              </span>
              <span className="white-panel-title">Tindakan Perlu Keputusan</span>
            </div>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("operations")}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <span>Pusat Operasi</span>
              <Icon name="arrow-right" size={13} />
            </button>
          </div>
          {decisions.length === 0 ? (
            <div style={{ textAlign: "center", padding: "28px 16px" }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: "rgba(22, 163, 74, 0.1)",
                  color: "var(--ok)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 10px",
                }}
              >
                <Icon name="check" size={20} />
              </div>
              <p style={{ margin: "0 0 4px", fontWeight: 600, fontSize: "0.88rem" }}>
                Seluruh Alur Kerja Aman &amp; Lancar
              </p>
              <p className="hint" style={{ margin: 0 }}>
                Tidak ada tindakan berisiko yang tertahan atau membutuhkan intervensi persetujuan saat ini.
              </p>
            </div>
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
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                  }}
                >
                  <span style={{ color: d.kind === "approval" ? "var(--warn)" : "var(--bad)", marginTop: 2, flexShrink: 0 }}>
                    <Icon name={d.kind === "approval" ? "clock" : "alert-triangle"} size={16} />
                  </span>
                  <div style={{ flex: 1 }}>
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
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Active SEO & Marketing Campaigns Table */}
      <div className="white-panel">
        <div className="white-panel-header">
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--ok)", display: "flex" }}>
              <Icon name="target" size={17} />
            </span>
            <span className="white-panel-title">Kampanye SEO &amp; Pertumbuhan Berjalan</span>
          </div>
          <button
            type="button"
            className="section-head-link"
            onClick={() => onNavigate("seo")}
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            <span>Kelola Kampanye SEO</span>
            <Icon name="arrow-right" size={13} />
          </button>
        </div>
        {activeCampaigns.length === 0 ? (
          <div style={{ textAlign: "center", padding: "28px 16px" }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: "50%",
                background: "var(--surface-subtle)",
                color: "var(--text-secondary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 10px",
              }}
            >
              <Icon name="target" size={20} />
            </div>
            <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: "0.88rem" }}>
              Belum ada kampanye aktif
            </p>
            <p className="hint" style={{ margin: "0 auto 14px", maxWidth: 360 }}>
              Buat kampanye dengan target terukur pada modul Website &amp; Growth untuk memicu audit rutin dan pelacakan keyword.
            </p>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => onNavigate("seo")}
              style={{ fontSize: "0.8rem", padding: "6px 14px", display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Icon name="plus" size={14} />
              <span>Buka Modul SEO</span>
            </button>
          </div>
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

      {/* Marketing AI Team & Telemetry Summary */}
      <div className="workspace-middle-grid">
        <div className="white-panel">
          <div className="white-panel-header">
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "var(--info)", display: "flex" }}>
                <Icon name="bot" size={17} />
              </span>
              <span className="white-panel-title">Status Tim Agen Marketing AI</span>
            </div>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("operations")}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <span>Lihat Antrean Tugas</span>
              <Icon name="arrow-right" size={13} />
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
                gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
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
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: "50%",
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      color: "var(--accent)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <Icon name={ROLE_ICONS[a.role] ?? "bot"} size={16} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <strong
                        style={{
                          fontSize: "0.78rem",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                        title={ROLE_LABEL[a.role] ?? a.role}
                      >
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
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="white-panel">
          <div className="white-panel-header">
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "var(--accent)", display: "flex" }}>
                <Icon name="sparkles" size={17} />
              </span>
              <span className="white-panel-title">Telemetri AI &amp; Konten (24 Jam)</span>
            </div>
            <button
              type="button"
              className="section-head-link"
              onClick={() => onNavigate("settings")}
              style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              <span>Pengaturan AI</span>
              <Icon name="arrow-right" size={13} />
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
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <span
                  style={{
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  Panggilan AI 24j
                </span>
                <span style={{ color: "var(--info)", display: "flex" }}>
                  <Icon name="zap" size={14} />
                </span>
              </div>
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
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <span
                  style={{
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  Galat AI 24j
                </span>
                <span style={{ color: data && data.ai.errors_24h > 0 ? "var(--bad)" : "var(--text-secondary)", display: "flex" }}>
                  <Icon name="alert-triangle" size={14} />
                </span>
              </div>
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
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <span
                  style={{
                    fontSize: "0.72rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  Konten Siap Tinjau
                </span>
                <span style={{ color: "var(--ok)", display: "flex" }}>
                  <Icon name="file-text" size={14} />
                </span>
              </div>
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
