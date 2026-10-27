"use client";

import { useState } from "react";
import { AiFeature } from "./AiFeature";

export function SettingsFeature() {
  const [activeTab, setActiveTab] = useState<"workspace" | "team" | "ai" | "security">("ai");

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0, color: "var(--dash-text-main)" }}>
            ⚙️ Pengaturan &amp; AI Provider Control
          </h2>
          <p style={{ margin: "4px 0 0", color: "var(--dash-text-muted)", fontSize: "0.85rem" }}>
            Konfigurasi workspace, peran spesialis AI marketing, Google Gemini API, anggaran biaya, dan keamanan sistem.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className={activeTab === "ai" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("ai")}
          >
            AI Provider &amp; Anggaran
          </button>
          <button
            type="button"
            className={activeTab === "team" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("team")}
          >
            Spesialis AI ({12} Peran)
          </button>
          <button
            type="button"
            className={activeTab === "workspace" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("workspace")}
          >
            Workspace
          </button>
          <button
            type="button"
            className={activeTab === "security" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("security")}
          >
            Keamanan &amp; Privasi
          </button>
        </div>
      </div>

      {/* Subtab: AI Provider (AiFeature) */}
      {activeTab === "ai" && <AiFeature />}

      {/* Subtab: Team & Roles */}
      {activeTab === "team" && (
        <div className="white-panel">
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
            🤖 12 Spesialis AI Marketing Terpadu (Master Addendum v2.0 Bagian V)
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
            {[
              { role: "Marketing Director / Orchestrator", desc: "Memahami tujuan bisnis, membagi pekerjaan & mengonsolidasi hasil", icon: "👑" },
              { role: "Marketing Strategist", desc: "Menganalisis positioning, menyusun rencana channel & KPI", icon: "🧭" },
              { role: "SEO & Growth Specialist", desc: "Audit SEO teknis, keyword research, gap analysis & on-page", icon: "🌐" },
              { role: "Content Strategist & Writer", desc: "Brief, penulisan artikel, repurposing & review klaim", icon: "✍️" },
              { role: "Social Media Specialist", desc: "Perencanaan konten multi-platform & jadwal publikasi", icon: "📱" },
              { role: "Campaign & Ads Specialist", desc: "Strategi audiens kampanye, eksperimen kreatif & alokasi budget", icon: "🚀" },
              { role: "Lead Generation Specialist", desc: "Strategi lead magnet, formulir capture & aturan kualifikasi", icon: "🎯" },
              { role: "CRM & Lifecycle Specialist", desc: "Segmentasi kontak, alur tindak lanjut & retensi klien", icon: "👥" },
              { role: "Email Marketing Specialist", desc: "Kampanye email outreach, subjek kontekstual & deliverability", icon: "✉️" },
              { role: "CRO Specialist", desc: "Analisis corong konversi, pengujian hipotesis landing page", icon: "📈" },
              { role: "Marketing Data Analyst", desc: "Validasi metrik, tren kinerja, deteksi anomali & pelaporan", icon: "📊" },
              { role: "Marketing Automation Specialist", desc: "Desain alur kerja pemicu, integrasi alat & penanganan error", icon: "⚡" },
            ].map((sp) => (
              <div key={sp.role} style={{ padding: 12, borderRadius: 14, background: "var(--dash-pill-bg)", border: "1px solid var(--dash-border)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: "1.2rem" }}>{sp.icon}</span>
                  <strong style={{ fontSize: "0.86rem", color: "var(--dash-text-main)" }}>{sp.role}</strong>
                </div>
                <p style={{ fontSize: "0.76rem", color: "var(--dash-text-muted)", margin: 0 }}>{sp.desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Subtab: Workspace */}
      {activeTab === "workspace" && (
        <div className="white-panel">
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
            🏢 Profil Ruang Kerja (Workspace)
          </h3>
          <div style={{ display: "grid", gap: 14, maxWidth: 500 }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--dash-text-muted)", marginBottom: 4 }}>
                Nama Organisasi / Platform
              </label>
              <input
                type="text"
                disabled
                value="Roihan AI Office"
                style={{ width: "100%", padding: 9, borderRadius: 10, border: "1px solid var(--dash-border)", background: "var(--dash-pill-bg)", color: "var(--dash-text-main)" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--dash-text-muted)", marginBottom: 4 }}>
                Domain Resmi Perusahaan
              </label>
              <input
                type="text"
                disabled
                value="https://roihan.id"
                style={{ width: "100%", padding: 9, borderRadius: 10, border: "1px solid var(--dash-border)", background: "var(--dash-pill-bg)", color: "var(--dash-text-main)" }}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--dash-text-muted)", marginBottom: 4 }}>
                Zona Waktu Operasional
              </label>
              <input
                type="text"
                disabled
                value="Asia/Jakarta (WIB, UTC+7)"
                style={{ width: "100%", padding: 9, borderRadius: 10, border: "1px solid var(--dash-border)", background: "var(--dash-pill-bg)", color: "var(--dash-text-main)" }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Subtab: Security */}
      {activeTab === "security" && (
        <div className="white-panel">
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
            🔒 Kebijakan Keamanan &amp; Governance
          </h3>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: "0.84rem", color: "var(--dash-text-main)", display: "grid", gap: 10 }}>
            <li><strong>Perlindungan SSRF Crawler:</strong> IP privat (RFC 1918), localhost, dan link-local diblokir ketat oleh filter socket backend.</li>
            <li><strong>Redaksi Secret Otomatis:</strong> Kunci API dan token OAuth otomatis disensor menjadi [REDACTED] dalam file log dan error trace.</li>
            <li><strong>Human-in-the-Loop Approval:</strong> Tindakan penerbitan artikel produksi, kampanye email massal, dan modifikasi budget memerlukan segel persetujuan eksplisit.</li>
            <li><strong>Kepatuhan UU PDP No. 27/2022:</strong> Data prospek yang tidak berinteraksi selama 180 hari otomatis ditandai untuk persetujuan anonimisasi atau penghapusan permanen.</li>
          </ul>
        </div>
      )}
    </div>
  );
}
