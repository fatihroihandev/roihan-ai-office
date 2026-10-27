"use client";

import type { Dashboard } from "@/lib/dashboardApi";
import type { Kpis, SeoCampaign } from "@/lib/seoApi";
import type { DashboardView } from "@/lib/dashboard/dock";

// Semua angka berasal dari backend. Nilai null/tidak ada ditampilkan sebagai "Belum terhubung"
// (bukan 0) agar data kosong, nol, dan tidak tersedia tidak tertukar.
const NA = "Belum terhubung";
const num = (v: number | null | undefined, digits = 0) =>
  v == null ? NA : v.toLocaleString("id-ID", { maximumFractionDigits: digits });
const pct = (v: number | null | undefined) => (v == null ? NA : `${(v * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`);
const idr = (v: number | null | undefined) => (v == null ? NA : `Rp ${v.toLocaleString("id-ID")}`);

const STATUS_LABEL: Record<string, string> = {
  new: "Baru", qualified: "Terkualifikasi", contacted: "Dihubungi", meeting: "Meeting", disqualified: "Gugur",
};
const OBJECTIVE_LABEL: Record<SeoCampaign["objective"], string> = {
  keyword_rank: "Peringkat keyword", organic_traffic: "Trafik organik", clicks: "Klik", leads: "Leads", conversions: "Konversi",
};
const CAMPAIGN_STATUS_LABEL: Record<SeoCampaign["status"], string> = {
  draft: "Draf", auditing: "Audit", planning: "Perencanaan", active: "Aktif", paused: "Dijeda",
  target_review: "Tinjau target", completed: "Selesai", failed: "Gagal", archived: "Arsip",
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

export function MarketingOverview({ data, kpis, campaigns, pendingApprovals, onNavigate, onAudit, onLead }: Props) {
  const m = data?.marketing;
  const byStatus = Object.entries(m?.by_status ?? {});
  const maxStatus = Math.max(1, ...byStatus.map(([, n]) => n));
  const activeCampaigns = campaigns.filter((c) => !["completed", "archived", "failed"].includes(c.status));
  const decisions = data?.needs_decision ?? [];

  const cards: { title: string; value: string; hint: string; view: DashboardView; color: string }[] = [
    { title: "Leads", value: num(m?.leads_total), hint: `${num(kpis?.leads.qualified)} terkualifikasi • ${num(m?.opportunities_open)} peluang terbuka`, view: "leads", color: "#ec4899" },
    { title: "Klik Organik", value: num(kpis?.organic.clicks), hint: `Impresi ${num(kpis?.organic.impressions)} • CTR ${pct(kpis?.organic.ctr)}`, view: "seo", color: "#10b981" },
    { title: "Posisi Rata-rata", value: num(kpis?.organic.avg_position, 1), hint: `Sesi organik ${num(kpis?.organic.organic_sessions)}`, view: "seo", color: "#3b82f6" },
    { title: "Perlu Persetujuan", value: num(pendingApprovals), hint: `${num(m?.outbox_waiting)} pesan menunggu dikirim manual`, view: "approvals", color: "#f59e0b" },
  ];

  return (
    <>
      <div className="workspace-kpi-grid">
        {cards.map((c) => (
          <div key={c.title} className="kpi-card" onClick={() => onNavigate(c.view)} role="button" tabIndex={0}>
            <div className="kpi-card-top"><span className="kpi-card-title">{c.title}</span></div>
            <div className="kpi-card-stat stacked">
              <strong style={{ color: c.color, fontSize: c.value === NA ? "1rem" : undefined }}>{c.value}</strong>
              <span>{c.hint}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="workspace-middle-grid">
        <div className="white-panel">
          <div className="white-panel-header"><span className="white-panel-title">Pipeline Leads per Status</span></div>
          {byStatus.length === 0 ? (
            <p className="hint">Belum ada leads. Tambahkan prospek pertama lewat tombol di bawah.</p>
          ) : (
            <div style={{ display: "grid", gap: 10, marginTop: 8 }}>
              {byStatus.map(([s, n]) => (
                <div key={s} style={{ display: "grid", gridTemplateColumns: "110px 1fr 36px", alignItems: "center", gap: 10, fontSize: "0.8rem" }}>
                  <span>{STATUS_LABEL[s] ?? s}</span>
                  <div style={{ background: "var(--dash-pill-bg)", borderRadius: 8, height: 10 }}>
                    <div style={{ width: `${(n / maxStatus) * 100}%`, height: "100%", borderRadius: 8, background: "#ff5722" }} />
                  </div>
                  <strong>{n}</strong>
                </div>
              ))}
            </div>
          )}
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            <button type="button" className="btn-primary-orange" onClick={onLead}>+ Catat Prospek</button>
            <button type="button" className="btn-secondary" onClick={onAudit}>⚡ Audit SEO Cepat</button>
          </div>
        </div>

        <div className="white-panel">
          <div className="white-panel-header"><span className="white-panel-title">Perlu Keputusan Anda</span></div>
          {decisions.length === 0 ? (
            <p className="hint">Tidak ada yang menunggu keputusan.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
              {decisions.slice(0, 6).map((d) => (
                <li key={`${d.kind}-${d.id}`} style={{ fontSize: "0.82rem", padding: "8px 10px", background: "var(--dash-pill-bg)", borderRadius: 10 }}>
                  <strong>{d.title}</strong>
                  <span style={{ display: "block", color: "var(--dash-card-muted)", fontSize: "0.72rem" }}>
                    {d.kind === "approval" ? "Menunggu persetujuan" : d.kind === "task_blocked" ? "Tugas terblokir" : "Tugas gagal"}
                    {d.reason ? ` • ${d.reason}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="workspace-bottom-section">
        <div className="section-head-row">
          <div className="section-head-title"><span className="section-head-bar">|</span><span>Kampanye SEO Berjalan</span></div>
          <button type="button" className="section-head-link" onClick={() => onNavigate("campaigns")}>Kelola Kampanye →</button>
        </div>
        {activeCampaigns.length === 0 ? (
          <p className="hint">Belum ada kampanye aktif. Buat kampanye dengan target terukur di menu Kampanye.</p>
        ) : (
          <table className="feature-data-table">
            <thead><tr><th>Kampanye</th><th>Tujuan</th><th>Status</th><th>Target</th><th>Tinjau</th></tr></thead>
            <tbody>
              {activeCampaigns.slice(0, 6).map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{OBJECTIVE_LABEL[c.objective]}</td>
                  <td><span className="badge-sev info">{CAMPAIGN_STATUS_LABEL[c.status]}</span></td>
                  <td>{num(c.target_value)}</td>
                  <td>{c.review_on ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {kpis && kpis.money.cost_idr != null && (
          <p className="hint" style={{ marginTop: 10 }}>
            Biaya {idr(kpis.money.cost_idr)} • Pendapatan {idr(kpis.money.revenue_idr)} • ROI {num(kpis.money.roi, 2)}
          </p>
        )}
        {kpis && kpis.notes.length > 0 && (
          <ul className="hint" style={{ marginTop: 6 }}>{kpis.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        )}
      </div>
    </>
  );
}
