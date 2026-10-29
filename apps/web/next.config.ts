import type { NextConfig } from "next";

const dev = process.env.NODE_ENV !== "production";
const wsUrl = process.env.NEXT_PUBLIC_API_WS_URL?.replace(/\/+$/, "");
const apiUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL)?.replace(/\/+$/, "");

const connectSrc = [
  "'self'",
  "ws://127.0.0.1:*",
  "ws://localhost:*",
  "http://127.0.0.1:*",
  "http://localhost:*",
  wsUrl,
  apiUrl,
  "https://*.onrender.com",
  "wss://*.onrender.com",
].filter(Boolean).join(" ");

// CSP statis: Next menyisipkan skrip inline untuk hidrasi, jadi 'unsafe-inline' dibutuhkan pada script-src (tanpa nonce per permintaan).
// Pertahanan utama tetap: tidak ada konten pihak ketiga, object/base/frame ditutup, dan koneksi hanya ke asal sendiri + backend terpercaya.
// 'unsafe-eval' hanya di mode dev (React/Turbopack membutuhkannya untuk debugging).
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src ${connectSrc}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
