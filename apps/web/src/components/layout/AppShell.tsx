"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useCallback, type ReactNode } from "react";
import { DOCK, NAV_GROUPS, VIEW_IDS, VIEW_META, type DashboardView } from "@/lib/dashboard/dock";
import { powerApi, type PowerState } from "@/lib/powerApi";
import { tasksApi, type Approval, type Task } from "@/lib/tasksApi";
import { authApi } from "@/lib/authApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import { Icon } from "@/components/ui/Icons";

const ROUTE_SECTION: { prefix: string; view: DashboardView }[] = [
  { prefix: "/tasks", view: "operations" },
  { prefix: "/approvals", view: "operations" },
  { prefix: "/projects", view: "operations" },
  { prefix: "/products", view: "campaigns" },
  { prefix: "/marketing/leads", view: "leads" },
  { prefix: "/marketing/campaigns", view: "campaigns" },
  { prefix: "/marketing/content", view: "content" },
  { prefix: "/marketing/seo", view: "seo" },
  { prefix: "/ai", view: "settings" },
  { prefix: "/office", view: "operations" },
];

export function NavIcon({ name }: { name: string }) {
  return <Icon name={name} size={18} strokeWidth={1.85} />;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const router = useRouter();
  const { lang, setLang } = useLanguage();

  // Theme state: Light mode baseline per Addendum v2.4 Section 4.1
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeView, setActiveView] = useState<DashboardView>("overview");

  // Global navbar state
  const [searchQuery, setSearchQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [powerState, setPowerState] = useState<PowerState>("RUNNING");
  const [powerBusy, setPowerBusy] = useState(false);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  }, []);

  // Sync theme & sidebar state from localStorage
  useEffect(() => {
    const id = setTimeout(() => {
      try {
        const savedTheme = localStorage.getItem("roihan_theme");
        if (savedTheme === "dark" || savedTheme === "light") {
          setTheme(savedTheme);
          document.documentElement.setAttribute("data-theme", savedTheme);
        } else {
          document.documentElement.setAttribute("data-theme", "light");
        }
        const savedCollapsed = localStorage.getItem("roihan_sidebar_collapsed");
        if (savedCollapsed === "1") setCollapsed(true);
      } catch {
        document.documentElement.setAttribute("data-theme", "light");
      }
    }, 0);
    return () => clearTimeout(id);
  }, []);

  // Sync current view from URL query or route prefix
  useEffect(() => {
    const id = setTimeout(() => {
      if (pathname === "/") {
        const v = new URLSearchParams(window.location.search).get("view") as DashboardView | null;
        if (v && VIEW_IDS.includes(v)) {
          setActiveView(v);
        } else {
          setActiveView("overview");
        }
      } else {
        const matched = ROUTE_SECTION.find((s) => pathname.startsWith(s.prefix));
        if (matched) setActiveView(matched.view);
      }
    }, 0);
    return () => clearTimeout(id);
  }, [pathname]);

  // Listen to view navigation events from child dashboard components
  useEffect(() => {
    const onViewChanged = (e: Event) => {
      const detail = (e as CustomEvent<DashboardView>).detail;
      if (detail && VIEW_IDS.includes(detail)) {
        setActiveView(detail);
      }
    };
    window.addEventListener("roihan:view-changed", onViewChanged);
    return () => window.removeEventListener("roihan:view-changed", onViewChanged);
  }, []);

  // Load real backend status for Navbar indicators
  const refreshNavbarTelemetry = useCallback(() => {
    powerApi.status().then((p) => setPowerState(p.state), () => undefined);
    tasksApi.approvals().then(setApprovals, () => undefined);
    tasksApi.list().then(setTasks, () => undefined);
  }, []);

  useEffect(() => {
    refreshNavbarTelemetry();
    const timer = setInterval(refreshNavbarTelemetry, 12000);
    return () => clearInterval(timer);
  }, [refreshNavbarTelemetry]);

  const navigateToView = useCallback(
    (view: DashboardView) => {
      setActiveView(view);
      setMobileOpen(false);
      setSearchQuery("");
      setShowNotifications(false);

      const targetUrl = view === "overview" ? "/" : `/?view=${view}`;
      if (pathname === "/") {
        window.history.pushState({}, "", targetUrl);
        window.dispatchEvent(new CustomEvent<DashboardView>("roihan:navigate-view", { detail: view }));
      } else {
        router.push(targetUrl);
      }
    },
    [pathname, router]
  );

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    try {
      localStorage.setItem("roihan_theme", next);
    } catch {
      /* ignore */
    }
    document.documentElement.setAttribute("data-theme", next);
  };

  const toggleSidebarCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem("roihan_sidebar_collapsed", next ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  const togglePower = async () => {
    if (powerBusy) return;
    setPowerBusy(true);
    try {
      if (powerState === "RUNNING") {
        const res = await powerApi.off();
        setPowerState(res.state);
        showToast("Daya AI dijeda — Seluruh antrean tugas disimpan aman.");
      } else {
        const res = await powerApi.on();
        setPowerState(res.state);
        showToast("Daya AI aktif — Pemrosesan tugas pemasaran dilanjutkan.");
      }
    } catch (e) {
      showToast("Gagal mengubah status daya: " + (e as Error).message);
    } finally {
      setPowerBusy(false);
    }
  };

  const pendingApprovals = useMemo(
    () => approvals.filter((a) => a.status === "pending").length,
    [approvals]
  );
  const runningTasks = useMemo(
    () => tasks.filter((t) => t.status === "running").length,
    [tasks]
  );
  const completedTasks = useMemo(
    () => tasks.filter((t) => t.status === "completed").length,
    [tasks]
  );

  const filteredSearch = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    return DOCK.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.subtitle.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  const currentMeta = VIEW_META[activeView] ?? VIEW_META.overview;

  return (
    <div className="app-shell" data-theme={theme}>
      {/* Mobile Drawer Scrim */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* 1. LEFT SIDEBAR (Single Primary Navigation — Section 3.2) */}
      <aside
        className={`app-sidebar ${collapsed ? "collapsed" : ""} ${mobileOpen ? "mobile-open" : ""}`}
        aria-label="Navigasi Utama Roihan AI Office"
      >
        <div className="sidebar-brand-bar">
          <Link
            href="/"
            className="sidebar-brand-link"
            onClick={(e) => {
              e.preventDefault();
              navigateToView("overview");
            }}
            title="Roihan AI Office — Command Center"
          >
            <div className="sidebar-brand-logo" aria-hidden="true">
              <Image
                src="/brand/roihan-app-icon.png"
                alt="Roihan Technologies Logo"
                width={34}
                height={34}
                unoptimized
                priority
                style={{ width: "100%", height: "100%", borderRadius: "inherit", objectFit: "cover" }}
              />
            </div>
            <div className="sidebar-brand-text">
              <span className="sidebar-brand-name">Roihan AI Office</span>
              <span className="sidebar-brand-tag">Marketing Operations</span>
            </div>
          </Link>

          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={toggleSidebarCollapse}
            title={collapsed ? "Perluas Sidebar" : "Ciutkan Sidebar"}
            aria-label={collapsed ? "Perluas Sidebar" : "Ciutkan Sidebar"}
          >
            <Icon name={collapsed ? "chevron-right" : "chevron-left"} size={16} />
          </button>
        </div>

        <nav className="sidebar-nav-scroll" aria-label="Modul Marketing">
          {NAV_GROUPS.map((grp) => {
            const items = DOCK.filter((d) => d.group === grp.key);
            return (
              <div key={grp.key} className="sidebar-group">
                <div className="sidebar-group-label">{grp.label}</div>
                <ul className="sidebar-menu-list">
                  {items.map((item) => {
                    const isActive = activeView === item.view;
                    const showBadge = item.view === "operations" && pendingApprovals > 0;
                    return (
                      <li key={item.view}>
                        <button
                          type="button"
                          className={`sidebar-menu-btn ${isActive ? "active" : ""}`}
                          onClick={() => navigateToView(item.view)}
                          title={`${item.title} — ${item.subtitle}`}
                          aria-current={isActive ? "page" : undefined}
                        >
                          <span className="sidebar-menu-icon">
                            <NavIcon name={item.icon} />
                          </span>
                          <span className="sidebar-menu-label">{item.title}</span>
                          {showBadge && (
                            <span className="sidebar-menu-badge" title={`${pendingApprovals} menunggu persetujuan`}>
                              {pendingApprovals}
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-footer-card" title="Mode Keamanan Pemilik Tunggal Aktif">
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#16a34a" }} />
              Single-Owner Mode
            </span>
            <strong style={{ fontSize: "0.7rem", color: "var(--sidebar-text)" }}>v2.4</strong>
          </div>
        </div>
      </aside>

      {/* 2. MAIN AREA: TOP NAVBAR + MAIN CONTENT (Section 3.3 & 3.4) */}
      <div className="app-main-area">
        <header className="app-navbar" aria-label="Bilah Kontrol Atas">
          <div className="navbar-left">
            <button
              type="button"
              className="navbar-toggle-btn"
              onClick={() => {
                if (typeof window !== "undefined" && window.innerWidth <= 960) {
                  setMobileOpen(!mobileOpen);
                } else {
                  toggleSidebarCollapse();
                }
              }}
              title="Toggle Navigasi Sidebar"
              aria-label="Toggle Navigasi Sidebar"
            >
              <Icon name="sliders" size={17} />
            </button>

            <div className="navbar-breadcrumb">
              <span className="navbar-crumb-group">{currentMeta.groupLabel}</span>
              <span className="navbar-crumb-sep" aria-hidden="true">/</span>
              <span className="navbar-page-title">{currentMeta.title}</span>
            </div>
          </div>

          <div className="navbar-right">
            {/* Global Search */}
            <div className="workspace-search">
              <Icon name="search" size={15} className="workspace-search-icon" />
              <input
                type="search"
                placeholder="Cari modul atau fitur..."
                aria-label="Cari modul atau fitur"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="workspace-search-clear"
                  onClick={() => setSearchQuery("")}
                  aria-label="Bersihkan pencarian"
                >
                  <Icon name="close" size={12} />
                </button>
              )}
              {filteredSearch.length > 0 && (
                <div className="search-results-dropdown" role="listbox">
                  {filteredSearch.map((item) => (
                    <div
                      key={item.view}
                      className="search-result-item"
                      role="option"
                      aria-selected={activeView === item.view}
                      onClick={() => navigateToView(item.view)}
                    >
                      <span className="sidebar-menu-icon">
                        <NavIcon name={item.icon} />
                      </span>
                      <div className="search-result-meta">
                        <span className="search-result-title">{item.title}</span>
                        <span className="search-result-sub">{item.subtitle}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Real AI Task / Power Status Pill */}
            <button
              type="button"
              className="navbar-status-pill"
              onClick={togglePower}
              disabled={powerBusy}
              title={`Daya Kantor AI: ${powerState}. Klik untuk jeda/lanjutkan pemrosesan worker.`}
            >
              <span className={`navbar-status-dot ${powerState === "RUNNING" ? "" : "paused"}`} />
              <span>{powerState === "RUNNING" ? (runningTasks > 0 ? `AI Memproses (${runningTasks})` : "AI Siap") : "AI Dijeda"}</span>
            </button>

            {/* Notifications & Approvals Popover */}
            <div style={{ position: "relative" }}>
              <button
                type="button"
                className="workspace-bell-btn"
                title="Notifikasi & Persetujuan"
                aria-label="Notifikasi & Persetujuan"
                onClick={() => setShowNotifications(!showNotifications)}
              >
                <Icon name="bell" size={16} />
                {pendingApprovals > 0 && <span className="workspace-bell-badge" />}
              </button>

              {showNotifications && (
                <div className="notifications-popover">
                  <h4>
                    <span>Status &amp; Persetujuan</span>
                    {pendingApprovals > 0 && (
                      <span className="notifications-popover-badge">{pendingApprovals} Tertunda</span>
                    )}
                  </h4>
                  <div className="notifications-list">
                    {pendingApprovals > 0 ? (
                      <div className="notification-row">
                        <div>
                          <strong>{pendingApprovals} Tindakan Menunggu Izin</strong>
                          <p>Memerlukan persetujuan pemilik sebelum dieksekusi.</p>
                        </div>
                        <button
                          type="button"
                          className="btn-primary-orange"
                          onClick={() => navigateToView("operations")}
                        >
                          Tinjau
                        </button>
                      </div>
                    ) : (
                      <div className="notification-row">
                        <div>
                          <strong>Tidak Ada Persetujuan Tertunda</strong>
                          <p>Seluruh tindakan eksternal berada dalam batas aman.</p>
                        </div>
                      </div>
                    )}
                    <div className="notification-row">
                      <div>
                        <strong>Antrean Worker AI</strong>
                        <p>{runningTasks} berjalan • {completedTasks} selesai</p>
                      </div>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => navigateToView("operations")}
                      >
                        Log
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Language Switcher (ID / EN) */}
            <button
              type="button"
              className="navbar-icon-btn"
              onClick={() => setLang(lang === "id" ? "en" : "id")}
              title={`Bahasa: ${lang.toUpperCase()} (Klik untuk ganti)`}
              aria-label="Ganti Bahasa"
              style={{ fontSize: "0.72rem", fontWeight: 700 }}
            >
              {lang.toUpperCase()}
            </button>

            {/* Theme Toggle (Light Baseline / Dark Mode) */}
            <button
              type="button"
              className="navbar-icon-btn"
              onClick={toggleTheme}
              title={theme === "light" ? "Aktifkan Dark Mode" : "Aktifkan Light Mode"}
              aria-label={theme === "light" ? "Aktifkan Dark Mode" : "Aktifkan Light Mode"}
            >
              {theme === "light" ? <Icon name="moon" size={16} /> : <Icon name="sun" size={16} />}
            </button>

            {/* Owner Account & Logout */}
            <div className="navbar-user-chip">
              <span className="navbar-user-avatar" style={{ padding: 2, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                <Image
                  src="/brand/roihan-logo-icon.png"
                  alt="Roihan Logo"
                  width={18}
                  height={18}
                  unoptimized
                  style={{ width: 18, height: 18, objectFit: "contain" }}
                />
              </span>
              <span className="navbar-user-name">Owner</span>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await authApi.logout();
                  } catch {
                    // Fallback bila backend tidak dapat dihubungi
                  }
                  window.location.href = "/";
                }}
                title="Keluar Sesi (Logout)"
                aria-label="Keluar Sesi (Logout)"
                style={{
                  border: "none",
                  background: "transparent",
                  padding: "4px 6px",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.25rem",
                  borderRadius: "4px",
                  transition: "background 0.15s, color 0.15s",
                }}
              >
                <Icon name="logout" size={15} />
              </button>
            </div>
          </div>
        </header>

        {/* Main Workspace Content Area */}
        <div className="app-content">
          {children}
        </div>
      </div>

      {toastMessage && (
        <div className="inspired-toast" role="status">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
