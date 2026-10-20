"use client";

import { HealthStatus } from "@/components/HealthStatus";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useLanguage } from "@/i18n/LanguageProvider";

export default function Home() {
  const { t } = useLanguage();
  return (
    <main>
      <header>
        <div>
          <h1>{t("app.name")}</h1>
          <p className="tagline">{t("app.tagline")}</p>
        </div>
        <LanguageSwitcher />
      </header>
      <HealthStatus />
      <footer>{t("footer.phase")}</footer>
    </main>
  );
}
