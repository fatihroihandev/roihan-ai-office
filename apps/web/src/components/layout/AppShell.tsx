"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { DOCK, type DashboardView } from "@/lib/dashboard/dock";

// Hanya ada satu dashboard. Halaman detail (mis. /tasks/[id]) memakai dock, tema, dan wadah
// yang sama dengan dashboard; setiap menu dock membuka tampilan dashboard di rute "/".
const SECTION: { prefix: string; view: DashboardView }[] = [
  { prefix: "/tasks", view: "tasks" },
  { prefix: "/projects", view: "projects" },
  { prefix: "/products", view: "products" },
  { prefix: "/marketing/leads", view: "leads" },
  { prefix: "/marketing/campaigns", view: "campaigns" },
  { prefix: "/marketing/content", view: "content" },
  { prefix: "/marketing/seo", view: "seo" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("roihan_theme");
    if (saved === "dark" || saved === "light") {
      setTheme(saved);
      document.documentElement.setAttribute("data-theme", saved);
    }
  }, []);

  if (pathname === "/") return <div className="app-shell dashboard-mode">{children}</div>;

  const current = SECTION.find((s) => pathname.startsWith(s.prefix))?.view;
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("roihan_theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  return (
    <div className="app-shell dashboard-mode">
      <div className={`inspired-dashboard-container ${theme === "light" ? "light-theme" : ""}`} data-theme={theme}>
        <aside className="inspired-dock" aria-label="Dock Navigasi Marketing">
          <Link href="/" className="inspired-dock-logo" title="Roihan AI Office" aria-label="Roihan AI Office">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 5v14M18 5v14M2 9h4M18 9h4M2 15h4M18 15h4M6 12h12" />
            </svg>
          </Link>
          <ul className="inspired-dock-nav">
            {DOCK.map((d) => (
              <li key={d.view}>
                <Link
                  href={d.view === "overview" ? "/" : `/?view=${d.view}`}
                  className={`inspired-dock-btn ${current === d.view ? "active" : ""}`}
                  title={d.title}
                  aria-label={d.title}
                >
                  <span aria-hidden="true" style={{ fontSize: "1.1rem" }}>{d.icon}</span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="inspired-dock-footer">
            <button type="button" className="inspired-dock-btn" onClick={toggleTheme} title={theme === "dark" ? "Ganti ke Light Mode" : "Ganti ke Dark Mode"}>
              {theme === "dark" ? "🌙" : "☀️"}
            </button>
          </div>
        </aside>
        <main className="inspired-workspace">
          <div className="feature-view-container">{children}</div>
        </main>
      </div>
    </div>
  );
}
