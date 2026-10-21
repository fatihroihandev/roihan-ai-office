"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const NAV: { href: string; key: MessageKey }[] = [
  { href: "/", key: "nav.home" },
  { href: "/office", key: "nav.office" },
  { href: "/projects", key: "nav.projects" },
  { href: "/tasks", key: "nav.tasks" },
  { href: "/products", key: "nav.products" },
  { href: "/marketing", key: "nav.marketing" },
  { href: "/approvals", key: "nav.approvals" },
  { href: "/ai", key: "nav.ai" },
];

export function AppHeader() {
  const { t } = useLanguage();
  const path = usePathname() ?? "/";
  const active = (href: string) => (href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`));
  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label={t("app.name")}>
        <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">
          <defs>
            <linearGradient id="rg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#00e5ff" />
              <stop offset="1" stopColor="#ff2bd6" />
            </linearGradient>
          </defs>
          <polygon points="17,2 30,9.5 30,24.5 17,32 4,24.5 4,9.5" fill="rgba(0,184,255,0.08)" stroke="url(#rg)" strokeWidth="1.8" />
          <path d="M12 23V11h6.2a3.6 3.6 0 0 1 0 7.2H12m6 0 4.2 4.8" fill="none" stroke="url(#rg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span>
          <span className="brand-name">{t("app.name")}</span>
          <span className="tagline">{t("app.tagline")}</span>
        </span>
      </Link>
      <nav aria-label="Menu">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}>{t(n.key)}</Link>
        ))}
      </nav>
      <LanguageSwitcher />
    </header>
  );
}
