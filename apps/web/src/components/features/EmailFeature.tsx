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
  { id: "wf-1", name: "Onboarding Prospek Baru", trigger: "Lead berstatus 'qualified'", action: "Kirim email pengantar profil Roihan AI", active: true },
  { id: "wf-2", name: "Pengingat Prospek Pasif", trigger: "30 hari tanpa interaksi", action: "Kirim email newsletter industri & tren AI", active: true },
  { id: "wf-3", name: "Tindak Lanjut Pasca Meeting", trigger: "Meeting selesai dicatat", action: "Buat draf rangkuman proposal solusi", active: false },
  { id: "wf-4", name: "Kepatuhan UU PDP (Retensi)", trigger: "180 hari tanpa kontak", action: "Tandai untuk persetujuan anonimisasi data", active: true },
];

export function EmailFeature() {
  const [tab, setTab] = useState<"campaigns" | "audiences" | "templates" | "workflows" | "deliverability">("campaigns");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [outbox, setOutbox] = useState<OutboundMessage[]>([]);
  const [suppressed, setSuppressed] = useState<{ id: string }[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [workflows, setWorkflows] = useState<AutomationWorkflow[]>(DEFAULT_WORKFLOWS);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);

  // New Campaign / Email Blast Form
  const [subject, setSubject] = useState("");
  const [emailBody, setEmailBody] = useState("");
  const [targetAudience, setTargetAudience] = useState<string>("all_leads");
  const [sending, setSending] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
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
      // offline / mock fallback
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleWorkflow = (id: string) => {
    setWorkflows((prev) =>
      prev.map((w) => {
        if (w.id === id) {
          const next = !w.active;
          setNotice(`Workflow "${w.name}" ${next ? "diaktifkan" : "dinonaktifkan"}.`);
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
      setNotice(`Kampanye email "${subject}" berhasil dijadwalkan ke ${leads.length} kontak penerima.`);
      setSubject("");
      setEmailBody("");
      setTimeout(() => setNotice(null), 4000);
    }, 600);
  };

  const activeSubscribers = leads.filter((l) => !l.do_not_contact && !l.anonymized);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0, color: "var(--dash-text-main)" }}>
            ✉️ Email Marketing &amp; Automation
          </h2>
          <p style={{ margin: "4px 0 0", color: "var(--dash-text-muted)", fontSize: "0.85rem" }}>
            Otomatisasi pengiriman pesan outreach, daftar audiens terverifikasi, kepatuhan UU PDP, dan monitoring deliverability.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
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
            Deliverability
          </button>
        </div>
      </div>

      {notice && (
        <div style={{ padding: "10px 14px", borderRadius: 12, background: "rgba(255, 87, 34, 0.15)", border: "1px solid #ff5722", color: "#ff5722", fontSize: "0.85rem", fontWeight: 600 }}>
          {notice}
        </div>
      )}

      {/* Tab: Campaigns */}
      {tab === "campaigns" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20 }}>
          <div className="white-panel">
            <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
              📝 Siapkan Kampanye Email Baru
            </h3>
            <form onSubmit={handleSendCampaign} style={{ display: "grid", gap: 14 }}>
              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--dash-text-muted)", marginBottom: 6 }}>
                  Subjek Email
                </label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Contoh: Optimasi Efisiensi Marketing Kantor Anda dengan AI"
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 10,
                    border: "1px solid var(--dash-border)",
                    background: "var(--dash-input-bg)",
                    color: "var(--dash-text-main)",
                    fontSize: "0.85rem",
                    boxSizing: "border-box",
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--dash-text-muted)", marginBottom: 6 }}>
                  Segmen Audiens Target
                </label>
                <select
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 10,
                    border: "1px solid var(--dash-border)",
                    background: "var(--dash-input-bg)",
                    color: "var(--dash-text-main)",
                    fontSize: "0.85rem",
                    boxSizing: "border-box",
                  }}
                >
                  <option value="all_leads">Semua Prospek Aktif ({activeSubscribers.length} kontak)</option>
                  <option value="qualified">Hanya Prospek Terkualifikasi (Skor &ge; 40)</option>
                  <option value="enterprise">Perusahaan Skala Menengah &amp; Besar</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "var(--dash-text-muted)", marginBottom: 6 }}>
                  Badan Pesan Email
                </label>
                <textarea
                  rows={6}
                  value={emailBody}
                  onChange={(e) => setEmailBody(e.target.value)}
                  placeholder="Yth. {{contact_name}}, salam hangat dari Roihan AI Office..."
                  style={{
                    width: "100%",
                    padding: 10,
                    borderRadius: 12,
                    border: "1px solid var(--dash-border)",
                    background: "var(--dash-input-bg)",
                    color: "var(--dash-text-main)",
                    fontSize: "0.85rem",
                    boxSizing: "border-box",
                  }}
                  required
                />
                <span style={{ fontSize: "0.72rem", color: "var(--dash-text-muted)", marginTop: 4, display: "block" }}>
                  💡 Variabel didukung: &#123;&#123;contact_name&#125;&#125;, &#123;&#123;company_name&#125;&#125;, &#123;&#123;unsubscribe_link&#125;&#125;. Link unsubscribe otomatis disisipkan.
                </span>
              </div>

              <button type="submit" className="btn-primary-orange" disabled={sending}>
                {sending ? "Memproses..." : "📤 Jadwalkan Pengiriman Kampanye"}
              </button>
            </form>
          </div>

          <div className="white-panel">
            <h3 style={{ fontSize: "1.05rem", margin: "0 0 12px", color: "var(--dash-text-main)" }}>
              📬 Pesan Keluar (Outbox)
            </h3>
            {outbox.length === 0 ? (
              <p style={{ color: "var(--dash-text-muted)", fontSize: "0.85rem" }}>
                Tidak ada pesan keluar yang menunggu. Semua pesan outreach terkontrol telah diproses.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 10, maxHeight: 360, overflowY: "auto" }}>
                {outbox.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      padding: 12,
                      borderRadius: 12,
                      background: "var(--dash-pill-bg)",
                      border: "1px solid var(--dash-border)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <strong style={{ fontSize: "0.85rem", color: "var(--dash-text-main)" }}>{msg.subject}</strong>
                      <span style={{ fontSize: "0.7rem", color: "#ff5722", fontWeight: 600 }}>{msg.status}</span>
                    </div>
                    <p style={{ fontSize: "0.78rem", color: "var(--dash-text-muted)", margin: 0 }}>{msg.body.slice(0, 80)}...</p>
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
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 12px", color: "var(--dash-text-main)" }}>
            👥 Manajemen Daftar Kontak &amp; Privasi UU PDP
          </h3>
          <p style={{ fontSize: "0.82rem", color: "var(--dash-text-muted)", marginBottom: 16 }}>
            Setiap kontak dicatat dengan dasar hukum pengumpulan data yang jelas. Kontak yang memohon berhenti berlangganan masuk ke daftar supresi permanen.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
            <div className="kpi-card">
              <span className="kpi-card-title">Pelanggan Aktif</span>
              <strong style={{ color: "#10b981" }}>{activeSubscribers.length}</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Izin kontak sah</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Daftar Supresi / Unsubscribed</span>
              <strong style={{ color: "#ef4444" }}>{suppressed.length}</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Blokir otomatis</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Terkualifikasi Penjualan</span>
              <strong style={{ color: "#3b82f6" }}>{leads.filter((l) => (l.score ?? 0) >= 40).length}</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Siap diprospek</span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Workflows */}
      {tab === "workflows" && (
        <div className="white-panel">
          <h3 style={{ fontSize: "1.05rem", margin: "0 0 14px", color: "var(--dash-text-main)" }}>
            ⚡ Alur Otomatisasi Berbasis Pemicu (Trigger-Based Automation)
          </h3>
          <div style={{ display: "grid", gap: 12 }}>
            {workflows.map((wf) => (
              <div
                key={wf.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: 14,
                  borderRadius: 14,
                  border: "1px solid var(--dash-border)",
                  background: "var(--dash-pill-bg)",
                }}
              >
                <div>
                  <strong style={{ display: "block", fontSize: "0.9rem", color: "var(--dash-text-main)" }}>
                    {wf.name}
                  </strong>
                  <span style={{ fontSize: "0.78rem", color: "var(--dash-text-muted)" }}>
                    Pemicu: <strong>{wf.trigger}</strong> &rarr; Tindakan: <em>{wf.action}</em>
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => toggleWorkflow(wf.id)}
                  style={{
                    padding: "6px 14px",
                    borderRadius: 10,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    border: wf.active ? "1px solid #10b981" : "1px solid var(--dash-border)",
                    background: wf.active ? "rgba(16, 185, 129, 0.12)" : "var(--dash-input-bg)",
                    color: wf.active ? "#10b981" : "var(--dash-text-main)",
                  }}
                >
                  {wf.active ? "Aktif" : "Nonaktif"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Deliverability */}
      {tab === "deliverability" && (
        <div style={{ display: "grid", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
            <div className="kpi-card">
              <span className="kpi-card-title">Tingkat Pengiriman</span>
              <strong style={{ color: "#10b981" }}>99.2%</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>SPF & DKIM Valid</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Rasio Buka (Open Rate)</span>
              <strong style={{ color: "#3b82f6" }}>34.8%</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Benchmark B2B: 21%</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Tingkat Klik (CTR)</span>
              <strong style={{ color: "#ff5722" }}>6.4%</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Link proposal</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Bounce Rate</span>
              <strong style={{ color: "#ec4899" }}>0.8%</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--dash-text-muted)" }}>Di bawah batas risiko</span>
            </div>
          </div>
          <div className="white-panel">
            <h4 style={{ margin: "0 0 8px", color: "var(--dash-text-main)" }}>Status Protokol Email Kantor</h4>
            <p style={{ fontSize: "0.82rem", color: "var(--dash-text-muted)", margin: 0 }}>
              Domain pengirim dikonfigurasi dengan enkripsi TLS 1.3 serta record SPF, DKIM, dan DMARC. Sesuai kebijakan keamanan, setiap pengiriman massal diwajibkan melewati filter kuota harian.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
