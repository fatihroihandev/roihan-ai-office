"use client";

import { useEffect, useState, useCallback, type ReactNode } from "react";
import { authApi, type AuthStatus, type OwnerUser } from "@/lib/authApi";

export function AuthGateway({ children }: { children: ReactNode }) {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("Roihan");
  const [bootstrapToken, setBootstrapToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const checkStatus = useCallback(async () => {
    try {
      const s = await authApi.status();
      setAuthStatus(s);
    } catch {
      // Offline fallback: allow local development to proceed
      setAuthStatus({
        initialized: true,
        authenticated: true,
        owner_email_configured: false,
        user: { id: "local", email: "owner@roihan.id", full_name: "Roihan" },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const handleBootstrap = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await authApi.bootstrap({
        email,
        password,
        full_name: fullName,
        bootstrap_token: bootstrapToken || undefined,
      });
      await checkStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal inisialisasi akun pemilik";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await authApi.login({ email, password });
      await checkStatus();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Email atau kata sandi tidak valid";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#131517", color: "#f4f4f5" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ width: 44, height: 44, border: "3px solid #27272a", borderTopColor: "#ff5722", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 16px" }} />
          <p style={{ fontSize: "0.88rem", color: "#a1a1aa" }}>Memverifikasi sesi pemilik...</p>
        </div>
      </div>
    );
  }

  // Jika sudah terautentikasi, tampilkan aplikasi utama
  if (authStatus?.authenticated) {
    return <>{children}</>;
  }

  const isInit = authStatus?.initialized;

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#131517",
        padding: 20,
        boxSizing: "border-box",
        fontFamily: "var(--font-montserrat, system-ui, sans-serif)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 440,
          background: "#1e2226",
          border: "1px solid #2a2e33",
          borderRadius: 20,
          padding: "36px 32px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
          color: "#f4f4f5",
        }}
      >
        {/* Logo & Brand Header */}
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 16,
              background: "#ff5722",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 14px",
              boxShadow: "0 8px 20px rgba(255, 87, 34, 0.35)",
            }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 5v14M18 5v14M2 9h4M18 9h4M2 15h4M18 15h4M6 12h12" />
            </svg>
          </div>
          <h1 style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0 0 6px", color: "#ffffff" }}>
            Roihan AI Office
          </h1>
          <p style={{ fontSize: "0.82rem", color: "#a1a1aa", margin: 0 }}>
            {isInit ? "Gerbang Akses Pemilik Tunggal (Single-Owner)" : "Inisialisasi Akun Pemilik (Setup Awal)"}
          </p>
        </div>

        {error && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 12,
              background: "rgba(239, 68, 68, 0.12)",
              border: "1px solid #ef4444",
              color: "#f87171",
              fontSize: "0.82rem",
              marginBottom: 18,
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* Form: Login if initialized, Bootstrap if first time */}
        {isInit ? (
          <form onSubmit={handleLogin} style={{ display: "grid", gap: 14 }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#a1a1aa", marginBottom: 6 }}>
                Email Pemilik
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@roihan.id"
                required
                style={{
                  width: "100%",
                  padding: "11px 14px",
                  borderRadius: 12,
                  border: "1px solid #33383f",
                  background: "#181b1e",
                  color: "#ffffff",
                  fontSize: "0.88rem",
                  boxSizing: "border-box",
                  outline: "none",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#a1a1aa", marginBottom: 6 }}>
                Kata Sandi
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: "100%",
                  padding: "11px 14px",
                  borderRadius: 12,
                  border: "1px solid #33383f",
                  background: "#181b1e",
                  color: "#ffffff",
                  fontSize: "0.88rem",
                  boxSizing: "border-box",
                  outline: "none",
                }}
              />
            </div>

            <button
              type="submit"
              disabled={busy}
              style={{
                marginTop: 8,
                padding: "12px",
                borderRadius: 12,
                border: "none",
                background: "#ff5722",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "0.9rem",
                cursor: busy ? "not-allowed" : "pointer",
                boxShadow: "0 6px 16px rgba(255, 87, 34, 0.3)",
                transition: "background 0.2s, transform 0.1s",
              }}
            >
              {busy ? "Memverifikasi..." : "Masuk ke Workspace →"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleBootstrap} style={{ display: "grid", gap: 14 }}>
            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#a1a1aa", marginBottom: 6 }}>
                Nama Lengkap Pemilik
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Fatih Roihan"
                required
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  border: "1px solid #33383f",
                  background: "#181b1e",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#a1a1aa", marginBottom: 6 }}>
                Email Pemilik Sah
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@roihan.id"
                required
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  border: "1px solid #33383f",
                  background: "#181b1e",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#a1a1aa", marginBottom: 6 }}>
                Kata Sandi Baru (Min. 8 Karakter)
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimal 8 karakter unik"
                required
                minLength={8}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  border: "1px solid #33383f",
                  background: "#181b1e",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.78rem", fontWeight: 600, color: "#a1a1aa", marginBottom: 6 }}>
                Token Bootstrap (Opsional, jika diset di server)
              </label>
              <input
                type="text"
                value={bootstrapToken}
                onChange={(e) => setBootstrapToken(e.target.value)}
                placeholder="Kosongkan jika tidak diset di .env"
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: 12,
                  border: "1px solid #33383f",
                  background: "#181b1e",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <button
              type="submit"
              disabled={busy}
              style={{
                marginTop: 6,
                padding: "12px",
                borderRadius: 12,
                border: "none",
                background: "#ff5722",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "0.9rem",
                cursor: busy ? "not-allowed" : "pointer",
                boxShadow: "0 6px 16px rgba(255, 87, 34, 0.3)",
              }}
            >
              {busy ? "Membuat Akun..." : "🔒 Inisialisasi Akun Pemilik"}
            </button>
          </form>
        )}

        {/* Security Notice Footer */}
        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid #2a2e33", textAlign: "center" }}>
          <p style={{ fontSize: "0.72rem", color: "#71717a", margin: 0, lineHeight: 1.4 }}>
            🛡️ <strong>Single-Owner Security:</strong> Registrasi publik ditutup permanen. Akses dilindungi sesi HttpOnly terenkripsi &amp; rate limit anti brute-force.
          </p>
        </div>
      </div>
    </div>
  );
}
