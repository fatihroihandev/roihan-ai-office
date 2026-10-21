"use client";

import Link from "next/link";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/i18n/LanguageProvider";

export function AppHeader() {
  const { t } = useLanguage();
  return (
    <header>
      <div>
        <h1>{t("app.name")}</h1>
        <p className="tagline">{t("app.tagline")}</p>
        <nav>
          <Link href="/">{t("nav.home")}</Link>
          <Link href="/office">{t("nav.office")}</Link>
          <Link href="/projects">{t("nav.projects")}</Link>
          <Link href="/tasks">{t("nav.tasks")}</Link>
          <Link href="/products">{t("nav.products")}</Link>
          <Link href="/marketing">{t("nav.marketing")}</Link>
          <Link href="/approvals">{t("nav.approvals")}</Link>
          <Link href="/ai">{t("nav.ai")}</Link>
        </nav>
      </div>
      <LanguageSwitcher />
    </header>
  );
}
