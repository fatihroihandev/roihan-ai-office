"use client";

import { useState } from "react";
import { ApprovalsFeature } from "./ApprovalsFeature";
import { TasksFeature } from "./TasksFeature";
import { ProjectsFeature } from "./ProjectsFeature";
import { ProductsFeature } from "./ProductsFeature";

export function OperationsFeature() {
  const [activeSubtab, setActiveSubtab] = useState<
    "approvals" | "tasks" | "products" | "projects" | "integrations"
  >("approvals");

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="workspace-header">
        <div className="workspace-greeting">
          <h2>Operations, Approvals &amp; Governance</h2>
          <p>
            Pusat persetujuan tindakan sensitif (Human-in-the-Loop), antrean tugas agen AI, katalog produk, dan berkas proyek.
          </p>
        </div>
        <div className="workspace-header-actions">
          <button
            type="button"
            className={activeSubtab === "approvals" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("approvals")}
          >
            Persetujuan (Approvals)
          </button>
          <button
            type="button"
            className={activeSubtab === "tasks" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("tasks")}
          >
            Antrean &amp; Log Tugas AI
          </button>
          <button
            type="button"
            className={activeSubtab === "products" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("products")}
          >
            Produk &amp; Klaim
          </button>
          <button
            type="button"
            className={activeSubtab === "projects" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("projects")}
          >
            Proyek &amp; Berkas
          </button>
          <button
            type="button"
            className={activeSubtab === "integrations" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("integrations")}
          >
            Status Infrastruktur
          </button>
        </div>
      </div>

      {activeSubtab === "approvals" && <ApprovalsFeature />}
      {activeSubtab === "tasks" && <TasksFeature />}
      {activeSubtab === "products" && <ProductsFeature />}
      {activeSubtab === "projects" && <ProjectsFeature />}

      {activeSubtab === "integrations" && (
        <div className="white-panel">
          <h3>Status Infrastruktur &amp; Konektor Sistem</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 12,
            }}
          >
            {[
              {
                name: "Google Gemini API",
                type: "AI Provider Utama",
                status: "Terkonfigurasi",
                detail: "Routing otomatis model spesialis pemasaran",
              },
              {
                name: "PostgreSQL Database",
                type: "Penyimpanan Transaksional",
                status: "Aktif",
                detail: "Alembic migration rev 0015 (Single-Owner Auth)",
              },
              {
                name: "Web Crawler & Audit Engine",
                type: "SEO & Growth",
                status: "SSRF Guard Aktif",
                detail: "Blokir otomatis IP privat, loopback, dan link-local",
              },
              {
                name: "Human-in-the-Loop Gate",
                type: "Governance & Outbound",
                status: "Wajib Persetujuan",
                detail: "Publikasi & outreach eksternal memerlukan segel pemilik",
              },
            ].map((conn) => (
              <div
                key={conn.name}
                style={{
                  padding: 14,
                  borderRadius: "var(--radius-md)",
                  background: "var(--surface-subtle)",
                  border: "1px solid var(--border)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 4,
                  }}
                >
                  <strong style={{ fontSize: "0.88rem" }}>{conn.name}</strong>
                  <span className="badge" data-state="active">
                    {conn.status}
                  </span>
                </div>
                <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  {conn.type} • {conn.detail}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
