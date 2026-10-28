"use client";

import { useEffect, useState, useCallback } from "react";
import { marketingApi, type Analytics, type Lead } from "@/lib/marketingApi";
import { seoApi, type Kpis, type SeoCampaign } from "@/lib/seoApi";
import { Icon } from "@/components/ui/Icons";

const IDR = new Intl.NumberFormat("id-ID");

export function AnalyticsFeature() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [campaigns, setCampaigns] = useState<SeoCampaign[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "funnel" | "attribution">("overview");

  const loadData = useCallback(async () => {
    try {
      const [an, kp, c, l] = await Promise.all([
        marketingApi.analytics(),
        seoApi.kpis(),
        seoApi.campaigns(),
        marketingApi.leads(),
      ]);
      setAnalytics(an);
      setKpis(kp);
      setCampaigns(c);
      setLeads(l);
    } catch {
      // fallback
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(() => {
      void loadData();
    }, 0);
    return () => clearTimeout(id);
  }, [loadData]);

  const handleExportCsv = () => {
    const csvContent =
      "data:text/csv;charset=utf-8," +
      "Metric,Value,Note\n" +
      `Total Leads,${analytics?.leads_total ?? 0},Database aktual\n` +
      `Qualified Leads,${kpis?.leads?.qualified ?? 0},Skor >= 40\n` +
      `Organic Clicks,${kpis?.organic?.clicks ?? 0},Search Console / SEO\n` +
      `Organic Impressions,${kpis?.organic?.impressions ?? 0},Search Console / SEO\n` +
      `Opportunities Open,${analytics?.opportunities_open ?? 0},CRM Pipeline\n` +
      `Recorded Revenue (IDR),${analytics?.revenue_recorded_idr ?? 0},Won Opportunities\n`;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute(
      "download",
      `roihan_marketing_analytics_${new Date().toISOString().slice(0, 10)}.csv`
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const leadsTotal = analytics?.leads_total ?? leads.length;
  const qualifiedTotal =
    kpis?.leads?.qualified ?? leads.filter((l) => (l.score ?? 0) >= 40).length;
  const opportunitiesTotal = analytics?.opportunities_open ?? 0;
  const wonDeals = leads.filter((l) => l.status === "won").length;

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="workspace-header">
        <div className="workspace-greeting">
          <h2>Analytics &amp; Intelligence Hub</h2>
          <p>
            Evaluasi metrik pemasaran aktual, corong konversi penuh, distribusi sumber prospek, dan ekspor laporan.
          </p>
        </div>
        <div className="workspace-header-actions">
          <button
            type="button"
            className={activeTab === "overview" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("overview")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="chart" size={14} />
            <span>Ringkasan Metrik</span>
          </button>
          <button
            type="button"
            className={activeTab === "funnel" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("funnel")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="filter" size={14} />
            <span>Corong Konversi</span>
          </button>
          <button
            type="button"
            className={activeTab === "attribution" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("attribution")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="share" size={14} />
            <span>Atribusi Kanal</span>
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={handleExportCsv}
            title="Unduh laporan dalam format CSV"
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="arrow-up-right" size={14} />
            <span>Ekspor CSV</span>
          </button>
        </div>
      </div>

      {/* Top 4 KPI Metrics */}
      <div className="workspace-kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="kpi-card-title">Klik Organik</span>
            <span style={{ color: "var(--ok)" }}><Icon name="trend-up" size={16} /></span>
          </div>
          <strong style={{ color: "var(--ok)" }}>{kpis?.organic.clicks ?? 0}</strong>
          <span className="small muted">
            Impresi: {kpis?.organic.impressions ?? 0} • CTR:{" "}
            {((kpis?.organic.ctr ?? 0) * 100).toFixed(1)}%
          </span>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="kpi-card-title">Total Prospek (Leads)</span>
            <span style={{ color: "var(--accent)" }}><Icon name="users" size={16} /></span>
          </div>
          <strong style={{ color: "var(--accent)" }}>{leadsTotal}</strong>
          <span className="small muted">
            {qualifiedTotal} terkualifikasi (
            {leadsTotal > 0 ? Math.round((qualifiedTotal / leadsTotal) * 100) : 0}%)
          </span>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="kpi-card-title">Peluang Terbuka (Deals)</span>
            <span style={{ color: "var(--info)" }}><Icon name="target" size={16} /></span>
          </div>
          <strong style={{ color: "var(--info)" }}>{opportunitiesTotal}</strong>
          <span className="small muted">
            Win rate:{" "}
            {analytics?.win_rate != null ? `${Math.round(analytics.win_rate * 100)}%` : "—"}
          </span>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="kpi-card-title">Pendapatan Tercatat</span>
            <span style={{ color: "var(--ok)" }}><Icon name="check-circle" size={16} /></span>
          </div>
          <strong>Rp {IDR.format(analytics?.revenue_recorded_idr ?? 0)}</strong>
          <span className="small muted">
            ROI Kampanye:{" "}
            {kpis?.money.roi != null ? `${(kpis.money.roi * 100).toFixed(0)}%` : "—"}
          </span>
        </div>
      </div>

      {/* Tab: Overview */}
      {activeTab === "overview" && (
        <div className="workspace-middle-grid">
          <div className="white-panel">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <span style={{ color: "var(--accent)", display: "flex" }}>
                <Icon name="users" size={18} />
              </span>
              <h3 style={{ margin: 0 }}>Distribusi Sumber Prospek (Lead Sources)</h3>
            </div>
            {Object.keys(analytics?.by_source ?? {}).length === 0 ? (
              <p className="hint">Belum ada data sumber prospek tercatat.</p>
            ) : (
              <div style={{ display: "grid", gap: 10 }}>
                {Object.entries(analytics?.by_source ?? {}).map(([src, count]) => (
                  <div
                    key={src}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "140px 1fr 40px",
                      alignItems: "center",
                      gap: 10,
                      fontSize: "0.82rem",
                    }}
                  >
                    <span style={{ textTransform: "capitalize" }}>
                      {src.replace("_", " ")}
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
                          width: `${Math.min(100, (count / Math.max(1, leadsTotal)) * 100)}%`,
                          height: "100%",
                          background: "var(--accent)",
                          borderRadius: 6,
                        }}
                      />
                    </div>
                    <strong style={{ textAlign: "right" }}>{count}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="white-panel">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <span style={{ color: "var(--info)", display: "flex" }}>
                <Icon name="target" size={18} />
              </span>
              <h3 style={{ margin: 0 }}>Kampanye SEO &amp; Target Anggaran</h3>
            </div>
            {campaigns.length === 0 ? (
              <p className="hint">Belum ada kampanye SEO yang dikonfigurasi.</p>
            ) : (
              <div style={{ display: "grid", gap: 10, maxHeight: 280, overflowY: "auto" }}>
                {campaigns.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      padding: 12,
                      borderRadius: "var(--radius-md)",
                      background: "var(--surface-subtle)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <strong style={{ fontSize: "0.86rem" }}>{c.name}</strong>
                      <span className="badge">{c.status}</span>
                    </div>
                    <span
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--text-secondary)",
                        display: "block",
                        marginTop: 4,
                      }}
                    >
                      Objektif: {c.objective} • Anggaran API: Rp {IDR.format(c.api_budget_idr)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Funnel */}
      {activeTab === "funnel" && (
        <div className="white-panel">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="filter" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>Corong Konversi Pemasaran (Full Marketing Funnel)</h3>
          </div>
          <div style={{ display: "grid", gap: 14 }}>
            {[
              {
                label: "1. Klik Organik Website",
                val: kpis?.organic.clicks ?? 0,
                color: "var(--ok)",
                pct: "100%",
              },
              {
                label: "2. Prospek Baru Ditangkap (Leads)",
                val: leadsTotal,
                color: "var(--info)",
                pct: kpis?.organic.clicks
                  ? `${Math.min(100, Math.round((leadsTotal / kpis.organic.clicks) * 100))}%`
                  : "100%",
              },
              {
                label: "3. Terkualifikasi Penjualan (Qualified)",
                val: qualifiedTotal,
                color: "var(--accent)",
                pct: leadsTotal
                  ? `${Math.round((qualifiedTotal / leadsTotal) * 100)}%`
                  : "0%",
              },
              {
                label: "4. Peluang Terbuka (Opportunity)",
                val: opportunitiesTotal,
                color: "var(--warn)",
                pct: qualifiedTotal
                  ? `${Math.round((opportunitiesTotal / qualifiedTotal) * 100)}%`
                  : "0%",
              },
              {
                label: "5. Peluang Menang (Won Deals)",
                val: wonDeals,
                color: "var(--ok)",
                pct: opportunitiesTotal
                  ? `${Math.round((wonDeals / Math.max(1, opportunitiesTotal)) * 100)}%`
                  : "0%",
              },
            ].map((step) => (
              <div
                key={step.label}
                style={{
                  display: "grid",
                  gridTemplateColumns: "240px 1fr 100px",
                  alignItems: "center",
                  gap: 16,
                }}
              >
                <span style={{ fontSize: "0.84rem", fontWeight: 600 }}>
                  {step.label}
                </span>
                <div
                  style={{
                    background: "var(--surface-subtle)",
                    borderRadius: 6,
                    height: 12,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: step.pct,
                      height: "100%",
                      background: step.color,
                      borderRadius: 6,
                    }}
                  />
                </div>
                <div style={{ textAlign: "right" }}>
                  <strong style={{ fontSize: "0.92rem" }}>{step.val}</strong>
                  <span
                    style={{
                      display: "block",
                      fontSize: "0.7rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    {step.pct}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Attribution */}
      {activeTab === "attribution" && (
        <div className="white-panel">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "var(--info)", display: "flex" }}>
              <Icon name="share" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>Evaluasi Atribusi Kanal Pemasaran</h3>
          </div>
          <p className="hint">
            Ringkasan kontribusi kanal berdasarkan asal prospek (source provenance) dan status konversi peluang di database CRM.
          </p>
          <table className="feature-data-table">
            <thead>
              <tr>
                <th>Sumber Akuisisi</th>
                <th>Jumlah Prospek</th>
                <th>Porsi Kanal</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(analytics?.by_source ?? {}).length === 0 ? (
                <tr>
                  <td colSpan={3} className="muted">
                    Belum ada prospek tercatat untuk dihitung atribusinya.
                  </td>
                </tr>
              ) : (
                Object.entries(analytics?.by_source ?? {}).map(([src, count]) => (
                  <tr key={src}>
                    <td style={{ textTransform: "capitalize" }}>
                      <strong>{src.replace("_", " ")}</strong>
                    </td>
                    <td>{count}</td>
                    <td>
                      {leadsTotal > 0 ? `${Math.round((count / leadsTotal) * 100)}%` : "0%"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
