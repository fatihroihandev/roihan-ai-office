"use client";

import { useState } from "react";
import { AiFeature } from "./AiFeature";
import { Icon } from "@/components/ui/Icons";

const SPECIALIST_ICONS: Record<number, string> = {
  0: "bot",
  1: "target",
  2: "globe",
  3: "pen",
  4: "share",
  5: "target",
  6: "users",
  7: "mail",
  8: "send",
  9: "trend-up",
  10: "chart",
  11: "zap",
};

export function SettingsFeature() {
  const [activeTab, setActiveTab] = useState<"ai" | "team" | "workspace" | "security">("ai");

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="workspace-header">
        <div className="workspace-greeting">
          <h2>Settings &amp; AI Provider Control</h2>
          <p>
            Konfigurasi provider model AI, batas anggaran bulanan, spesifikasi 12 peran agen pemasaran, dan keamanan workspace.
          </p>
        </div>
        <div className="workspace-header-actions">
          <button
            type="button"
            className={activeTab === "ai" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("ai")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="sparkles" size={14} />
            <span>AI Provider &amp; Anggaran</span>
          </button>
          <button
            type="button"
            className={activeTab === "team" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("team")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="users" size={14} />
            <span>12 Peran Spesialis AI</span>
          </button>
          <button
            type="button"
            className={activeTab === "workspace" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("workspace")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="building" size={14} />
            <span>Profil Workspace</span>
          </button>
          <button
            type="button"
            className={activeTab === "security" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveTab("security")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="shield" size={14} />
            <span>Keamanan &amp; Privasi</span>
          </button>
        </div>
      </div>

      {activeTab === "ai" && <AiFeature />}

      {activeTab === "team" && (
        <div className="white-panel">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="users" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>12 Spesialis AI Marketing Terpadu</h3>
          </div>
          <p className="hint" style={{ marginTop: 0, marginBottom: 16 }}>
            Setiap tugas pemasaran didelegasikan ke peran spesialis dengan batasan konteks dan aturan verifikasi yang spesifik.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 12,
            }}
          >
            {[
              {
                role: "Marketing Director / Orchestrator",
                desc: "Memahami tujuan bisnis, membagi pekerjaan, dan mengonsolidasi hasil lintas modul.",
              },
              {
                role: "Marketing Strategist",
                desc: "Menganalisis positioning produk, menyusun rencana kanal, dan menetapkan target KPI.",
              },
              {
                role: "SEO & Growth Specialist",
                desc: "Audit SEO teknis, riset kata kunci, analisis gap kompetitor, dan optimasi on-page.",
              },
              {
                role: "Content Strategist & Writer",
                desc: "Menyusun brief konten, menulis artikel/materi sosial, dan memvalidasi klaim produk.",
              },
              {
                role: "Social Media Specialist",
                desc: "Perencanaan distribusi konten multi-platform dan penjadwalan publikasi.",
              },
              {
                role: "Campaign & Ads Specialist",
                desc: "Strategi audiens kampanye, eksperimen pesan kreatif, dan pengendalian anggaran.",
              },
              {
                role: "Lead Generation Specialist",
                desc: "Riset prospek publik yang sah, ekstraksi fakta bisnis, dan penilaian awal.",
              },
              {
                role: "CRM & Lifecycle Specialist",
                desc: "Segmentasi kontak B2B, pengelolaan tahapan peluang, dan tindak lanjut klien.",
              },
              {
                role: "Email Marketing Specialist",
                desc: "Penyusunan draf email outreach terpersonalisasi dan kepatuhan opt-out.",
              },
              {
                role: "CRO Specialist",
                desc: "Evaluasi hambatan konversi halaman arahan dan rekomendasi peningkatan rasio klik.",
              },
              {
                role: "Marketing Data Analyst",
                desc: "Validasi metrik organik, corong konversi, atribusi sumber, dan pelaporan ROI.",
              },
              {
                role: "Marketing Automation Specialist",
                desc: "Pengelolaan alur kerja berbasis pemicu dan kebijakan retensi data otomatis.",
              },
            ].map((sp, idx) => (
              <div
                key={sp.role}
                style={{
                  padding: 14,
                  borderRadius: "var(--radius-md)",
                  background: "var(--surface-subtle)",
                  border: "1px solid var(--border)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 12,
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "var(--radius-md)",
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    color: "var(--accent)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <Icon name={SPECIALIST_ICONS[idx] ?? "bot"} size={18} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: 4,
                      gap: 6,
                    }}
                  >
                    <strong style={{ fontSize: "0.86rem" }}>{sp.role}</strong>
                    <span className="badge">#{String(idx + 1).padStart(2, "0")}</span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.78rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    {sp.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "workspace" && (
        <div className="white-panel">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="building" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>Profil Workspace</h3>
          </div>
          <div style={{ display: "grid", gap: 12, maxWidth: 480 }}>
            <label>
              Nama Platform
              <input type="text" disabled value="Roihan AI Office" />
            </label>
            <label>
              Mode Akses
              <input type="text" disabled value="Single-Owner Authenticated Workspace" />
            </label>
            <label>
              Zona Waktu Standar
              <input type="text" disabled value="Asia/Jakarta (WIB, UTC+7)" />
            </label>
          </div>
        </div>
      )}

      {activeTab === "security" && (
        <div className="white-panel">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: "var(--info)", display: "flex" }}>
              <Icon name="shield" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>Kebijakan Keamanan &amp; Tata Kelola Data</h3>
          </div>
          <ul
            style={{
              margin: 0,
              paddingLeft: 18,
              fontSize: "0.85rem",
              display: "grid",
              gap: 10,
            }}
          >
            <li>
              <strong>Autentikasi Pemilik Tunggal:</strong> Hanya satu akun pemilik sah yang dapat mengakses aplikasi; pendaftaran publik dinonaktifkan.
            </li>
            <li>
              <strong>Perlindungan SSRF Crawler:</strong> Permintaan ke IP privat (RFC 1918), localhost, dan alamat link-local ditolak di tingkat jaringan.
            </li>
            <li>
              <strong>Sensor Kredensial Otomatis:</strong> Kunci API dan token rahasia selalu disamarkan dalam log aplikasi dan pesan galat.
            </li>
            <li>
              <strong>Persetujuan Manusia (Human-in-the-Loop):</strong> Publikasi konten dan pengiriman pesan keluar membutuhkan persetujuan eksplisit pemilik.
            </li>
            <li>
              <strong>Kepatuhan Privasi UU PDP:</strong> Prospek yang melewati batas retensi tanpa interaksi ditandai untuk anonimisasi atau penghapusan.
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
