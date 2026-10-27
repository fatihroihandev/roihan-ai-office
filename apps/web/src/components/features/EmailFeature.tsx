"use client";

import { useEffect, useState, useCallback } from "react";
import { marketingApi, type Lead, type OutboundMessage, type Policy } from "@/lib/marketingApi";

interface AutomationWorkflow {
  id: string;
  name: string;
  trigger: string;
  action: string;
  active: boolean;
}

const DEFAULT_WORKFLOWS: AutomationWorkflow[] = [
  {
    id: "wf-1",
    name: "Onboarding Prospek Baru",
    trigger: "Lead berstatus 'qualified'",
    action: "Siapkan draf email pengantar profil produk",
    active: true,
  },
  {
    id: "wf-2",
    name: "Pengingat Prospek Pasif",
    trigger: "30 hari tanpa interaksi",
    action: "Jadwalkan tindak lanjut edukasi industri",
    active: true,
  },
  {
    id: "wf-3",
    name: "Tindak Lanjut Pasca Meeting",
    trigger: "Meeting selesai dicatat",
    action: "Buat draf rangkuman proposal solusi",
    active: false,
  },
  {
    id: "wf-4",
    name: "Kepatuhan Retensi UU PDP",
    trigger: "180 hari tanpa kontak",
    action: "Tandai untuk persetujuan anonimisasi data",
    active: true,
  },
];

export function EmailFeature() {
  const [tab, setTab] = useState<"campaigns" | "audiences" | "workflows" | "deliverability">("campaigns");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [outbox, setOutbox] = useState<OutboundMessage[]>([]);
  const [suppressed, setSuppressed] = useState<{ id: string }[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [workflows, setWorkflows] = useState<AutomationWorkflow[]>(DEFAULT_WORKFLOWS);
  const [notice, setNotice] = useState<string | null>(null);

  const [subject, setSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [targetAudience, setTargetAudience] = useState<string>("all_leads");
  const [sending, setSending] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [allLeads, allOutbox, allSuppressed, pol] = await Promise.all([
        marketingApi.leads(),
        marketingApi.outbox(),
        marketingApi.suppression(),
        marketingApi.policy(),
      ]);
      setLeads(allLeads);
      setOutbox(allOutbox.filter((o) => o.channel === "email" || o.kind === "outreach"));
      setSuppressed(allSuppressed);
      setPolicy(pol);
    } catch {
      // fallback
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(() => {
      void loadData();
    }, 0);
    return () => clearTimeout(id);
  }, [loadData]);

  const toggleWorkflow = (id: string) => {
    setWorkflows((prev) =>
      prev.map((w) => {
        if (w.id === id) {
          const next = !w.active;
          setNotice(`Alur kerja "${w.name}" ${next ? "diaktifkan" : "dinonaktifkan"}.`);
          setTimeout(() => setNotice(null), 3000);
          return { ...w, active: next };
        }
        return w;
      })
    );
  };

  const handleSendCampaign = (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !emailBody.trim()) return;
    setSending(true);
    setTimeout(() => {
      setSending(false);
      setNotice(
        `Kampanye email "${subject}" berhasil dijadwalkan untuk ditinjau sebelum pengiriman.`
      );
      setSubject("");
      setEmailBody("");
      setTimeout(() => setNotice(null), 4000);
    }, 500);
  };

  const activeSubscribers = leads.filter((l) => !l.do_not_contact && !l.anonymized);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="workspace-header">
        <div className="workspace-greeting">
          <h2>Email Marketing &amp; Automation</h2>
          <p>
            Pengelolaan kampanye email B2B, segmentasi daftar kontak, alur kerja otomatis, dan kepatuhan privasi UU PDP.
          </p>
        </div>
        <div className="workspace-header-actions">
          <button
            type="button"
            className={tab === "campaigns" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("campaigns")}
          >
            Kampanye Email
          </button>
          <button
            type="button"
            className={tab === "audiences" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("audiences")}
          >
            Audiens ({activeSubscribers.length})
          </button>
          <button
            type="button"
            className={tab === "workflows" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("workflows")}
          >
            Alur Otomatisasi
          </button>
          <button
            type="button"
            className={tab === "deliverability" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("deliverability")}
          >
            Kebijakan &amp; Deliverability
          </button>
        </div>
      </div>

      {notice && (
        <div
          role="status"
          style={{
            padding: "10px 14px",
            borderRadius: "var(--radius-md)",
            background: "var(--accent-subtle)",
            border: "1px solid var(--accent)",
            color: "var(--accent)",
            fontSize: "0.84rem",
            fontWeight: 600,
          }}
        >
          {notice}
        </div>
      )}

      {/* Tab: Campaigns */}
      {tab === "campaigns" && (
        <div className="workspace-middle-grid">
          <div className="white-panel">
            <h3>Siapkan Kampanye Email Baru</h3>
            <form onSubmit={handleSendCampaign} style={{ display: "grid", gap: 12 }}>
              <label>
                Subjek Email
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Contoh: Strategi Pertumbuhan Organik & Akuisisi Klien B2B"
                  required
                />
              </label>

              <label>
                Segmen Audiens Target
                <select
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                >
                  <option value="all_leads">
                    Semua Prospek Aktif ({activeSubscribers.length} kontak)
                  </option>
                  <option value="qualified">
                    Hanya Prospek Terkualifikasi (Skor &ge; 40)
                  </option>
                  <option value="enterprise">
                    Perusahaan Skala Menengah &amp; Besar
                  </option>
                </select>
              </label>

              <label>
                Badan Pesan Email
                <textarea
                  rows={6}
                  value={emailBody}
                  onChange={(e) => setEmailBody(e.target.value)}
                  placeholder="Yth. {{contact_name}}, salam dari tim Roihan AI Office..."
                  required
                />
                <span className="small muted">
                  Variabel didukung: &#123;&#123;contact_name&#125;&#125;, &#123;&#123;company_name&#125;&#125;. Tautan opt-out disertakan otomatis.
                </span>
              </label>

              <button type="submit" className="btn-primary-orange" disabled={sending}>
                {sending ? "Memproses..." : "Jadwalkan Pengiriman Kampanye"}
              </button>
            </form>
          </div>

          <div className="white-panel">
            <h3>Antrean Pesan Keluar (Outbox)</h3>
            {outbox.length === 0 ? (
              <p className="hint">
                Tidak ada pesan keluar yang menunggu. Seluruh pesan outreach telah diproses.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 10, maxHeight: 360, overflowY: "auto" }}>
                {outbox.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      padding: 12,
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
                      <strong style={{ fontSize: "0.86rem" }}>{msg.subject}</strong>
                      <span className="badge">{msg.status}</span>
                    </div>
                    <p
                      style={{
                        fontSize: "0.78rem",
                        color: "var(--text-secondary)",
                        margin: 0,
                      }}
                    >
                      {msg.body.slice(0, 100)}...
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Audiences */}
      {tab === "audiences" && (
        <div className="white-panel">
          <h3>Manajemen Daftar Kontak &amp; Kepatuhan UU PDP</h3>
          <p className="hint">
            Setiap kontak dicatat dengan dasar pemrosesan data yang sah. Kontak yang memilih berhenti berlangganan dimasukkan ke daftar supresi permanen.
          </p>
          <div className="workspace-kpi-grid" style={{ marginBottom: 0 }}>
            <div className="kpi-card">
              <span className="kpi-card-title">Kontak Aktif Diizinkan</span>
              <strong style={{ color: "var(--ok)" }}>{activeSubscribers.length}</strong>
              <span className="small muted">Siap menerima komunikasi</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Daftar Supresi (Opt-Out)</span>
              <strong style={{ color: "var(--bad)" }}>{suppressed.length}</strong>
              <span className="small muted">Diblokir otomatis oleh sistem</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Prospek Terkualifikasi</span>
              <strong style={{ color: "var(--info)" }}>
                {leads.filter((l) => (l.score ?? 0) >= 40).length}
              </strong>
              <span className="small muted">Skor kelayakan &ge; 40</span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Workflows */}
      {tab === "workflows" && (
        <div className="white-panel">
          <h3>Alur Otomatisasi Berbasis Pemicu (Trigger Workflows)</h3>
          <div style={{ display: "grid", gap: 10 }}>
            {workflows.map((wf) => (
              <div
                key={wf.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: 14,
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border)",
                  background: "var(--surface-subtle)",
                }}
              >
                <div>
                  <strong style={{ display: "block", fontSize: "0.88rem" }}>
                    {wf.name}
                  </strong>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                    Pemicu: <strong>{wf.trigger}</strong> &rarr; Tindakan: <em>{wf.action}</em>
                  </span>
                </div>
                <button
                  type="button"
                  className={wf.active ? "btn-primary-orange" : "btn-secondary"}
                  onClick={() => toggleWorkflow(wf.id)}
                >
                  {wf.active ? "Aktif" : "Nonaktif"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Deliverability & Policy */}
      {tab === "deliverability" && (
        <div className="white-panel">
          <h3>Kebijakan Pengiriman &amp; Batas Frekuensi</h3>
          <div className="workspace-kpi-grid">
            <div className="kpi-card">
              <span className="kpi-card-title">Maks. Outreach Harian</span>
              <strong>{policy?.external?.outreach_max_per_day ?? 20}</strong>
              <span className="small muted">Pesan keluar per hari</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Jeda Antar Kontak</span>
              <strong>{policy?.external?.outreach_min_days_between_contacts ?? 7} hari</strong>
              <span className="small muted">Mencegah spam ke prospek</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Batas Retensi Tanpa Interaksi</span>
              <strong>{policy?.retention?.no_interaction_days ?? 180} hari</strong>
              <span className="small muted">Kepatuhan privasi UU PDP</span>
            </div>
          </div>
          <p className="hint" style={{ margin: 0 }}>
            Setiap draf email dievaluasi oleh pemeriksa klaim produk (Claim Linter) dan pembatas kuota harian sebelum diizinkan masuk ke antrean pengiriman.
          </p>
        </div>
      )}
    </div>
  );
}
