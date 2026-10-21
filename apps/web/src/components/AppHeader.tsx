"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { BRAND } from "@/lib/brand";
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
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={BRAND.logoMark} alt="" width={38} height={38} />
        <span className="brand-text">
          <span className="brand-name">{BRAND.name}</span>
          <span className="brand-sub">{BRAND.sub}</span>
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
