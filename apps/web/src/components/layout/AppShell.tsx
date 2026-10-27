"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useLanguage } from "@/i18n/LanguageProvider";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { BRAND } from "@/lib/brand";

interface NavItem {
  href: string;
  key: string;
  icon: string;
  badge?: string;
}

const SIDEBAR_ITEMS: NavItem[] = [
  { href: "/", key: "nav.overview", icon: "📊" },
  { href: "/marketing/seo", key: "nav.websiteSeo", icon: "🌐" },
  { href: "/marketing/content", key: "nav.contentStudio", icon: "✍️" },
  { href: "/marketing#leads", key: "nav.leadsCrm", icon: "👥" },
  { href: "/marketing#campaigns", key: "nav.campaigns", icon: "🚀" },
  { href: "/marketing#analytics", key: "nav.analytics", icon: "📈" },
  { href: "/approvals", key: "nav.approvals", icon: "🛡️" },
  { href: "/tasks", key: "nav.activityLog", icon: "📋" },
  { href: "/ai#integrations", key: "nav.integrations", icon: "🔌" },
  { href: "/ai", key: "nav.settings", icon: "⚙️" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useLanguage();
  const pathname = usePathname() ?? "/";
  const [mobileOpen, setMobileOpen] = useState(false);

  const isOffice = pathname === "/office";
  const isDashboard = pathname === "/";

  if (isDashboard) {
    return <div className="app-shell dashboard-mode">{children}</div>;
  }

  // Fungsi penentu halaman aktif
  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    const baseHref = href.split("#")[0];
    return pathname === baseHref || pathname.startsWith(baseHref + "/");
  };

  return (
    <div className={`app-shell ${isOffice ? "office-mode" : ""}`}>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div 
          className="sidebar-backdrop" 
          onClick={() => setMobileOpen(false)}
          aria-hidden="true" 
        />
      )}

      {/* Modern Minimalist Sidebar */}
      <aside className={`app-sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="sidebar-header">
          <Link href="/" className="brand-badge" onClick={() => setMobileOpen(false)}>
            <div className="brand-dot" />
            <div className="brand-text">
              <span className="brand-title">{BRAND.name}</span>
              <span className="brand-sub">{BRAND.sub}</span>
            </div>
          </Link>
          <button 
            type="button" 
            className="mobile-close-btn"
            onClick={() => setMobileOpen(false)}
            aria-label="Tutup Menu"
          >
            ✕
          </button>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group-title">MARKETING COMMAND</div>
          <ul className="nav-list">
            {SIDEBAR_ITEMS.map((item) => {
              const active = isActive(item.href);
              return (
                <li key={item.href} className="nav-item">
                  <Link
                    href={item.href}
                    className={`nav-link ${active ? "active" : ""}`}
                    onClick={() => setMobileOpen(false)}
                  >
                    <span className="nav-icon" aria-hidden="true">{item.icon}</span>
                    <span className="nav-label">{t(item.key as any) || item.key}</span>
                    {item.badge && <span className="nav-badge">{item.badge}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="nav-group-title secondary-group">WORKSPACE</div>
          <ul className="nav-list">
            <li className="nav-item">
              <Link
                href="/projects"
                className={`nav-link ${pathname.startsWith("/projects") ? "active" : ""}`}
                onClick={() => setMobileOpen(false)}
              >
                <span className="nav-icon" aria-hidden="true">📁</span>
                <span className="nav-label">{t("nav.projects")}</span>
              </Link>
            </li>
            <li className="nav-item">
              <Link
                href="/office"
                className={`nav-link ${pathname === "/office" ? "active" : ""}`}
                onClick={() => setMobileOpen(false)}
              >
                <span className="nav-icon" aria-hidden="true">🏢</span>
                <span className="nav-label">{t("nav.office")}</span>
              </Link>
            </li>
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="avatar-chip">CEO</div>
            <div className="user-info">
              <span className="user-name">Roihan Admin</span>
              <span className="user-role">Marketing & Growth</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="app-main-wrapper">
        <header className="app-header">
          <div className="header-left">
            <button
              type="button"
              className="hamburger-btn"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Menu"
            >
              ☰
            </button>
            <div className="header-title">
              <span className="header-crumb">Roihan AI Office</span>
              <span className="header-separator">/</span>
              <span className="header-page">
                {SIDEBAR_ITEMS.find((i) => isActive(i.href))
                  ? t(SIDEBAR_ITEMS.find((i) => isActive(i.href))!.key as any)
                  : pathname.replace("/", "") || "Overview"}
              </span>
            </div>
          </div>

          <div className="header-right">
            <LanguageSwitcher />
            <div className="status-indicator-pill" title="Sistem Aktif">
              <span className="pulse-dot" />
              <span className="pill-text">Online</span>
            </div>
          </div>
        </header>

        <main className="app-content-body">
          {children}
        </main>
      </div>
    </div>
  );
}
