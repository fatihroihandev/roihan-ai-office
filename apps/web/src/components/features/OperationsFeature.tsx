"use client";

import { useState } from "react";
import { ApprovalsFeature } from "./ApprovalsFeature";
import { TasksFeature } from "./TasksFeature";

export function OperationsFeature() {
  const [activeSubtab, setActiveSubtab] = useState<"approvals" | "tasks" | "integrations" | "engine">("approvals");

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* Operations Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0, color: "var(--dash-text-main)" }}>
            🛡️ Pusat Operasi, Persetujuan &amp; Log Agen
          </h2>
          <p style={{ margin: "4px 0 0", color: "var(--dash-text-muted)", fontSize: "0.85rem" }}>
            Audit trail eksekusi AI, kontrol tindakan berisiko tinggi (Human-in-the-Loop), dan status integrasi infrastruktur.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className={activeSubtab === "approvals" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("approvals")}
          >
            Pusat Persetujuan (Approval)
          </button>
          <button
            type="button"
            className={activeSubtab === "tasks" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("tasks")}
          >
            Log Aktivitas Tugas AI
          </button>
          <button
            type="button"
            className={activeSubtab === "integrations" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("integrations")}
          >
            Konektor &amp; Integrasi
          </button>
          <button
            type="button"
            className={activeSubtab === "engine" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("engine")}
          >
            Status Engine &amp; Worker
          </button>
        </div>
      </div>

      {/* Subtab: Approvals */}
      {activeSubtab === "approvals" && <ApprovalsFeature />}

      {/* Subtab: Tasks Log */}
      {activeSubtab === "tasks" && <TasksFeature />}

      {/* Subtab: Integrations */}
      {activeSubtab === "integrations" && (
        <div className="white-panel">
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
            🔌 Status Integrasi Resmi
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
            {[
              { name: "Google Gemini API", type: "AI Provider", status: "Terhubung / Aktif", tone: "#10b981", detail: "gemini-2.5-flash & gemini-2.5-pro" },
              { name: "PostgreSQL Database", type: "Penyimpanan Utama", status: "Terhubung (48 tabel)", tone: "#10b981", detail: "psycopg v3, Alembic rev 0014" },
              { name: "Web Crawler Engine", type: "SEO & Growth", status: "Aktif (SSRF Guarded)", tone: "#10b981", detail: "Private IP blocked, DNS pinned" },
              { name: "Google Search Console", type: "Search Analytics", status: "OAuth Siap", tone: "#3b82f6", detail: "Menunggu koneksi akun pengguna" },
              { name: "LinkedIn & Meta APIs", type: "Media Sosial", status: "Terkonfigurasi", tone: "#3b82f6", detail: "Scope publikasi postingan aman" },
              { name: "Email SMTP / REST", type: "Outreach & Notifikasi", status: "Terkontrol", tone: "#10b981", detail: "Supresi UU PDP otomatis aktif" },
            ].map((conn) => (
              <div key={conn.name} style={{ padding: 14, borderRadius: 14, background: "var(--dash-pill-bg)", border: "1px solid var(--dash-border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <strong style={{ fontSize: "0.9rem", color: "var(--dash-text-main)" }}>{conn.name}</strong>
                  <span style={{ fontSize: "0.72rem", padding: "2px 8px", borderRadius: 8, background: "var(--dash-input-bg)", color: conn.tone, fontWeight: 600 }}>
                    {conn.status}
                  </span>
                </div>
                <span style={{ fontSize: "0.75rem", color: "var(--dash-text-muted)", display: "block" }}>{conn.type} • {conn.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Subtab: Engine */}
      {activeSubtab === "engine" && (
        <div className="white-panel">
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
            ⚙️ Task Engine &amp; Worker Concurrency
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
            <div className="kpi-card">
              <span className="kpi-card-title">Maks. Tugas Konkuren</span>
              <strong style={{ color: "#ff5722" }}>1</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Antrean terurut aman</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Jeda Polling Worker</span>
              <strong style={{ color: "#3b82f6" }}>1.0s</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Reaktif &amp; hemat resource</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Maks. Percobaan (Retry)</span>
              <strong style={{ color: "#10b981" }}>2x</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Dengan backoff eksponensial</span>
            </div>
          </div>
          <p style={{ fontSize: "0.82rem", color: "var(--dash-text-muted)", margin: 0 }}>
            Task engine menjaga idempotensi penuh untuk setiap tindakan eksternal. Perubahan status tugas dipersistenkan langsung ke database PostgreSQL sehingga tidak bergantung pada koneksi WebSocket semata.
          </p>
        </div>
      )}
    </div>
  );
}
