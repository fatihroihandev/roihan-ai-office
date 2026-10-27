"use client";

import Link from "next/link";
import { useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { useInsights } from "@/lib/charts/useInsights";
import { powerApi, type PowerState } from "@/lib/powerApi";
import { seoApi, type Artifact, type SeoCampaign } from "@/lib/seoApi";
import { marketingApi, type Lead, type Outreach, type Policy, type Retention } from "@/lib/marketingApi";
import { tasksApi, type Approval, type Task } from "@/lib/tasksApi";
import { authApi } from "@/lib/authApi";

import { SeoFeature } from "@/components/features/SeoFeature";
import { ContentFeature } from "@/components/features/ContentFeature";
import { LeadsFeature } from "@/components/features/LeadsFeature";
import { CampaignsFeature } from "@/components/features/CampaignsFeature";
import { ProjectsFeature } from "@/components/features/ProjectsFeature";
import { ProductsFeature } from "@/components/features/ProductsFeature";
import { ApprovalsFeature } from "@/components/features/ApprovalsFeature";
import { TasksFeature } from "@/components/features/TasksFeature";
import { OfficeFeature } from "@/components/features/OfficeFeature";
import { AiFeature } from "@/components/features/AiFeature";
import { SocialFeature } from "@/components/features/SocialFeature";
import { EmailFeature } from "@/components/features/EmailFeature";
import { AnalyticsFeature } from "@/components/features/AnalyticsFeature";
import { OperationsFeature } from "@/components/features/OperationsFeature";
import { SettingsFeature } from "@/components/features/SettingsFeature";

import { MarketingOverview } from "./MarketingOverview";
import { MarketingSidePanel } from "./MarketingSidePanel";
import type { Kpis } from "@/lib/seoApi";
import { DOCK, VIEW_IDS, type DashboardView } from "@/lib/dashboard/dock";

interface SearchResult {
  title: string;
  sub: string;
  icon: string;
  view: DashboardView;
}

const SEARCH_CATALOG: SearchResult[] = [
  { title: "Command Center (Overview)", sub: "Ringkasan performa marketing, KPI & tugas agen", icon: "⊞", view: "overview" },
  { title: "Website & Growth (SEO)", sub: "Crawl teknis, keyword ranking & optimasi on-page", icon: "🌐", view: "seo" },
  { title: "Content Studio", sub: "Brief konten, linter klaim & draf artikel/sosial", icon: "✍️", view: "content" },
  { title: "Social Media Hub", sub: "Jadwal posting, multi-akun terhubung & analitik sosial", icon: "📱", view: "social" },
  { title: "Campaigns & Advertising", sub: "Perencanaan kampanye, anggaran & eksperimen", icon: "🚀", view: "campaigns" },
  { title: "Leads & CRM Pipeline", sub: "Prospek B2B, skor & retensi privasi UU PDP", icon: "👥", view: "leads" },
  { title: "Email & Automation", sub: "Kampanye email, audiens & trigger alur kerja", icon: "✉️", view: "email" },
  { title: "Analytics & Intelligence", sub: "Corong konversi, atribusi kanal & ekspor CSV", icon: "📊", view: "analytics" },
  { title: "Pusat Operasi & Persetujuan", sub: "Verifikasi tindakan kritis & log aktivitas", icon: "🛡️", view: "operations" },
  { title: "Pengaturan & AI Core", sub: "Google Gemini API, batas token & peran spesialis", icon: "⚙️", view: "settings" },
];

export function InspiredDashboard() {
  const { data, stale, connected } = useOfficeData();
  const ins = useInsights(data?.generated_at ?? null);

  // Active View inside the single dashboard
  const [activeView, setActiveView] = useState<DashboardView>("overview");
  const [timeframe, setTimeframe] = useState<"Mingguan" | "Bulanan">("Mingguan");
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);

  // Theme Mode (Dark / Light)
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  // Office Power state
  const [powerState, setPowerState] = useState<PowerState>("RUNNING");
  const [powerBusy, setPowerBusy] = useState(false);

  // Modals state
  const [auditModalOpen, setAuditModalOpen] = useState(false);
  const [leadModalOpen, setLeadModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Form states for Quick Audit
  const [auditUrl, setAuditUrl] = useState("https://roihan.id");
  const [auditHtml, setAuditHtml] = useState("<html><head><title>Roihan AI Office</title></head><body><h1>Autonomous Marketing</h1></body></html>");
  const [auditBusy, setAuditBusy] = useState(false);

  // Form states for Quick Lead
  const [leadCompany, setLeadCompany] = useState("");
  const [leadContact, setLeadContact] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadBusy, setLeadBusy] = useState(false);

  // Feature specific data
  const [approvalsList, setApprovalsList] = useState<Approval[]>([]);
  const [leadsList, setLeadsList] = useState<Lead[]>([]);
  const [campaignsList, setCampaignsList] = useState<SeoCampaign[]>([]);
  const [retentionInfo, setRetentionInfo] = useState<Retention | null>(null);
  const [tasksList, setTasksList] = useState<Task[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);

  // Selected calendar day
  const [selectedDay, setSelectedDay] = useState<number>(27);

  // Buka tampilan dari ?view= (menggantikan route lama yang kini redirect ke sini)
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get("view") as DashboardView | null;
    if (v && VIEW_IDS.includes(v)) setActiveView(v);
  }, []);

  // Load theme preference on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem("roihan_theme") as "dark" | "light" | null;
    if (savedTheme) {
      setTheme(savedTheme);
      document.documentElement.setAttribute("data-theme", savedTheme);
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("roihan_theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Sync initial power and approvals status
  useEffect(() => {
    powerApi.status().then((p) => setPowerState(p.state), () => undefined);
    tasksApi.approvals().then(setApprovalsList, () => undefined);
    marketingApi.leads().then(setLeadsList, () => undefined);
    seoApi.campaigns().then(setCampaignsList, () => undefined);
    marketingApi.retention().then(setRetentionInfo, () => undefined);
    tasksApi.list().then(setTasksList, () => undefined);
    seoApi.kpis().then(setKpis, () => undefined);
  }, []);

  const togglePower = async () => {
    if (powerBusy) return;
    setPowerBusy(true);
    try {
      if (powerState === "RUNNING") {
        const res = await powerApi.off();
        setPowerState(res.state);
        showToast("Daya Kantor Dijeda — Seluruh tugas tersimpan dalam checkpoint aman.");
      } else {
        const res = await powerApi.on();
        setPowerState(res.state);
        showToast("Daya Kantor Aktif — Pemrosesan tugas AI dilanjutkan.");
      }
    } catch (e) {
      showToast("Gagal mengubah daya: " + (e as Error).message);
    } finally {
      setPowerBusy(false);
    }
  };

  const handleRunAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuditBusy(true);
    try {
      await seoApi.audit({ url: auditUrl, html: auditHtml });
      setAuditModalOpen(false);
      showToast("Audit SEO Teknis berhasil diantrekan ke antrean worker!");
    } catch (e) {
      showToast("Gagal memulai audit: " + (e as Error).message);
    } finally {
      setAuditBusy(false);
    }
  };

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadCompany.trim()) return;
    setLeadBusy(true);
    try {
      await marketingApi.createLead({
        company: { name: leadCompany, industry: "Technology", size_band: "medium" },
        contact: { name: leadContact || undefined, title: "Director", email: leadEmail || undefined, phone: undefined },
        source: { source_type: "manual", url: undefined },
      });
      setLeadModalOpen(false);
      setLeadCompany("");
      setLeadContact("");
      setLeadEmail("");
      marketingApi.leads().then(setLeadsList, () => undefined);
      showToast("Prospek baru berhasil dicatat ke dalam CRM!");
    } catch (e) {
      showToast("Gagal mencatat prospek: " + (e as Error).message);
    } finally {
      setLeadBusy(false);
    }
  };

  const handleDecideApproval = async (id: string, action: "approve" | "reject") => {
    try {
      if (action === "approve") {
        await tasksApi.approve(id, "Disetujui oleh CEO dari Dashboard");
        showToast("Approval disetujui — Tindakan diizinkan untuk dieksekusi.");
      } else {
        await tasksApi.reject(id, "Ditolak oleh CEO");
        showToast("Approval ditolak.");
      }
      tasksApi.approvals().then(setApprovalsList, () => undefined);
    } catch (e) {
      showToast("Operasi approval gagal: " + (e as Error).message);
    }
  };

  const handleRunRetention = async () => {
    try {
      await marketingApi.runRetention();
      showToast("Retensi Privasi UU PDP dijalankan: data kedaluwarsa telah dianonimkan.");
      marketingApi.retention().then(setRetentionInfo, () => undefined);
      marketingApi.leads().then(setLeadsList, () => undefined);
    } catch (e) {
      showToast("Gagal menjalankan retensi: " + (e as Error).message);
    }
  };

  // Instant catalog search
  const filteredSearch = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return SEARCH_CATALOG.filter((item) =>
      item.title.toLowerCase().includes(q) || item.sub.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  const hour = new Date().getHours();
  const greeting = hour < 11 ? "Selamat Pagi" : hour < 15 ? "Selamat Siang" : hour < 18 ? "Selamat Sore" : "Selamat Malam";

  // Real backend metrics
  const aiCalls = data?.ai?.calls_24h ?? 0;
  const activeTasks = data?.tasks?.running ?? 0;
  const completedTasks = data?.tasks?.completed ?? 0;
  const pendingApprovals = approvalsList.filter((a) => a.status === "pending").length;
  const totalLeads = leadsList.length > 0 ? leadsList.length : (data?.marketing?.leads_total ?? 0);
  const openOpportunities = data?.marketing?.opportunities_open ?? 0;

  return (
    <div className={`inspired-dashboard-container ${theme === "light" ? "light-theme" : ""}`} data-theme={theme}>
      {/* 1. Left Slim Dock Sidebar */}
      <aside className="inspired-dock" aria-label="Dock Navigasi Marketing">
        <div
          className="inspired-dock-logo"
          title="Roihan AI Office"
          onClick={() => setActiveView("overview")}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 5v14M18 5v14M2 9h4M18 9h4M2 15h4M18 15h4M6 12h12" />
          </svg>
        </div>

        <ul className="inspired-dock-nav">
          {DOCK.map((d) => (
            <li key={d.view}>
              <button type="button" className={`inspired-dock-btn ${activeView === d.view ? "active" : ""}`} onClick={() => setActiveView(d.view)} title={d.title} aria-label={d.title}>
                <span aria-hidden="true" style={{ fontSize: "1.1rem" }}>{d.icon}</span>
                {d.view === "approvals" && pendingApprovals > 0 && (<span style={{ position: "absolute", top: 6, right: 6, width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />)}
              </button>
            </li>
          ))}
        </ul>

        {/* Dock Footer: Power Status & Dark/Light Mode Switch */}
        <div className="inspired-dock-footer">
          <button
            type="button"
            className="inspired-dock-toggle"
            title={`Status Daya Kantor: ${powerState} (Klik untuk jeda/lanjutkan)`}
            onClick={togglePower}
            disabled={powerBusy}
          >
            <div
              className="inspired-dock-dot"
              style={{
                background: powerState === "RUNNING" ? "#ff5722" : "#71717a",
                boxShadow: powerState === "RUNNING" ? "0 0 10px #ff5722" : "none",
              }}
            />
          </button>
          <button
            type="button"
            className="inspired-dock-btn"
            title={theme === "dark" ? "Ganti ke Light Mode ☀️" : "Ganti ke Dark Mode 🌙"}
            onClick={toggleTheme}
          >
            {theme === "dark" ? (
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            ) : (
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>
          <button
            type="button"
            className="inspired-dock-btn"
            title="Keluar Sesi Pemilik (Logout)"
            onClick={async () => {
              if (window.confirm("Apakah Anda yakin ingin keluar dari sesi pemilik?")) {
                await authApi.logout();
                window.location.reload();
              }
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
          </button>
        </div>
      </aside>

      {/* 2. Center Workspace Panel */}
      <main className="inspired-workspace">
        {/* Header */}
        <div className="workspace-header">
          <div className="workspace-greeting">
            <h2>{greeting}, Roihan 👋</h2>
            <p>Pusat Operasi Marketing &amp; Pertumbuhan Website Otonom</p>
          </div>

          <div className="workspace-header-actions">
            {/* Real Search Bar */}
            <div className="workspace-search">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                placeholder="Cari modul, tugas, atau kampanye..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {filteredSearch.length > 0 && (
                <div className="search-results-dropdown">
                  {filteredSearch.map((item) => (
                    <div
                      key={item.title}
                      className="search-result-item"
                      onClick={() => {
                        setActiveView(item.view);
                        setSearchQuery("");
                      }}
                    >
                      <span className="search-result-icon">{item.icon}</span>
                      <div className="search-result-meta">
                        <span className="search-result-title">{item.title}</span>
                        <span className="search-result-sub">{item.sub}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Notification Bell with Dropdown */}
            <div style={{ position: "relative" }}>
              <button
                type="button"
                className="workspace-bell-btn"
                title="Notifikasi & Tindakan Tertunda"
                onClick={() => setShowNotifications(!showNotifications)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {pendingApprovals > 0 && <span className="workspace-bell-badge" />}
              </button>

              {showNotifications && (
                <div className="notifications-popover">
                  <h4>
                    <span>Pusat Notifikasi</span>
                    {pendingApprovals > 0 && (
                      <span className="notifications-popover-badge">{pendingApprovals} Tertunda</span>
                    )}
                  </h4>
                  <div className="notifications-list">
                    {pendingApprovals > 0 ? (
                      <div className="notification-row">
                        <div>
                          <strong>{pendingApprovals} Approval Menunggu</strong>
                          <p>Tindakan outbound memerlukan segel CEO.</p>
                        </div>
                        <button
                          type="button"
                          className="btn-primary-orange"
                          style={{ padding: "4px 10px", fontSize: "0.7rem" }}
                          onClick={() => {
                            setActiveView("approvals");
                            setShowNotifications(false);
                          }}
                        >
                          Tinjau
                        </button>
                      </div>
                    ) : (
                      <p style={{ fontSize: "0.75rem", color: "var(--dash-text-muted)", margin: 0 }}>Semua tindakan berizin aman. Tidak ada approval tertunda.</p>
                    )}
                    <div className="notification-row">
                      <div>
                        <strong>Antrean Worker</strong>
                        <p>{activeTasks} tugas berjalan • {completedTasks} selesai.</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Overview marketing: seluruh angka dari backend */}
        {activeView === "overview" && (<MarketingOverview data={data} kpis={kpis} campaigns={campaignsList} pendingApprovals={pendingApprovals} onNavigate={setActiveView} onAudit={() => setAuditModalOpen(true)} onLead={() => setLeadModalOpen(true)} />)}

        {/* Fitur terintegrasi: semua modul dijalankan langsung di dashboard tunggal */}
        {/* 10 Modul Kanonis Master Addendum v2.0 */}
        {activeView === "seo" && (<div className="feature-view-container"><SeoFeature /></div>)}
        {activeView === "content" && (<div className="feature-view-container"><ContentFeature /></div>)}
        {activeView === "social" && (<div className="feature-view-container"><SocialFeature /></div>)}
        {activeView === "campaigns" && (<div className="feature-view-container"><CampaignsFeature /></div>)}
        {activeView === "leads" && (<div className="feature-view-container"><LeadsFeature /></div>)}
        {activeView === "email" && (<div className="feature-view-container"><EmailFeature /></div>)}
        {activeView === "analytics" && (<div className="feature-view-container"><AnalyticsFeature /></div>)}
        {activeView === "operations" && (<div className="feature-view-container"><OperationsFeature /></div>)}
        {activeView === "settings" && (<div className="feature-view-container"><SettingsFeature /></div>)}

        {/* Tampilan Pendukung & Detail */}
        {activeView === "projects" && (<div className="feature-view-container"><ProjectsFeature /></div>)}
        {activeView === "products" && (<div className="feature-view-container"><ProductsFeature /></div>)}
        {activeView === "approvals" && (<div className="feature-view-container"><ApprovalsFeature /></div>)}
        {activeView === "tasks" && (<div className="feature-view-container"><TasksFeature /></div>)}
        {activeView === "office" && (<div className="feature-view-container"><Suspense fallback={null}><OfficeFeature /></Suspense></div>)}
        {activeView === "ai" && (<div className="feature-view-container"><AiFeature /></div>)}
      </main>

      <MarketingSidePanel data={data} campaigns={campaignsList} onNavigate={setActiveView} onLead={() => setLeadModalOpen(true)} />

      {/* Quick Audit Modal */}
      {auditModalOpen && (
        <div className="inspired-modal-backdrop" onClick={() => setAuditModalOpen(false)}>
          <div className="inspired-modal" onClick={(e) => e.stopPropagation()}>
            <div className="inspired-modal-header">
              <h3>⚡ Jalankan Audit SEO Teknis</h3>
              <button type="button" className="inspired-modal-close" onClick={() => setAuditModalOpen(false)}>✕</button>
            </div>
            <form onSubmit={handleRunAudit}>
              <div className="inspired-form-group">
                <label>URL Website Target (Perlindungan SSRF aktif)</label>
                <input
                  type="url"
                  className="inspired-form-input"
                  value={auditUrl}
                  onChange={(e) => setAuditUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                />
              </div>
              <div className="inspired-form-group">
                <label>Snapshot Konten HTML</label>
                <textarea
                  rows={4}
                  className="inspired-form-textarea"
                  value={auditHtml}
                  onChange={(e) => setAuditHtml(e.target.value)}
                  required
                />
              </div>
              <div className="inspired-modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setAuditModalOpen(false)}>
                  Batal
                </button>
                <button type="submit" className="btn-primary-orange" disabled={auditBusy}>
                  {auditBusy ? "Sedang Crawl..." : "Jalankan Audit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Quick Lead Modal */}
      {leadModalOpen && (
        <div className="inspired-modal-backdrop" onClick={() => setLeadModalOpen(false)}>
          <div className="inspired-modal" onClick={(e) => e.stopPropagation()}>
            <div className="inspired-modal-header">
              <h3>👥 Catat Prospek B2B Baru</h3>
              <button type="button" className="inspired-modal-close" onClick={() => setLeadModalOpen(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateLead}>
              <div className="inspired-form-group">
                <label>Nama Perusahaan</label>
                <input
                  type="text"
                  className="inspired-form-input"
                  value={leadCompany}
                  onChange={(e) => setLeadCompany(e.target.value)}
                  placeholder="PT Sinar Gemilang"
                  required
                />
              </div>
              <div className="inspired-form-group">
                <label>Nama Kontak Bisnis (Opsional)</label>
                <input
                  type="text"
                  className="inspired-form-input"
                  value={leadContact}
                  onChange={(e) => setLeadContact(e.target.value)}
                  placeholder="Budi Setiawan"
                />
              </div>
              <div className="inspired-form-group">
                <label>Email Kontak Kantor (Opsional)</label>
                <input
                  type="email"
                  className="inspired-form-input"
                  value={leadEmail}
                  onChange={(e) => setLeadEmail(e.target.value)}
                  placeholder="budi@example.com"
                />
              </div>
              <div className="inspired-modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setLeadModalOpen(false)}>
                  Batal
                </button>
                <button type="submit" className="btn-primary-orange" disabled={leadBusy || !leadCompany.trim()}>
                  {leadBusy ? "Menyimpan..." : "Simpan Prospek ke CRM"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className="inspired-toast">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
