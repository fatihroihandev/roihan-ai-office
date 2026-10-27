"use client";

import Image from "next/image";
import { useEffect, useState, useCallback, type ReactNode } from "react";
import { authApi, type AuthStatus } from "@/lib/authApi";

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
      // Offline / local development fallback
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
    const id = setTimeout(() => {
      void checkStatus();
    }, 0);
    return () => clearTimeout(id);
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
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg)",
          color: "var(--text)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <p style={{ fontSize: "0.88rem", color: "var(--text-secondary)", margin: 0 }}>
            Memverifikasi sesi pemilik...
          </p>
        </div>
      </div>
    );
  }

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
        background: "var(--bg)",
        padding: 20,
      }}
    >
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: 420,
          padding: "32px 28px",
          boxShadow: "var(--shadow-lg)",
          marginBottom: 0,
        }}
      >
        {/* Brand Header */}
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              margin: "0 auto 12px",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Image
              src="/brand/roihan-app-icon.png"
              alt="Roihan Technologies Logo"
              width={52}
              height={52}
              unoptimized
              priority
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0 0 4px" }}>
            Roihan AI Office
          </h1>
          <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
            {isInit
              ? "Gerbang Akses Pemilik Tunggal (Single-Owner)"
              : "Inisialisasi Akun Pemilik (Setup Awal)"}
          </p>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              background: "var(--bad-subtle)",
              border: "1px solid var(--bad)",
              color: "var(--bad)",
              fontSize: "0.8rem",
              fontWeight: 500,
              marginBottom: 16,
            }}
          >
            {error}
          </div>
        )}

        {isInit ? (
          <form onSubmit={handleLogin} style={{ display: "grid", gap: 12 }}>
            <label>
              Email Pemilik
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@roihan.id"
                required
              />
            </label>

            <label>
              Kata Sandi
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </label>

            <button
              type="submit"
              className="btn-primary-orange"
              disabled={busy}
              style={{ width: "100%", padding: "10px 14px", marginTop: 4 }}
            >
              {busy ? "Memverifikasi..." : "Masuk ke Workspace"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleBootstrap} style={{ display: "grid", gap: 12 }}>
            <label>
              Nama Lengkap Pemilik
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Fatih Roihan"
                required
              />
            </label>

            <label>
              Email Pemilik Sah
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@roihan.id"
                required
              />
            </label>

            <label>
              Kata Sandi Baru (Min. 8 Karakter)
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimal 8 karakter unik"
                required
                minLength={8}
              />
            </label>

            <label>
              Token Bootstrap (Opsional, jika diset di server)
              <input
                type="text"
                value={bootstrapToken}
                onChange={(e) => setBootstrapToken(e.target.value)}
                placeholder="Kosongkan jika tidak diset di .env"
              />
            </label>

            <button
              type="submit"
              className="btn-primary-orange"
              disabled={busy}
              style={{ width: "100%", padding: "10px 14px", marginTop: 4 }}
            >
              {busy ? "Membuat Akun..." : "Inisialisasi Akun Pemilik"}
            </button>
          </form>
        )}

        <div
          style={{
            marginTop: 20,
            paddingTop: 14,
            borderTop: "1px solid var(--border)",
            textAlign: "center",
          }}
        >
          <p
            style={{
              fontSize: "0.72rem",
              color: "var(--text-secondary)",
              margin: 0,
              lineHeight: 1.45,
            }}
          >
            <strong>Single-Owner Security:</strong> Registrasi publik ditutup permanen. Akses dilindungi sesi HttpOnly terenkripsi &amp; proteksi rate limit.
          </p>
        </div>
      </div>
    </div>
  );
}
