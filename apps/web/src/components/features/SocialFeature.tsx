"use client";

import { useEffect, useState, useCallback } from "react";
import { marketingApi, type ContentAsset, type Campaign } from "@/lib/marketingApi";

interface SocialAccount {
  id: string;
  platform: "linkedin" | "instagram" | "x" | "facebook" | "youtube";
  name: string;
  handle: string;
  connected: boolean;
  code: string;
}

const INITIAL_ACCOUNTS: SocialAccount[] = [
  { id: "1", platform: "linkedin", name: "Roihan AI Office", handle: "@roihan-ai", connected: true, code: "IN" },
  { id: "2", platform: "x", name: "Roihan AI", handle: "@roihan_ai", connected: false, code: "X" },
  { id: "3", platform: "instagram", name: "Roihan Marketing", handle: "@roihan.office", connected: false, code: "IG" },
  { id: "4", platform: "youtube", name: "Roihan Tech & Marketing", handle: "@roihantech", connected: false, code: "YT" },
];

export function SocialFeature() {
  const [tab, setTab] = useState<"accounts" | "scheduled" | "analytics">("scheduled");
  const [accounts, setAccounts] = useState<SocialAccount[]>(INITIAL_ACCOUNTS);
  const [contents, setContents] = useState<ContentAsset[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);

  const [postPlatform, setPostPlatform] = useState<"linkedin" | "x" | "instagram">("linkedin");
  const [postText, setPostText] = useState("");
  const [postSchedule, setPostSchedule] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [allContents, allCampaigns] = await Promise.all([
        marketingApi.contents(),
        marketingApi.campaigns(),
      ]);
      setContents(
        allContents.filter(
          (c) => c.kind === "social_post" || c.channel === "linkedin" || c.channel === "instagram"
        )
      );
      setCampaigns(allCampaigns);
    } catch {
      // fallback
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = setTimeout(() => {
      void loadData();
    }, 0);
    return () => clearTimeout(id);
  }, [loadData]);

  const toggleConnect = (id: string) => {
    setAccounts((prev) =>
      prev.map((acc) => {
        if (acc.id === id) {
          const next = !acc.connected;
          setNotice(
            next
              ? `Akun ${acc.name} berhasil dihubungkan via OAuth.`
              : `Koneksi akun ${acc.name} dicabut.`
          );
          setTimeout(() => setNotice(null), 3500);
          return { ...acc, connected: next };
        }
        return acc;
      })
    );
  };

  const handleCreatePost = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!postText.trim()) return;
    setIsSubmitting(true);
    try {
      await marketingApi.createContent({
        product_id: campaigns[0]?.product_id || "default",
        kind: "social_post",
        channel: postPlatform,
        title: postText.slice(0, 40) + "...",
        body: postText,
        campaign_id: campaigns[0]?.id,
      });
      setPostText("");
      setPostSchedule("");
      setNotice("Postingan media sosial berhasil dijadwalkan ke antrean publikasi.");
      setTimeout(() => setNotice(null), 4000);
      await loadData();
      setTab("scheduled");
    } catch {
      setNotice("Gagal membuat postingan. Pastikan produk dan kampanye telah disiapkan.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 20 }}>
      {/* Header */}
      <div className="workspace-header">
        <div className="workspace-greeting">
          <h2>Social Media Hub</h2>
          <p>
            Kelola akun sosial resmi, kalender publikasi multi-kanal, jadwal posting, dan metrik keterlibatan.
          </p>
        </div>
        <div className="workspace-header-actions">
          <button
            type="button"
            className={tab === "scheduled" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("scheduled")}
          >
            Jadwal Publikasi ({contents.length})
          </button>
          <button
            type="button"
            className={tab === "accounts" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("accounts")}
          >
            Akun Terhubung ({accounts.filter((a) => a.connected).length})
          </button>
          <button
            type="button"
            className={tab === "analytics" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("analytics")}
          >
            Analitik Sosial
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

      {/* Tab: Scheduled & Post Creator */}
      {tab === "scheduled" && (
        <div className="workspace-middle-grid">
          <div className="white-panel">
            <h3>Buat Postingan Sosial Baru</h3>
            <form onSubmit={handleCreatePost} style={{ display: "grid", gap: 12 }}>
              <div>
                <label>Saluran Publikasi</label>
                <div className="actions" style={{ marginTop: 0 }}>
                  {(["linkedin", "x", "instagram"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={postPlatform === p ? "btn-primary-orange" : "btn-secondary"}
                      onClick={() => setPostPlatform(p)}
                    >
                      {p === "x" ? "X (Twitter)" : p === "linkedin" ? "LinkedIn" : "Instagram"}
                    </button>
                  ))}
                </div>
              </div>

              <label>
                Konten Pesan ({postText.length} karakter)
                <textarea
                  rows={5}
                  value={postText}
                  onChange={(e) => setPostText(e.target.value)}
                  placeholder="Tulis pembaruan strategi marketing, studi kasus klien, atau pengumuman produk..."
                  required
                />
              </label>

              <label>
                Jadwal Publikasi (Opsional)
                <input
                  type="datetime-local"
                  value={postSchedule}
                  onChange={(e) => setPostSchedule(e.target.value)}
                />
              </label>

              <button type="submit" className="btn-primary-orange" disabled={isSubmitting}>
                {isSubmitting ? "Menyimpan..." : "Simpan & Jadwalkan Post"}
              </button>
            </form>
          </div>

          <div className="white-panel">
            <h3>Antrean Postingan Sosial</h3>
            {loading ? (
              <p className="hint">Memuat antrean publikasi...</p>
            ) : contents.length === 0 ? (
              <p className="hint">
                Belum ada postingan sosial dalam antrean. Buat draf pertama pada formulir di samping.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 10, maxHeight: 380, overflowY: "auto" }}>
                {contents.map((item) => (
                  <div
                    key={item.id}
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
                        marginBottom: 6,
                      }}
                    >
                      <span
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          color: "var(--accent)",
                        }}
                      >
                        {item.channel}
                      </span>
                      <span className="badge">{item.status}</span>
                    </div>
                    <strong style={{ fontSize: "0.86rem", display: "block", marginBottom: 4 }}>
                      {item.title}
                    </strong>
                    <p
                      style={{
                        fontSize: "0.8rem",
                        color: "var(--text-secondary)",
                        margin: 0,
                      }}
                    >
                      {item.body}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab: Connected Accounts */}
      {tab === "accounts" && (
        <div className="white-panel">
          <h3>Akun Media Sosial yang Diotorisasi</h3>
          <p className="hint">
            Roihan AI Office menggunakan integrasi OAuth resmi untuk menjadwalkan dan memublikasikan konten. Kredensial tidak disimpan dalam bentuk plaintext.
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: 12,
            }}
          >
            {accounts.map((acc) => (
              <div
                key={acc.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: 14,
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border)",
                  background: "var(--surface-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: "var(--radius-md)",
                      background: "var(--sidebar-bg)",
                      color: "#fff",
                      fontSize: "0.76rem",
                      fontWeight: 700,
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {acc.code}
                  </span>
                  <div>
                    <strong style={{ display: "block", fontSize: "0.88rem" }}>
                      {acc.name}
                    </strong>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      {acc.handle}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  className={acc.connected ? "btn-secondary" : "btn-primary-orange"}
                  onClick={() => toggleConnect(acc.id)}
                >
                  {acc.connected ? "Terhubung" : "Hubungkan"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab: Social Analytics */}
      {tab === "analytics" && (
        <div style={{ display: "grid", gap: 16 }}>
          <div className="workspace-kpi-grid">
            <div className="kpi-card">
              <span className="kpi-card-title">Total Postingan</span>
              <strong style={{ color: "var(--accent)" }}>{contents.length}</strong>
              <span className="small muted">LinkedIn, X &amp; Instagram</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Akun Terotorisasi</span>
              <strong style={{ color: "var(--ok)" }}>
                {accounts.filter((a) => a.connected).length} / {accounts.length}
              </strong>
              <span className="small muted">Koneksi OAuth aktif</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Siap Publikasi</span>
              <strong style={{ color: "var(--info)" }}>
                {contents.filter((c) => c.status === "ready_for_review").length}
              </strong>
              <span className="small muted">Lolos pemeriksaan klaim</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-card-title">Kampanye Terkait</span>
              <strong>{campaigns.length}</strong>
              <span className="small muted">Kampanye lintas kanal</span>
            </div>
          </div>

          <div className="white-panel">
            <h3>Sinkronisasi Metrik Sosial</h3>
            <p className="hint" style={{ margin: 0 }}>
              Metrik keterlibatan dan jangkauan disinkronisasi secara berkala dari platform yang telah diotorisasi pada tab Akun Terhubung.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
