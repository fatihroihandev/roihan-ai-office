"use client";

import { useState } from "react";
import { AiFeature } from "./AiFeature";
import { Icon, type IconName } from "@/components/ui/Icons";

interface SpecialistRole {
  key: string;
  role: string;
  dept: "coordination" | "marketing" | "engineering";
  icon: IconName;
  desc: string;
}

const SPECIALIST_ROLES: SpecialistRole[] = [
  {
    key: "manager",
    role: "Marketing / Project Orchestrator",
    dept: "coordination",
    icon: "bot",
    desc: "Memahami sasaran bisnis, membagi pekerjaan menjadi draft tasks terstruktur, memilih agen spesialis, dan menyusun laporan konsolidasi.",
  },
  {
    key: "seo_specialist",
    role: "SEO & Growth Specialist",
    dept: "marketing",
    icon: "globe",
    desc: "Audit SEO teknis & on-page deterministik, riset kata kunci berbasis bukti sumber, analisis gap kompetitor, dan rekomendasi optimasi.",
  },
  {
    key: "market_research",
    role: "Market & Competitor Researcher",
    dept: "marketing",
    icon: "search",
    desc: "Riset tren pasar, identifikasi lanskap persaingan, benchmark produk kompetitor, dan perumusan fakta grounding terverifikasi.",
  },
  {
    key: "lead_generation",
    role: "Lead Generation & CRM Intake",
    dept: "marketing",
    icon: "target",
    desc: "Riset prospek B2B dari sumber publik sah, ekstraksi kontak bisnis, kalkulasi skor kecocokan deterministik, dan kepatuhan UU PDP.",
  },
  {
    key: "content_promotion",
    role: "Content & Copywriting Specialist",
    dept: "marketing",
    icon: "pen",
    desc: "Penyusunan brief editorial, penulisan artikel, landing page, materi sosial media, newsletter, dan validasi linter klaim produk.",
  },
  {
    key: "sales_client_relations",
    role: "B2B Outreach & CRM Specialist",
    dept: "marketing",
    icon: "mail",
    desc: "Penyusunan draf pesan pendekatan B2B dipersonalisasi dengan klausa unsubscribe, pengelolaan tahapan peluang, dan catatan interaksi.",
  },
  {
    key: "marketing_analytics",
    role: "Marketing Analytics & Growth",
    dept: "marketing",
    icon: "chart",
    desc: "Validasi metrik organik, analisis corong konversi prospek, atribusi sumber performa kampanye, dan pelaporan ROI terukur.",
  },
  {
    key: "analyst",
    role: "System & Requirement Analyst",
    dept: "engineering",
    icon: "file-text",
    desc: "Analisis kebutuhan fitur, spesifikasi teknis arsitektur, dan perumusan acceptance criteria tugas terukur.",
  },
  {
    key: "developer",
    role: "Full-Stack Developer",
    dept: "engineering",
    icon: "cpu",
    desc: "Implementasi kode aplikasi web, integrasi API sistem, penyelesaian bug, dan penulisan unit test.",
  },
  {
    key: "qa",
    role: "Quality Assurance Specialist",
    dept: "engineering",
    icon: "check-circle",
    desc: "Eksekusi automated test suite, validasi regresi, verifikasi acceptance criteria, dan pelaporan cacat perangkat lunak.",
  },
  {
    key: "reviewer",
    role: "Senior Code Reviewer & Security Gate",
    dept: "engineering",
    icon: "shield",
    desc: "Audit review kode deterministik, verifikasi keamanan sandbox eksekusi, dan penegakan standar kode.",
  },
  {
    key: "reporter",
    role: "Technical Documentation Specialist",
    dept: "engineering",
    icon: "sparkles",
    desc: "Penyusunan dokumentasi teknis, catatan rilis produk, panduan operasional pengguna, dan laporan kemajuan berkala.",
  },
];

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
            <h3 style={{ margin: 0 }}>12 Peran Spesialis AI (Katalog Task Engine)</h3>
          </div>
          <p className="hint" style={{ marginTop: 0, marginBottom: 16 }}>
            Setiap pekerjaan didelegasikan ke peran spesialis terdaftar (Koordinasi, Marketing, Engineering) dengan batasan kewenangan deny-by-default.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 12,
            }}
          >
            {SPECIALIST_ROLES.map((sp, idx) => (
              <div
                key={sp.key}
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
                  <Icon name={sp.icon} size={18} />
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
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span className="badge" style={{ textTransform: "capitalize", fontSize: "0.68rem" }}>{sp.dept}</span>
                      <span className="badge">#{String(idx + 1).padStart(2, "0")}</span>
                    </div>
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
