"use client";

import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";
import { HealthStatus } from "@/components/HealthStatus";
import { useLanguage } from "@/i18n/LanguageProvider";

export default function Home() {
  const { t } = useLanguage();
  return (
    <main>
      <AppHeader />
      <HealthStatus />
      <p>
        <Link className="button" href="/office">{t("home.openOffice")}</Link>{" "}
        <Link className="button" href="/projects">{t("home.openProjects")}</Link>
      </p>
      <footer>{t("footer.phase")}</footer>
    </main>
  );
}
