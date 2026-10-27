"use client";

import Link from "next/link";
import { useState } from "react";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { useInsights } from "@/lib/charts/useInsights";
import { CommandDeck } from "@/components/charts/CommandDeck";
import { LiveStrip } from "@/components/home/LiveStrip";

export function InspiredDashboard() {
  const { data, stale, connected } = useOfficeData();
  const ins = useInsights(data?.generated_at ?? null);
  const [activeTab, setActiveTab] = useState<"dash1" | "dash2" | "admin">("dash1");
  const [timeframe, setTimeframe] = useState<"Weekly" | "Monthly">("Weekly");
  const [searchQuery, setSearchQuery] = useState("");

  const aiCalls = data?.ai?.calls_24h ?? 1428;
  const activeTasks = data?.tasks?.running ?? 12;
  const completedTasks = data?.tasks?.completed ?? 428;
  const totalLeads = 104;

  return (
    <div className="inspired-dashboard-container">
      {/* 1. Left Slim Dock Sidebar */}
      <aside className="inspired-dock" aria-label="Quick Dock Navigation">
        <Link href="/" className="inspired-dock-logo" title="Roihan AI Office">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 5v14M18 5v14M2 9h4M18 9h4M2 15h4M18 15h4M6 12h12" />
          </svg>
        </Link>

        <ul className="inspired-dock-nav">
          <li>
            <button
              type="button"
              className={`inspired-dock-btn ${activeTab === "dash1" ? "active" : ""}`}
              onClick={() => setActiveTab("dash1")}
              title="Dashboard 1 (Modern Overview)"
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
            <Link href="/marketing/seo" className="inspired-dock-btn" title="Website & Technical SEO">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </Link>
          </li>
          <li>
            <Link href="/marketing/content" className="inspired-dock-btn" title="Content Studio & Campaigns">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            </Link>
          </li>
          <li>
            <Link href="/tasks" className="inspired-dock-btn" title="Activity Log & Timers">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </Link>
          </li>
          <li>
            <Link href="/marketing/leads" className="inspired-dock-btn" title="Leads & CRM">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </Link>
          </li>
          <li>
            <Link href="/ai" className="inspired-dock-btn" title="Settings & Integrations">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </Link>
          </li>
        </ul>

        <div className="inspired-dock-footer">
          <div className="inspired-dock-toggle" title="Office Power Status: Active">
            <div className="inspired-dock-dot" />
          </div>
          <button type="button" className="inspired-dock-btn" title="Night Mode">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          </button>
        </div>
      </aside>

      {/* 2. Center Workspace Panel */}
      <main className="inspired-workspace">
        {/* Header */}
        <div className="workspace-header">
          <div className="workspace-greeting">
            <h2>Good Morning, Roihan 👋</h2>
            <p>Let&apos;s accelerate your marketing &amp; growth operations today</p>
          </div>

          <div className="workspace-header-actions">
            <div className="workspace-search">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                placeholder="Search something here..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <button type="button" className="workspace-bell-btn" title="Notifications">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              <span className="workspace-bell-badge" />
            </button>
          </div>
        </div>

        {activeTab === "dash1" && (
          <>
            {/* Top 4 KPI Cards */}
            <div className="workspace-kpi-grid">
              {/* Card 1: Calories / AI Operations */}
              <div className="kpi-card">
                <div className="kpi-card-top">
                  <span className="kpi-card-title">Calories</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(255, 87, 34, 0.12)", color: "#ff5722" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2c1.1 0 2 .9 2 2 0 .74-.4 1.38-1 1.72v1.56c2.8 1.15 4 4.14 4 6.72 0 4.42-3.58 8-8 8s-8-3.58-8-8c0-3.72 2.56-6.85 6-7.74V5.72C6.4 5.38 6 4.74 6 4c0-1.1.9-2 2-2 1.66 0 3 1.34 3 3 0 .35-.07.69-.18 1 .84-.33 1.77-.5 2.76-.5.48 0 .95.04 1.42.13-.39-.42-.64-.98-.64-1.63 0-1.1.9-2 2-2z" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual">
                  {/* Mini bar chart */}
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
                  <span>Kcal</span>
                </div>
              </div>

              {/* Card 2: Heart Rate / Task Velocity */}
              <div className="kpi-card">
                <div className="kpi-card-top">
                  <span className="kpi-card-title">Heart Rate</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(236, 72, 153, 0.12)", color: "#ec4899" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual">
                  {/* ECG pulse line */}
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
                  <span>bpm/day</span>
                </div>
              </div>

              {/* Card 3: Steps / SEO Growth */}
              <div className="kpi-card">
                <div className="kpi-card-top">
                  <span className="kpi-card-title">Steps</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(16, 185, 129, 0.12)", color: "#10b981" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M13 4v16M17 8l-4-4-4 4" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual" style={{ justifyContent: "center" }}>
                  {/* Semi-circular gauge arch */}
                  <svg width="60" height="32" viewBox="0 0 60 32">
                    <path d="M 6 30 A 24 24 0 0 1 54 30" fill="none" stroke="#e5e7eb" strokeWidth="5" strokeLinecap="round" />
                    <path d="M 6 30 A 24 24 0 0 1 46 12" fill="none" stroke="#10b981" strokeWidth="5" strokeLinecap="round" />
                  </svg>
                </div>
                <div className="kpi-card-stat">
                  <strong style={{ color: "#10b981" }}>9,886</strong>
                  <span>Steps</span>
                </div>
              </div>

              {/* Card 4: Sleep / Position */}
              <div className="kpi-card">
                <div className="kpi-card-top">
                  <span className="kpi-card-title">Sleep</span>
                  <div className="kpi-card-icon" style={{ background: "rgba(59, 130, 246, 0.12)", color: "#3b82f6" }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12.3 2a10 10 0 0 0 9.7 13.7 10 10 0 1 1-9.7-13.7z" />
                    </svg>
                  </div>
                </div>
                <div className="kpi-card-visual">
                  {/* Mini blue bar chart */}
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
                  <span>hrs/day</span>
                </div>
              </div>
            </div>

            {/* Middle Row (Activity Tracking & Focus Banner) */}
            <div className="workspace-middle-grid">
              {/* Activity Tracking */}
              <div className="white-panel">
                <div className="white-panel-header">
                  <span className="white-panel-title">Activity Tracking</span>
                  <select
                    className="pill-select"
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value as any)}
                  >
                    <option value="Weekly">Weekly ▾</option>
                    <option value="Monthly">Monthly ▾</option>
                  </select>
                </div>

                <div className="chart-area-container">
                  <svg width="100%" height="150" viewBox="0 0 460 150" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="splineGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ff5722" stopOpacity="0.35" />
                        <stop offset="100%" stopColor="#ff5722" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Y-axis labels */}
                    <text x="5" y="20" fill="#9ca3af" fontSize="9" fontWeight="600">100%</text>
                    <text x="5" y="50" fill="#9ca3af" fontSize="9" fontWeight="600">80%</text>
                    <text x="5" y="80" fill="#9ca3af" fontSize="9" fontWeight="600">60%</text>
                    <text x="5" y="110" fill="#9ca3af" fontSize="9" fontWeight="600">40%</text>
                    <text x="5" y="138" fill="#9ca3af" fontSize="9" fontWeight="600">20%</text>

                    {/* Spline Area Fill */}
                    <path
                      d="M 40 125 C 80 115, 110 98, 140 102 C 170 106, 190 75, 230 65 C 260 58, 280 82, 320 95 C 350 105, 380 92, 430 110 L 430 140 L 40 140 Z"
                      fill="url(#splineGradient)"
                    />

                    {/* Spline Stroke Line */}
                    <path
                      d="M 40 125 C 80 115, 110 98, 140 102 C 170 106, 190 75, 230 65 C 260 58, 280 82, 320 95 C 350 105, 380 92, 430 110"
                      fill="none"
                      stroke="#ff5722"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                    />

                    {/* Peak Tooltip Pill Indicator */}
                    <circle cx="230" cy="65" r="5" fill="#ffffff" stroke="#ff5722" strokeWidth="3" />
                    <rect x="206" y="32" width="48" height="20" rx="10" fill="#ffffff" stroke="#ff5722" strokeWidth="1" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.15))" />
                    <text x="214" y="45" fill="#ff5722" fontSize="9" fontWeight="800">24 km/h</text>

                    {/* X-axis months */}
                    <text x="40" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Jan</text>
                    <text x="80" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Feb</text>
                    <text x="120" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Mar</text>
                    <text x="160" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Apr</text>
                    <text x="200" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">May</text>
                    <text x="240" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Jun</text>
                    <text x="280" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Jul</text>
                    <text x="320" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Aug</text>
                    <text x="360" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Sep</text>
                    <text x="400" y="148" fill="#9ca3af" fontSize="9" fontWeight="500">Oct</text>
                  </svg>
                </div>
              </div>

              {/* Running with resistance band / Focus Card */}
              <div className="white-panel focus-banner-card">
                <div className="focus-banner-info">
                  <h3>Running with resistance band</h3>

                  <div className="focus-banner-stat-block">
                    <strong>{activeTasks} km</strong>
                    <span>Today&apos;s distance</span>
                  </div>

                  <div className="focus-banner-stat-block">
                    <strong>{completedTasks} km</strong>
                    <span>Total distance covered</span>
                  </div>
                </div>

                <div className="focus-banner-image">
                  {/* High quality illustrative graphic matching the reference photo */}
                  <svg width="100%" height="100%" viewBox="0 0 140 140" fill="none">
                    <rect width="140" height="140" fill="#2d3748" />
                    <circle cx="70" cy="50" r="28" fill="#4a5568" />
                    <path d="M40 120 C 50 85, 90 85, 100 120" fill="#e2e8f0" opacity="0.9" />
                    <rect x="30" y="115" width="80" height="25" rx="6" fill="#1a202c" />
                    <circle cx="85" cy="45" r="14" fill="#cbd5e0" />
                    <path d="M60 70 L95 110" stroke="#ff5722" strokeWidth="4" strokeLinecap="round" />
                    <path d="M55 105 L80 125" stroke="#ff5722" strokeWidth="4" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Bottom Strategy & Workspaces ("Diet Plan" equivalent) */}
            <div className="workspace-bottom-section">
              <div className="section-head-row">
                <div className="section-head-title">
                  <span className="section-head-bar">|</span>
                  <span>Diet Plan</span>
                </div>
                <Link href="/marketing" className="section-head-link">view all</Link>
              </div>

              <div className="workspace-bottom-grid">
                {/* Card 1: Fruits only (White) */}
                <Link href="/marketing/seo" className="strategy-card white">
                  <div className="strategy-card-text">
                    <strong>Fruits only</strong>
                    <p>It contains most water contain in it.</p>
                    <span className="strategy-card-badge">Day 1</span>
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
                </Link>

                {/* Card 2: Vegetables only (Vibrant Orange Card!) */}
                <Link href="/marketing/content" className="strategy-card orange">
                  <div className="strategy-card-text">
                    <strong>Vegetables only</strong>
                    <p>It contains most water contain in it.</p>
                    <span className="strategy-card-badge">Day 2</span>
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
                </Link>

                {/* Card 3: Fruits and Vegetables (White) */}
                <Link href="/marketing/leads" className="strategy-card white">
                  <div className="strategy-card-text">
                    <strong>Fruits and Vegetables</strong>
                    <p>It contains most water contain in it.</p>
                    <span className="strategy-card-badge">Day 3</span>
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
                </Link>
              </div>
            </div>
          </>
        )}

        {activeTab === "dash2" && (
          <div style={{ marginTop: "10px" }}>
            <LiveStrip data={data} stale={stale} ins={ins} />
            {data && <CommandDeck d={data} ins={ins} />}
          </div>
        )}

        {activeTab === "admin" && (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <h3 style={{ fontSize: "1.3rem", color: "#fff", marginBottom: "10px" }}>🏢 Virtual Office &amp; System Administration</h3>
            <p style={{ color: "#9ca3af", maxWidth: "500px", margin: "0 auto 24px" }}>
              Access the interactive 3D virtual office, team avatar telemetry, power control, and backup systems.
            </p>
            <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
              <Link href="/office" className="switch-dock-btn active" style={{ textDecoration: "none" }}>
                Enter Virtual Office 🏢
              </Link>
              <Link href="/approvals" className="switch-dock-btn" style={{ background: "rgba(255,255,255,0.08)", textDecoration: "none" }}>
                Approvals Center 🛡️
              </Link>
            </div>
          </div>
        )}

        {/* Bottom Floating Segmented Switch Dock */}
        <div className="inspired-switch-dock">
          <span className="switch-dock-label">SWITCH</span>
          <button
            type="button"
            className={`switch-dock-btn ${activeTab === "dash1" ? "active" : ""}`}
            onClick={() => setActiveTab("dash1")}
          >
            ⚡ Dashboard 1
          </button>
          <button
            type="button"
            className={`switch-dock-btn ${activeTab === "dash2" ? "active" : ""}`}
            onClick={() => setActiveTab("dash2")}
          >
            🌿 Dashboard 2
          </button>
          <button
            type="button"
            className={`switch-dock-btn ${activeTab === "admin" ? "active" : ""}`}
            onClick={() => setActiveTab("admin")}
          >
            📊 Admin
          </button>
        </div>
      </main>

      {/* 3. Right Profile & Calendar Panel */}
      <aside className="inspired-sidebar-panel" aria-label="Profile and Calendar Panel">
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
              <strong>Lionel Messi ▾</strong>
              <span>@itsworks</span>
            </div>
          </div>
          <button type="button" className="profile-more-btn" title="Options">···</button>
        </div>

        {/* User Stats Row (Weight / Height / Age) */}
        <div className="profile-stats-row">
          <div className="profile-stat-col">
            <strong>75 kg</strong>
            <span>Weight</span>
          </div>
          <div className="profile-stat-col">
            <strong>180 cm</strong>
            <span>Height</span>
          </div>
          <div className="profile-stat-col">
            <strong>26 yrs</strong>
            <span>Age</span>
          </div>
        </div>

        {/* Calendar Widget (December 2022 matching reference image) */}
        <div className="calendar-widget">
          <div className="calendar-header">
            <strong>December 2022</strong>
            <div className="calendar-nav-btns">
              <button type="button" className="calendar-nav-btn">&lt;</button>
              <button type="button" className="calendar-nav-btn">&gt;</button>
            </div>
          </div>

          <div className="calendar-grid">
            {/* Days of week */}
            <span className="calendar-day-label">Su</span>
            <span className="calendar-day-label">Mo</span>
            <span className="calendar-day-label">Tu</span>
            <span className="calendar-day-label">We</span>
            <span className="calendar-day-label">Th</span>
            <span className="calendar-day-label">Fr</span>
            <span className="calendar-day-label">Sa</span>

            {/* Days row 1 */}
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>27</span>
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>28</span>
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>29</span>
            <span className="calendar-date-cell" style={{ opacity: 0.3 }}>30</span>
            <span className="calendar-date-cell">1</span>
            <span className="calendar-date-cell">2</span>
            <span className="calendar-date-cell">3</span>

            {/* Days row 2 */}
            <span className="calendar-date-cell">4</span>
            <span className="calendar-date-cell">5</span>
            <span className="calendar-date-cell">6</span>
            <span className="calendar-date-cell">7</span>
            <span className="calendar-date-cell">8</span>
            <span className="calendar-date-cell">9</span>
            <span className="calendar-date-cell">10</span>

            {/* Days row 3 */}
            <span className="calendar-date-cell">11</span>
            <span className="calendar-date-cell">12</span>
            <span className="calendar-date-cell">13</span>
            <span className="calendar-date-cell">14</span>
            <span className="calendar-date-cell">15</span>
            <span className="calendar-date-cell">16</span>
            <span className="calendar-date-cell badge-green">17</span>

            {/* Days row 4 */}
            <span className="calendar-date-cell">18</span>
            <span className="calendar-date-cell">19</span>
            <span className="calendar-date-cell">20</span>
            <span className="calendar-date-cell badge-green">21</span>
            <span className="calendar-date-cell">22</span>
            <span className="calendar-date-cell badge-orange">23</span>
            <span className="calendar-date-cell">24</span>

            {/* Days row 5 */}
            <span className="calendar-date-cell badge-red">25</span>
            <span className="calendar-date-cell">26</span>
            <span className="calendar-date-cell">27</span>
            <span className="calendar-date-cell">28</span>
            <span className="calendar-date-cell">29</span>
            <span className="calendar-date-cell">30</span>
            <span className="calendar-date-cell">31</span>
          </div>
        </div>

        {/* Scheduled List Section */}
        <div className="scheduled-section">
          <div className="section-head-row">
            <div className="section-head-title">
              <span className="section-head-bar">|</span>
              <span>Scheduled</span>
            </div>
            <Link href="/tasks" className="section-head-link">view all</Link>
          </div>

          <div className="scheduled-list">
            {/* Item 1 */}
            <div className="scheduled-item">
              <div className="scheduled-thumb">
                <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
                  <rect width="44" height="44" fill="#374151" />
                  <circle cx="22" cy="18" r="8" fill="#f43f5e" />
                  <path d="M12 36 L22 26 L32 36" stroke="#ffffff" strokeWidth="2.5" />
                </svg>
              </div>
              <div className="scheduled-info">
                <span className="scheduled-tag">Fitness</span>
                <strong>Cardio Workshop</strong>
                <span>Strengthens your muscles</span>
              </div>
              <div className="scheduled-meta">
                <span className="scheduled-date">17-21 Dec</span>
                <button type="button" className="profile-more-btn" style={{ width: 22, height: 22, fontSize: "0.6rem" }}>···</button>
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
                <span className="scheduled-tag">Fitness</span>
                <strong>Cardio Workshop</strong>
                <span>Strengthens your muscles</span>
              </div>
              <div className="scheduled-meta">
                <span className="scheduled-date">17-21 Dec</span>
                <button type="button" className="profile-more-btn" style={{ width: 22, height: 22, fontSize: "0.6rem" }}>···</button>
              </div>
            </div>

            {/* Item 3 */}
            <div className="scheduled-item">
              <div className="scheduled-thumb">
                <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
                  <rect width="44" height="44" fill="#312e81" />
                  <circle cx="22" cy="18" r="7" fill="#a855f7" />
                  <path d="M14 34 Q 22 24 30 34" stroke="#818cf8" strokeWidth="2.5" fill="none" />
                </svg>
              </div>
              <div className="scheduled-info">
                <span className="scheduled-tag">Fitness</span>
                <strong>Cardio Workshop</strong>
                <span>Strengthens your muscles</span>
              </div>
              <div className="scheduled-meta">
                <span className="scheduled-date">17-21 Dec</span>
                <button type="button" className="profile-more-btn" style={{ width: 22, height: 22, fontSize: "0.6rem" }}>···</button>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
