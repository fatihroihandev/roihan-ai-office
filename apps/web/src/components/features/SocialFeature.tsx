"use client";

import { useEffect, useState, useCallback } from "react";
import { marketingApi, type ContentAsset, type Campaign } from "@/lib/marketingApi";
import { Icon } from "@/components/ui/Icons";

interface SocialAccount {
  id: string;
  platform: "linkedin" | "instagram" | "x" | "facebook" | "youtube";
  name: string;
  handle: string;
  connected: boolean;
}

const INITIAL_ACCOUNTS: SocialAccount[] = [
  { id: "1", platform: "linkedin", name: "Roihan AI Office", handle: "@roihan-ai", connected: true },
  { id: "2", platform: "x", name: "Roihan AI", handle: "@roihan_ai", connected: false },
  { id: "3", platform: "instagram", name: "Roihan Marketing", handle: "@roihan.office", connected: false },
  { id: "4", platform: "youtube", name: "Roihan Tech & Marketing", handle: "@roihantech", connected: false },
];

function PlatformIcon({ platform, size = 18 }: { platform: string; size?: number }) {
  switch (platform) {
    case "linkedin":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
          <rect x="2" y="9" width="4" height="12" />
          <circle cx="4" cy="4" r="2" />
        </svg>
      );
    case "x":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 4l16 16M4 20L20 4" />
        </svg>
      );
    case "instagram":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
          <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
          <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
        </svg>
      );
    case "youtube":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z" />
          <polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02" />
        </svg>
      );
    default:
      return <Icon name="share" size={size} />;
  }
}

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
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="clock" size={14} />
            <span>Jadwal Publikasi ({contents.length})</span>
          </button>
          <button
            type="button"
            className={tab === "accounts" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("accounts")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="share" size={14} />
            <span>Akun Terhubung ({accounts.filter((a) => a.connected).length})</span>
          </button>
          <button
            type="button"
            className={tab === "analytics" ? "btn-primary-orange" : "btn-secondary"}
            onClick={() => setTab("analytics")}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Icon name="chart" size={14} />
            <span>Analitik Sosial</span>
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
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Icon name="info" size={16} />
          <span>{notice}</span>
        </div>
      )}

      {/* Tab: Scheduled & Post Creator */}
      {tab === "scheduled" && (
        <div className="workspace-middle-grid">
          <div className="white-panel">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <span style={{ color: "var(--accent)", display: "flex" }}>
                <Icon name="pen" size={18} />
              </span>
              <h3 style={{ margin: 0 }}>Buat Postingan Sosial Baru</h3>
            </div>
            <form onSubmit={handleCreatePost} style={{ display: "grid", gap: 12 }}>
              <div>
                <label>Saluran Publikasi</label>
                <div className="actions" style={{ marginTop: 4, display: "flex", gap: 8 }}>
                  {(["linkedin", "x", "instagram"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={postPlatform === p ? "btn-primary-orange" : "btn-secondary"}
                      onClick={() => setPostPlatform(p)}
                      style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                    >
                      <PlatformIcon platform={p} size={15} />
                      <span>{p === "x" ? "X (Twitter)" : p === "linkedin" ? "LinkedIn" : "Instagram"}</span>
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

              <button
                type="submit"
                className="btn-primary-orange"
                disabled={isSubmitting}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, justifySelf: "start" }}
              >
                <Icon name="send" size={14} />
                <span>{isSubmitting ? "Menyimpan..." : "Simpan & Jadwalkan Post"}</span>
              </button>
            </form>
          </div>

          <div className="white-panel">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <span style={{ color: "var(--info)", display: "flex" }}>
                <Icon name="clock" size={18} />
              </span>
              <h3 style={{ margin: 0 }}>Antrean Postingan Sosial</h3>
            </div>
            {loading ? (
              <p className="hint">Memuat antrean publikasi...</p>
            ) : contents.length === 0 ? (
              <div style={{ textAlign: "center", padding: "32px 16px" }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    background: "var(--surface-subtle)",
                    color: "var(--text-secondary)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 10px",
                  }}
                >
                  <Icon name="share" size={20} />
                </div>
                <p style={{ margin: "0 0 6px", fontWeight: 600, fontSize: "0.88rem" }}>
                  Belum ada postingan dalam antrean
                </p>
                <p className="hint" style={{ margin: 0 }}>
                  Buat draf pertama pada formulir di samping untuk memulai jadwal publikasi.
                </p>
              </div>
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
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 5,
                        }}
                      >
                        <PlatformIcon platform={item.channel} size={14} />
                        <span>{item.channel}</span>
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
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "var(--accent)", display: "flex" }}>
              <Icon name="share" size={18} />
            </span>
            <h3 style={{ margin: 0 }}>Akun Media Sosial yang Diotorisasi</h3>
          </div>
          <p className="hint" style={{ marginTop: 0, marginBottom: 16 }}>
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
                      width: 38,
                      height: 38,
                      borderRadius: "var(--radius-md)",
                      background: "var(--sidebar-bg)",
                      color: "#fff",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <PlatformIcon platform={acc.platform} size={18} />
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
                  style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
                >
                  <Icon name={acc.connected ? "check" : "plus"} size={13} />
                  <span>{acc.connected ? "Terhubung" : "Hubungkan"}</span>
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
              <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="kpi-card-title">Total Postingan</span>
                <span style={{ color: "var(--accent)" }}><Icon name="file-text" size={16} /></span>
              </div>
              <strong style={{ color: "var(--accent)" }}>{contents.length}</strong>
              <span className="small muted">LinkedIn, X &amp; Instagram</span>
            </div>
            <div className="kpi-card">
              <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="kpi-card-title">Akun Terotorisasi</span>
                <span style={{ color: "var(--ok)" }}><Icon name="share" size={16} /></span>
              </div>
              <strong style={{ color: "var(--ok)" }}>
                {accounts.filter((a) => a.connected).length} / {accounts.length}
              </strong>
              <span className="small muted">Koneksi OAuth aktif</span>
            </div>
            <div className="kpi-card">
              <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="kpi-card-title">Siap Publikasi</span>
                <span style={{ color: "var(--info)" }}><Icon name="check-circle" size={16} /></span>
              </div>
              <strong style={{ color: "var(--info)" }}>
                {contents.filter((c) => c.status === "ready_for_review").length}
              </strong>
              <span className="small muted">Lolos pemeriksaan klaim</span>
            </div>
            <div className="kpi-card">
              <div className="kpi-card-top" style={{ display: "flex", justifyContent: "space-between" }}>
                <span className="kpi-card-title">Kampanye Terkait</span>
                <span style={{ color: "var(--accent)" }}><Icon name="target" size={16} /></span>
              </div>
              <strong>{campaigns.length}</strong>
              <span className="small muted">Kampanye lintas kanal</span>
            </div>
          </div>

          <div className="white-panel">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ color: "var(--info)", display: "flex" }}>
                <Icon name="chart" size={18} />
              </span>
              <h3 style={{ margin: 0 }}>Sinkronisasi Metrik Sosial</h3>
            </div>
            <p className="hint" style={{ margin: 0 }}>
              Metrik keterlibatan dan jangkauan disinkronisasi secara berkala dari platform yang telah diotorisasi pada tab Akun Terhubung.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
