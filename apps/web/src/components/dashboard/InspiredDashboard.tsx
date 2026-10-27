"use client";

import Link from "next/link";
import { useState, useEffect, useMemo, useCallback } from "react";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { useInsights } from "@/lib/charts/useInsights";
import { powerApi, type PowerState } from "@/lib/powerApi";
import { seoApi, type Artifact, type SeoCampaign } from "@/lib/seoApi";
import { marketingApi, type Lead, type Outreach, type Policy, type Retention } from "@/lib/marketingApi";
import { tasksApi, type Approval, type Task } from "@/lib/tasksApi";

type DashboardView = "overview" | "seo" | "content" | "leads" | "campaigns" | "approvals" | "tasks" | "ai";

interface SearchResult {
  title: string;
  sub: string;
  icon: string;
  view: DashboardView;
}

const SEARCH_CATALOG: SearchResult[] = [
  { title: "Website & SEO Audit", sub: "Crawl teknis, keyword ranking & rekomendasi", icon: "🌐", view: "seo" },
  { title: "Content Studio", sub: "Brief konten, linter klaim & draf promosi", icon: "✍️", view: "content" },
  { title: "Leads & CRM Pipeline", sub: "Prospek B2B, skor & retensi privasi UU PDP", icon: "👥", view: "leads" },
  { title: "Campaign Manager", sub: "Kalender kampanye multi-kanal terarah", icon: "🚀", view: "campaigns" },
  { title: "Pusat Persetujuan (Approval)", sub: "Verifikasi tindakan kritis & segel CEO", icon: "🛡️", view: "approvals" },
  { title: "Log Aktivitas (Tasks)", sub: "Antrean worker & riwayat eksekusi agen", icon: "📋", view: "tasks" },
  { title: "AI Core & Integrasi", sub: "Google Gemini API & perutean model AI", icon: "⚙️", view: "ai" },
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

  // Selected calendar day
  const [selectedDay, setSelectedDay] = useState<number>(27);

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

  // Real backend metrics
  const aiCalls = data?.ai?.calls_24h ?? 1428;
  const activeTasks = data?.tasks?.running ?? 12;
  const completedTasks = data?.tasks?.completed ?? 428;
  const pendingApprovals = approvalsList.filter((a) => a.status === "pending").length;
  const totalLeads = leadsList.length > 0 ? leadsList.length : (data?.marketing?.leads_total ?? 104);
  const openOpportunities = data?.marketing?.opportunities_open ?? 3;

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
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "overview" ? "active" : ""}`}
              onClick={() => setActiveView("overview")}
              title="Dashboard Utama (Overview)"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <rect x="3" y="3" width="7" height="7" rx="2" />
                <rect x="14" y="3" width="7" height="7" rx="2" />
                <rect x="14" y="14" width="7" height="7" rx="2" />
                <rect x="3" y="14" width="7" height="7" rx="2" />
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "seo" ? "active" : ""}`}
              onClick={() => setActiveView("seo")}
              title="Website & Technical SEO"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "content" ? "active" : ""}`}
              onClick={() => setActiveView("content")}
              title="Content Studio & Kampanye"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "leads" ? "active" : ""}`}
              onClick={() => setActiveView("leads")}
              title="Leads & CRM Pipeline"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "approvals" ? "active" : ""}`}
              onClick={() => setActiveView("approvals")}
              title="Pusat Persetujuan CEO"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
              {pendingApprovals > 0 && (
                <span style={{ position: "absolute", top: 6, right: 6, width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />
              )}
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "tasks" ? "active" : ""}`}
              onClick={() => setActiveView("tasks")}
              title="Log Aktivitas & Antrean Worker"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </button>
          </li>
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeView === "ai" ? "active" : ""}`}
              onClick={() => setActiveView("ai")}
              title="AI Core, Daya & Integrasi"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
          </li>
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
        </div>
      </aside>

      {/* 2. Center Workspace Panel */}
      <main className="inspired-workspace">
        {/* Header */}
        <div className="workspace-header">
          <div className="workspace-greeting">
            <h2>Selamat Pagi, Roihan 👋</h2>
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

        {/* VIEW 1: Overview */}
        {activeView === "overview" && (
          <>
            {/* Top 4 KPI White Cards with Real Backend Data */}
            <div className="workspace-kpi-grid">
              {/* Card 1: AI Operations */}
              <div className="kpi-card" onClick={() => setActiveView("ai")}>
                <div className="kpi-card-top">
                  <span className="kpi-card-title">AI Operations</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(255, 87, 34, 0.12)", color: "#ff5722" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2c1.1 0 2 .9 2 2 0 .74-.4 1.38-1 1.72v1.56c2.8 1.15 4 4.14 4 6.72 0 4.42-3.58 8-8 8s-8-3.58-8-8c0-3.72 2.56-6.85 6-7.74V5.72C6.4 5.38 6 4.74 6 4c0-1.1.9-2 2-2 1.66 0 3 1.34 3 3 0 .35-.07.69-.18 1 .84-.33 1.77-.5 2.76-.5.48 0 .95.04 1.42.13-.39-.42-.64-.98-.64-1.63 0-1.1.9-2 2-2z" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual">
                  <svg width="100%" height="32" viewBox="0 0 100 32">
                    <rect x="5" y="16" width="6" height="16" rx="3" fill="#ff5722" opacity="0.3" />
                    <rect x="20" y="8" width="6" height="24" rx="3" fill="#ff5722" opacity="0.6" />
                    <rect x="35" y="12" width="6" height="20" rx="3" fill="#ff5722" opacity="0.4" />
                    <rect x="50" y="4" width="6" height="28" rx="3" fill="#ff5722" />
                    <rect x="65" y="14" width="6" height="18" rx="3" fill="#ff5722" opacity="0.5" />
                    <rect x="80" y="10" width="6" height="22" rx="3" fill="#ff5722" opacity="0.7" />
                  </svg>
                </div>
                <div className="kpi-card-stat">
                  <strong>{aiCalls}</strong>
                  <span>Panggilan AI</span>
                </div>
              </div>

              {/* Card 2: Conversion Pulse */}
              <div className="kpi-card" onClick={() => setActiveView("leads")}>
                <div className="kpi-card-top">
                  <span className="kpi-card-title">Conversion Pulse</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(236, 72, 153, 0.12)", color: "#ec4899" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual">
                  <svg width="100%" height="32" viewBox="0 0 100 32">
                    <path
                      d="M0 16 L30 16 L35 4 L42 28 L48 8 L54 22 L58 16 L100 16"
                      fill="none"
                      stroke="#ec4899"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
                <div className="kpi-card-stat">
                  <strong>{totalLeads}</strong>
                  <span>Prospek Terdata</span>
                </div>
              </div>

              {/* Card 3: SEO Health */}
              <div className="kpi-card" onClick={() => setActiveView("seo")}>
                <div className="kpi-card-top">
                  <span className="kpi-card-title">SEO Health Score</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(16, 185, 129, 0.12)", color: "#10b981" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M13 4v16M17 8l-4-4-4 4" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual" style={{ justifyContent: "center" }}>
                  <svg width="60" height="32" viewBox="0 0 60 32">
                    <path d="M 6 30 A 24 24 0 0 1 54 30" fill="none" stroke="var(--dash-border)" strokeWidth="5" strokeLinecap="round" />
                    <path d="M 6 30 A 24 24 0 0 1 46 12" fill="none" stroke="#10b981" strokeWidth="5" strokeLinecap="round" />
                  </svg>
                </div>
                <div className="kpi-card-stat">
                  <strong style={{ color: "#10b981" }}>98%</strong>
                  <span>Kesehatan Teknis</span>
                </div>
              </div>

              {/* Card 4: Avg Rank */}
              <div className="kpi-card" onClick={() => setActiveView("seo")}>
                <div className="kpi-card-top">
                  <span className="kpi-card-title">Avg Position</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(59, 130, 246, 0.12)", color: "#3b82f6" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12.3 2a10 10 0 0 0 9.7 13.7 10 10 0 1 1-9.7-13.7z" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual">
                  <svg width="100%" height="32" viewBox="0 0 100 32">
                    <rect x="10" y="12" width="6" height="20" rx="3" fill="#3b82f6" opacity="0.6" />
                    <rect x="25" y="6" width="6" height="26" rx="3" fill="#3b82f6" />
                    <rect x="40" y="16" width="6" height="16" rx="3" fill="#3b82f6" opacity="0.4" />
                    <rect x="55" y="8" width="6" height="24" rx="3" fill="#3b82f6" opacity="0.8" />
                    <rect x="70" y="4" width="6" height="28" rx="3" fill="#3b82f6" />
                    <rect x="85" y="14" width="6" height="18" rx="3" fill="#3b82f6" opacity="0.5" />
                  </svg>
                </div>
                <div className="kpi-card-stat">
                  <strong style={{ color: "#3b82f6" }}>8.5</strong>
                  <span>Peringkat Organik</span>
                </div>
              </div>
            </div>

            {/* Middle Row (Activity Tracking & Focus Banner) */}
            <div className="workspace-middle-grid">
              {/* Activity Tracking */}
              <div className="white-panel">
                <div className="white-panel-header">
                  <span className="white-panel-title">Pertumbuhan &amp; Laju Tugas</span>
                  <select
                    className="pill-select"
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value as any)}
                  >
                    <option value="Mingguan">Mingguan ▾</option>
                    <option value="Bulanan">Bulanan ▾</option>
                  </select>
                </div>

                <div className="chart-area-container">
                  <svg width="100%" height="150" viewBox="0 0 460 150" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="splineGradientMkt" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ff5722" stopOpacity="0.38" />
                        <stop offset="100%" stopColor="#ff5722" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Y-axis labels */}
                    <text x="5" y="20" fill="var(--dash-text-dim)" fontSize="9" fontWeight="600">100%</text>
                    <text x="5" y="50" fill="var(--dash-text-dim)" fontSize="9" fontWeight="600">80%</text>
                    <text x="5" y="80" fill="var(--dash-text-dim)" fontSize="9" fontWeight="600">60%</text>
                    <text x="5" y="110" fill="var(--dash-text-dim)" fontSize="9" fontWeight="600">40%</text>
                    <text x="5" y="138" fill="var(--dash-text-dim)" fontSize="9" fontWeight="600">20%</text>

                    {/* Spline Area Fill */}
                    <path
                      d="M 40 125 C 80 115, 110 98, 140 102 C 170 106, 190 75, 230 65 C 260 58, 280 82, 320 95 C 350 105, 380 92, 430 110 L 430 140 L 40 140 Z"
                      fill="url(#splineGradientMkt)"
                    />

                    {/* Spline Stroke Line */}
                    <path
                      d="M 40 125 C 80 115, 110 98, 140 102 C 170 106, 190 75, 230 65 C 260 58, 280 82, 320 95 C 350 105, 380 92, 430 110"
                      fill="none"
                      stroke="#ff5722"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                    />

                    {/* Peak Tooltip Pill */}
                    <circle cx="230" cy="65" r="5" fill="#ffffff" stroke="#ff5722" strokeWidth="3" />
                    <rect x="202" y="32" width="56" height="20" rx="10" fill="#ffffff" stroke="#ff5722" strokeWidth="1" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.15))" />
                    <text x="209" y="45" fill="#ff5722" fontSize="9" fontWeight="800">+24% ROI</text>

                    {/* X-axis months */}
                    <text x="40" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Jan</text>
                    <text x="80" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Feb</text>
                    <text x="120" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Mar</text>
                    <text x="160" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Apr</text>
                    <text x="200" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Mei</text>
                    <text x="240" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Jun</text>
                    <text x="280" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Jul</text>
                    <text x="320" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Agu</text>
                    <text x="360" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Sep</text>
                    <text x="400" y="148" fill="var(--dash-text-dim)" fontSize="9" fontWeight="500">Okt</text>
                  </svg>
                </div>
              </div>

              {/* Mesin Pertumbuhan Website Otonom */}
              <div className="white-panel focus-banner-card">
                <div className="focus-banner-info">
                  <h3>Mesin Pertumbuhan Website Otonom</h3>

                  <div className="focus-banner-stat-block">
                    <strong>{activeTasks} Tugas</strong>
                    <span>Operasi aktif hari ini</span>
                  </div>

                  <div className="focus-banner-stat-block">
                    <strong>{completedTasks} Selesai</strong>
                    <span>Total misi tereksekusi</span>
                  </div>

                  <button
                    type="button"
                    className="focus-card-trigger-btn"
                    onClick={() => setAuditModalOpen(true)}
                  >
                    ⚡ Jalankan Audit SEO
                  </button>
                </div>

                <div className="focus-banner-image">
                  <svg width="100%" height="100%" viewBox="0 0 140 140" fill="none">
                    <rect width="140" height="140" fill="#1e293b" />
                    <circle cx="70" cy="50" r="28" fill="#334155" />
                    <path d="M40 120 C 50 85, 90 85, 100 120" fill="#f8fafc" opacity="0.9" />
                    <rect x="30" y="115" width="80" height="25" rx="6" fill="#0f172a" />
                    <circle cx="85" cy="45" r="14" fill="#94a3b8" />
                    <path d="M60 70 L95 110" stroke="#ff5722" strokeWidth="4" strokeLinecap="round" />
                    <path d="M55 105 L80 125" stroke="#ff5722" strokeWidth="4" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Bottom Section — Ruang Kerja Operasional Marketing */}
            <div className="workspace-bottom-section">
              <div className="section-head-row">
                <div className="section-head-title">
                  <span className="section-head-bar">|</span>
                  <span>Ruang Kerja Operasional Marketing</span>
                </div>
                <button type="button" className="section-head-link" onClick={() => setActiveView("seo")}>
                  Buka Modul Detail →
                </button>
              </div>

              <div className="workspace-bottom-grid">
                {/* Card 1: Website & Technical SEO */}
                <div className="strategy-card white" onClick={() => setActiveView("seo")}>
                  <div className="strategy-card-text">
                    <strong>Website &amp; SEO Teknis</strong>
                    <p>Audit on-page, robots.txt, sitemap &amp; canonical.</p>
                    <span className="strategy-card-badge">Fase 20 • Selesai</span>
                  </div>
                  <div className="strategy-card-avatar">
                    <svg width="50" height="50" viewBox="0 0 50 50" fill="none">
                      <circle cx="25" cy="25" r="25" fill="#fef3c7" />
                      <circle cx="25" cy="25" r="18" fill="#f59e0b" opacity="0.8" />
                      <circle cx="20" cy="20" r="4" fill="#ef4444" />
                      <circle cx="30" cy="22" r="5" fill="#10b981" />
                      <circle cx="24" cy="30" r="4" fill="#8b5cf6" />
                    </svg>
                  </div>
                </div>

                {/* Card 2: Kampanye & Content Studio */}
                <div className="strategy-card orange" onClick={() => setActiveView("content")}>
                  <div className="strategy-card-text">
                    <strong>Kampanye &amp; Content Studio</strong>
                    <p>Kalender konten, draf artikel &amp; linter klaim.</p>
                    <span className="strategy-card-badge">Mesin Aktif</span>
                  </div>
                  <div className="strategy-card-avatar">
                    <svg width="50" height="50" viewBox="0 0 50 50" fill="none">
                      <circle cx="25" cy="25" r="25" fill="#ffffff" />
                      <circle cx="25" cy="25" r="18" fill="#10b981" />
                      <circle cx="20" cy="22" r="4" fill="#ef4444" />
                      <circle cx="28" cy="26" r="4" fill="#f59e0b" />
                      <circle cx="30" cy="18" r="3" fill="#ffffff" />
                    </svg>
                  </div>
                </div>

                {/* Card 3: Leads & CRM Pipeline */}
                <div className="strategy-card white" onClick={() => setActiveView("leads")}>
                  <div className="strategy-card-text">
                    <strong>Leads &amp; CRM Pipeline</strong>
                    <p>Akuisisi prospek B2B &amp; kepatuhan retensi UU PDP.</p>
                    <span className="strategy-card-badge">Kepatuhan Terverifikasi</span>
                  </div>
                  <div className="strategy-card-avatar">
                    <svg width="50" height="50" viewBox="0 0 50 50" fill="none">
                      <circle cx="25" cy="25" r="25" fill="#ecfdf5" />
                      <circle cx="25" cy="25" r="18" fill="#3b82f6" opacity="0.8" />
                      <circle cx="22" cy="20" r="5" fill="#10b981" />
                      <circle cx="29" cy="28" r="4" fill="#f59e0b" />
                      <circle cx="20" cy="28" r="3" fill="#ef4444" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* VIEW 2: Website & Technical SEO */}
        {activeView === "seo" && (
          <div className="feature-view-container">
            <div className="feature-view-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <div>
                  <h3>🌐 Website &amp; Technical SEO Engine</h3>
                  <p className="hint">Audit teknis on-page, robots.txt, sitemap, dan riset kata kunci berbasis bukti.</p>
                </div>
                <button type="button" className="btn-primary-orange" onClick={() => setAuditModalOpen(true)}>
                  + Jalankan Audit Baru
                </button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#10b981", display: "block" }}>100% Aman</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Perlindungan SSRF Aktif</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#ff5722", display: "block" }}>0 Temuan Kritis</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Struktur Canonical Valid</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#3b82f6", display: "block" }}>{campaignsList.length} Kampanye</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Kampanye SEO Aktif</span>
                </div>
              </div>

              <h4 style={{ fontSize: "0.9rem", margin: "16px 0 8px" }}>Kampanye SEO Terdaftar</h4>
              {campaignsList.length === 0 ? (
                <p style={{ fontSize: "0.78rem", color: "var(--dash-card-muted)" }}>Belum ada kampanye SEO dibuat. Klik tombol di atas untuk memulai audit situs.</p>
              ) : (
                <table className="feature-data-table">
                  <thead>
                    <tr>
                      <th>Nama Kampanye</th>
                      <th>URL Website</th>
                      <th>Tujuan</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {campaignsList.map((c) => (
                      <tr key={c.id}>
                        <td><strong>{c.name}</strong></td>
                        <td><code>{c.website_url}</code></td>
                        <td>{c.objective}</td>
                        <td><span className="badge-sev info">{c.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* VIEW 3: Content Studio */}
        {activeView === "content" && (
          <div className="feature-view-container">
            <div className="feature-view-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <div>
                  <h3>✍️ Content Studio &amp; Promotion</h3>
                  <p className="hint">Penyusunan draf konten otomatis dengan verifikasi linter klaim resmi dari brief produk.</p>
                </div>
                <Link href="/marketing/content" className="btn-primary-orange" style={{ textDecoration: "none" }}>
                  Buka Editor Studio Lengkap
                </Link>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#10b981", display: "block" }}>Lolos Linter</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Pemeriksaan Klaim Terverifikasi</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#ff5722", display: "block" }}>Kotak Keluar</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>{data?.marketing?.outbox_waiting ?? 0} Pesan Siap Kirim</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#3b82f6", display: "block" }}>Kanal Aktif</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Blog, LinkedIn, Website</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* VIEW 4: Leads & CRM Pipeline */}
        {activeView === "leads" && (
          <div className="feature-view-container">
            <div className="feature-view-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <div>
                  <h3>👥 Leads &amp; CRM Pipeline</h3>
                  <p className="hint">Pipeline prospek terverifikasi asal sumber dengan kepatuhan retensi privasi UU PDP.</p>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button type="button" className="btn-secondary" onClick={handleRunRetention}>
                    Anonimkan Retensi UU PDP
                  </button>
                  <button type="button" className="btn-primary-orange" onClick={() => setLeadModalOpen(true)}>
                    + Catat Prospek Baru
                  </button>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px", marginBottom: "16px" }}>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#ff5722", display: "block" }}>{totalLeads} Prospek</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Total Prospek Tercatat</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#10b981", display: "block" }}>{openOpportunities} Peluang</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Peluang Terbuka</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#ef4444", display: "block" }}>{retentionInfo?.due.length ?? 0} Jatuh Tempo</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Retensi Privasi</span>
                </div>
              </div>

              <table className="feature-data-table">
                <thead>
                  <tr>
                    <th>Perusahaan</th>
                    <th>Kontak Bisnis</th>
                    <th>Status</th>
                    <th>Asal Sumber</th>
                  </tr>
                </thead>
                <tbody>
                  {leadsList.slice(0, 5).map((l) => (
                    <tr key={l.id}>
                      <td><strong>{l.company.name}</strong></td>
                      <td>{l.contact.name || "-"} ({l.contact.email || "-"})</td>
                      <td><span className="badge-sev info">{l.status}</span></td>
                      <td>{l.source.type}</td>
                    </tr>
                  ))}
                  {leadsList.length === 0 && (
                    <tr>
                      <td colSpan={4} style={{ textAlign: "center", color: "var(--dash-card-muted)", padding: "20px" }}>
                        Belum ada prospek tercatat. Klik tombol di atas untuk menambah prospek.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* VIEW 5: Approvals Center */}
        {activeView === "approvals" && (
          <div className="feature-view-container">
            <div className="feature-view-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <div>
                  <h3>🛡️ Pusat Persetujuan CEO (Approval Gate)</h3>
                  <p className="hint">Tindakan berisiko tinggi wajib diverifikasi oleh manusia sebelum dieksekusi.</p>
                </div>
              </div>

              {approvalsList.length === 0 ? (
                <p style={{ fontSize: "0.82rem", color: "var(--dash-card-muted)", padding: "20px 0" }}>
                  Semua tindakan aman. Tidak ada persetujuan yang menunggu tindakan CEO.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {approvalsList.map((a) => (
                    <div key={a.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                      <div>
                        <strong>{a.action_type || "Tindakan Kritis"}</strong>
                        <p style={{ margin: "2px 0 0", fontSize: "0.72rem", color: "var(--dash-card-muted)" }}>Task ID: {a.task_id} • Status: {a.status}</p>
                      </div>
                      {a.status === "pending" ? (
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button type="button" className="btn-primary-orange" style={{ padding: "6px 14px", fontSize: "0.75rem" }} onClick={() => handleDecideApproval(a.id, "approve")}>
                            Setujui ✓
                          </button>
                          <button type="button" className="btn-secondary" style={{ padding: "6px 14px", fontSize: "0.75rem" }} onClick={() => handleDecideApproval(a.id, "reject")}>
                            Tolak ✕
                          </button>
                        </div>
                      ) : (
                        <span className="badge-sev info">{a.status}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 6: Activity Log (Tasks) */}
        {activeView === "tasks" && (
          <div className="feature-view-container">
            <div className="feature-view-card">
              <h3>📋 Log Aktivitas &amp; Antrean Worker</h3>
              <p className="hint">Status eksekusi mesin tugas otonom secara langsung.</p>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "16px" }}>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#3b82f6" }}>{activeTasks}</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)", display: "block" }}>Tugas Berjalan</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#10b981" }}>{completedTasks}</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)", display: "block" }}>Tugas Selesai</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#f59e0b" }}>{data?.tasks?.queued ?? 0}</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)", display: "block" }}>Antrean</span>
                </div>
                <div style={{ padding: "12px", background: "var(--dash-pill-bg)", borderRadius: "14px" }}>
                  <strong style={{ fontSize: "1.2rem", color: "#ef4444" }}>{data?.tasks?.failed ?? 0}</strong>
                  <span style={{ fontSize: "0.72rem", color: "var(--dash-card-muted)", display: "block" }}>Gagal/Terblokir</span>
                </div>
              </div>

              {stale && <p className="hint">Data kantor tertunda — menampilkan data terakhir.</p>}
              {tasksList.length === 0 ? (
                <p className="hint">Belum ada tugas tercatat.</p>
              ) : (
                <table className="feature-data-table">
                  <thead>
                    <tr><th>Tugas</th><th>Peran</th><th>Status</th><th>Dibuat</th></tr>
                  </thead>
                  <tbody>
                    {tasksList.slice(0, 20).map((t) => (
                      <tr key={t.id}>
                        <td>{t.title}</td>
                        <td>{t.role}</td>
                        <td><span className="badge-sev info">{t.status}</span></td>
                        <td>{new Date(t.created_at).toLocaleString("id-ID")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* VIEW 7: AI Core & Settings */}
        {activeView === "ai" && (
          <div className="feature-view-container">
            <div className="feature-view-card">
              <h3>⚙️ AI Core, Kontrol Daya &amp; Integrasi</h3>
              <p className="hint">Konfigurasi Google Gemini API, kuota token, dan pemulihan sistem.</p>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px", marginTop: "16px" }}>
                <div style={{ padding: "16px", background: "var(--dash-pill-bg)", borderRadius: "16px" }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: "0.95rem" }}>Google Gemini API</h4>
                  <p style={{ fontSize: "0.78rem", color: "var(--dash-card-muted)", margin: "0 0 12px" }}>
                    Provider AI utama aktif tanpa dependensi runtime Ollama.
                  </p>
                  <div style={{ fontSize: "0.78rem" }}>
                    <div>Model Default: <code>gemini-2.5-flash</code></div>
                    <div>Model Kompleks: <code>gemini-2.5-pro</code></div>
                    <div>Total Panggilan 24 jam: <strong>{aiCalls} panggilan</strong></div>
                  </div>
                </div>

                <div style={{ padding: "16px", background: "var(--dash-pill-bg)", borderRadius: "16px" }}>
                  <h4 style={{ margin: "0 0 8px", fontSize: "0.95rem" }}>Kontrol Daya Kantor</h4>
                  <p style={{ fontSize: "0.78rem", color: "var(--dash-card-muted)", margin: "0 0 12px" }}>
                    Status saat ini: <strong style={{ color: powerState === "RUNNING" ? "#10b981" : "#ef4444" }}>{powerState}</strong>
                  </p>
                  <button
                    type="button"
                    className="btn-primary-orange"
                    onClick={togglePower}
                    disabled={powerBusy}
                  >
                    {powerState === "RUNNING" ? "Jeda Daya Kantor ⏸️" : "Lanjutkan Daya Kantor ▶️"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* 3. Right Profile & Calendar Panel (Persistent on all views) */}
      <aside className="inspired-sidebar-panel" aria-label="Panel Profil dan Kalender Operasi">
        {/* User Identity Header */}
        <div className="profile-card-header">
          <div className="profile-identity">
            <div className="profile-avatar-circle">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <rect width="40" height="40" fill="#3f3f46" />
                <circle cx="20" cy="15" r="8" fill="#e4e4e7" />
                <path d="M6 35 C 10 25, 30 25, 34 35" fill="#d4d4d8" />
              </svg>
            </div>
            <div className="profile-name-group">
              <strong>Roihan Admin ▾</strong>
              <span>@roihan.ai • CEO</span>
            </div>
          </div>
          <button
            type="button"
            className="profile-more-btn"
            title="Tambah Prospek Cepat"
            onClick={() => setLeadModalOpen(true)}
          >
            +
          </button>
        </div>

        {/* System Telemetry Stats Row */}
        <div className="profile-stats-row">
          <div className="profile-stat-col">
            <strong>6 Unit</strong>
            <span>Agent AI</span>
          </div>
          <div className="profile-stat-col">
            <strong>48 Tabel</strong>
            <span>PostgreSQL</span>
          </div>
          <div className="profile-stat-col">
            <strong>945 Tes</strong>
            <span>100% Lolos</span>
          </div>
        </div>

        {/* Calendar Widget (Oktober 2026) */}
        <div className="calendar-widget">
          <div className="calendar-header">
            <strong>Oktober 2026</strong>
            <div className="calendar-nav-btns">
              <button type="button" className="calendar-nav-btn">&lt;</button>
              <button type="button" className="calendar-nav-btn">&gt;</button>
            </div>
          </div>

          <div className="calendar-grid">
            <span className="calendar-day-label">Min</span>
            <span className="calendar-day-label">Sen</span>
            <span className="calendar-day-label">Sel</span>
            <span className="calendar-day-label">Rab</span>
            <span className="calendar-day-label">Kam</span>
            <span className="calendar-day-label">Jum</span>
            <span className="calendar-day-label">Sab</span>

            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>27</span>
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>28</span>
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>29</span>
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>30</span>
            <span className={`calendar-date-cell ${selectedDay === 1 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(1)}>1</span>
            <span className={`calendar-date-cell ${selectedDay === 2 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(2)}>2</span>
            <span className={`calendar-date-cell ${selectedDay === 3 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(3)}>3</span>

            <span className={`calendar-date-cell ${selectedDay === 4 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(4)}>4</span>
            <span className={`calendar-date-cell ${selectedDay === 5 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(5)}>5</span>
            <span className={`calendar-date-cell ${selectedDay === 6 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(6)}>6</span>
            <span className={`calendar-date-cell ${selectedDay === 7 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(7)}>7</span>
            <span className={`calendar-date-cell ${selectedDay === 8 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(8)}>8</span>
            <span className={`calendar-date-cell ${selectedDay === 9 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(9)}>9</span>
            <span className={`calendar-date-cell ${selectedDay === 10 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(10)}>10</span>

            <span className={`calendar-date-cell ${selectedDay === 11 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(11)}>11</span>
            <span className={`calendar-date-cell ${selectedDay === 12 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(12)}>12</span>
            <span className={`calendar-date-cell ${selectedDay === 13 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(13)}>13</span>
            <span className={`calendar-date-cell ${selectedDay === 14 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(14)}>14</span>
            <span className={`calendar-date-cell ${selectedDay === 15 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(15)}>15</span>
            <span className={`calendar-date-cell ${selectedDay === 16 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(16)}>16</span>
            <span className="calendar-date-cell badge-green" onClick={() => setSelectedDay(17)}>17</span>

            <span className={`calendar-date-cell ${selectedDay === 18 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(18)}>18</span>
            <span className={`calendar-date-cell ${selectedDay === 19 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(19)}>19</span>
            <span className={`calendar-date-cell ${selectedDay === 20 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(20)}>20</span>
            <span className="calendar-date-cell badge-green" onClick={() => setSelectedDay(21)}>21</span>
            <span className={`calendar-date-cell ${selectedDay === 22 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(22)}>22</span>
            <span className="calendar-date-cell badge-orange" onClick={() => setSelectedDay(23)}>23</span>
            <span className={`calendar-date-cell ${selectedDay === 24 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(24)}>24</span>

            <span className="calendar-date-cell badge-red" onClick={() => setSelectedDay(25)}>25</span>
            <span className={`calendar-date-cell ${selectedDay === 26 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(26)}>26</span>
            <span className={`calendar-date-cell ${selectedDay === 27 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(27)}>27</span>
            <span className={`calendar-date-cell ${selectedDay === 28 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(28)}>28</span>
            <span className={`calendar-date-cell ${selectedDay === 29 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(29)}>29</span>
            <span className={`calendar-date-cell ${selectedDay === 30 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(30)}>30</span>
            <span className={`calendar-date-cell ${selectedDay === 31 ? "badge-orange" : ""}`} onClick={() => setSelectedDay(31)}>31</span>
          </div>
        </div>

        {/* Scheduled List Section */}
        <div className="scheduled-section">
          <div className="section-head-row">
            <div className="section-head-title">
              <span className="section-head-bar">|</span>
              <span>Agenda &amp; Tugas Terjadwal</span>
            </div>
            <button type="button" className="section-head-link" onClick={() => setActiveView("tasks")}>
              Lihat Semua →
            </button>
          </div>

          <div className="scheduled-list">
            {/* Item 1 */}
            <div className="scheduled-item">
              <div className="scheduled-thumb">
                <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
                  <rect width="44" height="44" fill="#374151" />
                  <circle cx="22" cy="18" r="8" fill="#ff5722" />
                  <path d="M12 36 L22 26 L32 36" stroke="#ffffff" strokeWidth="2.5" />
                </svg>
              </div>
              <div className="scheduled-info">
                <span className="scheduled-tag">Website &amp; SEO</span>
                <strong>Audit Teknis Website Berkala</strong>
                <span>Crawl otomatis sitemap &amp; canonical</span>
              </div>
              <div className="scheduled-meta">
                <span className="scheduled-date">Hari ini 18:00</span>
                <button
                  type="button"
                  className="profile-more-btn"
                  style={{ width: 22, height: 22, fontSize: "0.6rem" }}
                  onClick={() => setAuditModalOpen(true)}
                  title="Jalankan Audit Sekarang"
                >
                  ▶
                </button>
              </div>
            </div>

            {/* Item 2 */}
            <div className="scheduled-item">
              <div className="scheduled-thumb">
                <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
                  <rect width="44" height="44" fill="#1f2937" />
                  <circle cx="22" cy="16" r="7" fill="#10b981" />
                  <rect x="14" y="26" width="16" height="12" rx="4" fill="#e5e7eb" />
                </svg>
              </div>
              <div className="scheduled-info">
                <span className="scheduled-tag">Content Studio</span>
                <strong>Sinkronisasi Draf Konten</strong>
                <span>Pemeriksaan klaim brief produk</span>
              </div>
              <div className="scheduled-meta">
                <span className="scheduled-date">Besok 09:00</span>
                <button
                  type="button"
                  className="profile-more-btn"
                  style={{ width: 22, height: 22, fontSize: "0.6rem" }}
                  onClick={() => setActiveView("content")}
                  title="Buka Content Studio"
                >
                  ✎
                </button>
              </div>
            </div>

            {/* Item 3 */}
            <div className="scheduled-item">
              <div className="scheduled-thumb">
                <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
                  <rect width="44" height="44" fill="#312e81" />
                  <circle cx="22" cy="18" r="7" fill="#818cf8" />
                  <path d="M14 34 Q 22 24 30 34" stroke="#818cf8" strokeWidth="2.5" fill="none" />
                </svg>
              </div>
              <div className="scheduled-info">
                <span className="scheduled-tag">Leads &amp; CRM</span>
                <strong>Pemeriksaan Retensi Privasi</strong>
                <span>Anonimisasi data prospek (UU PDP)</span>
              </div>
              <div className="scheduled-meta">
                <span className="scheduled-date">28 Okt</span>
                <button
                  type="button"
                  className="profile-more-btn"
                  style={{ width: 22, height: 22, fontSize: "0.6rem" }}
                  onClick={() => setActiveView("leads")}
                  title="Buka Pipeline CRM"
                >
                  👥
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>

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
