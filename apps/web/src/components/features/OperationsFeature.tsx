"use client";

import { useState } from "react";
import { ApprovalsFeature } from "./ApprovalsFeature";
import { TasksFeature } from "./TasksFeature";
import { ProjectsFeature } from "./ProjectsFeature";
import { ProductsFeature } from "./ProductsFeature";
import { Icon } from "@/components/ui/Icons";

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
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="check-circle" size={14} />
            <span>Persetujuan (Approvals)</span>
          </button>
          <button
            type="button"
            className={activeSubtab === "tasks" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("tasks")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="list-todo" size={14} />
            <span>Antrean &amp; Log Tugas AI</span>
          </button>
          <button
            type="button"
            className={activeSubtab === "products" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("products")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="box" size={14} />
            <span>Produk &amp; Klaim</span>
          </button>
          <button
            type="button"
            className={activeSubtab === "projects" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("projects")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="folder" size={14} />
            <span>Proyek &amp; Berkas</span>
          </button>
          <button
            type="button"
            className={activeSubtab === "integrations" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setActiveSubtab("integrations")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="cpu" size={14} />
            <span>Status Infrastruktur</span>
          </button>
        </div>
      </div>

      {activeSubtab === "approvals" && <ApprovalsFeature />}
      {activeSubtab === "tasks" && <TasksFeature />}
      {activeSubtab === "products" && <ProductsFeature />}
      {activeSubtab === "projects" && <ProjectsFeature />}

      {activeSubtab === "integrations" && (
        <div className="white-panel">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="cpu" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>Status Infrastruktur &amp; Konektor Sistem</h3>
          </div>
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
                icon: "sparkles",
              },
              {
                name: "Database Backend",
                type: "Penyimpanan Transaksional",
                status: "Aktif",
                detail: "Database SQL terintegrasi & migrasi skema alembic selesai",
                icon: "database",
              },
              {
                name: "Web Crawler & Audit Engine",
                type: "SEO & Growth",
                status: "SSRF Guard Aktif",
                detail: "Blokir otomatis IP privat, loopback, dan link-local",
                icon: "globe",
              },
              {
                name: "Human-in-the-Loop Gate",
                type: "Governance & Outbound",
                status: "Wajib Persetujuan",
                detail: "Publikasi & outreach eksternal memerlukan izin pemilik",
                icon: "shield",
              },
            ].map((conn) => (
              <div
                key={conn.name}
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
                  <Icon name={conn.icon} size={18} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 4,
                    }}
                  >
                    <strong style={{ fontSize: "0.88rem" }}>{conn.name}</strong>
                    <span className="badge" data-task="completed">{conn.status}</span>
                  </div>
                  <span
                    style={{
                      fontSize: "0.74rem",
                      color: "var(--text-secondary)",
                      display: "block",
                      marginBottom: 4,
                    }}
                  >
                    {conn.type}
                  </span>
                  <p style={{ margin: 0, fontSize: "0.78rem" }}>{conn.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
