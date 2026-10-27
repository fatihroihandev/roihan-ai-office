"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { BRAND } from "@/lib/brand";

// Hanya ada satu dashboard (rute "/"). Halaman detail (mis. /tasks/[id]) tampil dengan bilah
// kembali ringkas ke tampilan dashboard asalnya, tanpa sidebar kedua.
const BACK: { prefix: string; view: string; label: string }[] = [
  { prefix: "/tasks", view: "tasks", label: "Tugas" },
  { prefix: "/projects", view: "projects", label: "Proyek" },
  { prefix: "/products", view: "products", label: "Produk" },
  { prefix: "/marketing/leads", view: "leads", label: "Leads & CRM" },
  { prefix: "/marketing/campaigns", view: "campaigns", label: "Kampanye" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  if (pathname === "/") return <div className="app-shell dashboard-mode">{children}</div>;

  const back = BACK.find((b) => pathname.startsWith(b.prefix));
  return (
    <div className="app-shell">
      <header className="app-header" style={{ position: "sticky", top: 0, zIndex: 10 }}>
        <div className="header-left">
          <Link href={`/?view=${back?.view ?? "overview"}`} className="brand-badge">
            <span aria-hidden="true">←</span>
            <span className="brand-text">
              <span className="brand-title">{BRAND.name}</span>
              <span className="brand-sub">Kembali ke Dashboard{back ? ` · ${back.label}` : ""}</span>
            </span>
          </Link>
        </div>
      </header>
      <main className="app-content-body">{children}</main>
    </div>
  );
}
