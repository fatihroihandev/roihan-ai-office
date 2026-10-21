"use client";

import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";
import { HealthStatus } from "@/components/HealthStatus";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const CARDS: { href: string; title: MessageKey; desc: MessageKey; accent: string }[] = [
  { href: "/office", title: "nav.office", desc: "home.card.office", accent: "#00b8ff" },
  { href: "/projects", title: "nav.projects", desc: "home.card.projects", accent: "#7c5cff" },
  { href: "/tasks", title: "nav.tasks", desc: "home.card.tasks", accent: "#00b8ff" },
  { href: "/products", title: "nav.products", desc: "home.card.products", accent: "#a855f7" },
  { href: "/marketing", title: "nav.marketing", desc: "home.card.marketing", accent: "#ff2bd6" },
  { href: "/approvals", title: "nav.approvals", desc: "home.card.approvals", accent: "#ffb020" },
  { href: "/ai", title: "nav.ai", desc: "home.card.ai", accent: "#2dd4bf" },
];

export default function Home() {
  const { t } = useLanguage();
  return (
    <main>
      <AppHeader />
      <section className="hero">
        <h2>{t("home.hero")}</h2>
        <p className="muted">{t("home.hero.sub")}</p>
      </section>
      <div className="homegrid">
        {CARDS.map((c) => (
          <Link key={c.href} href={c.href} className="tile" style={{ ["--tile" as string]: c.accent }}>
            <strong>{t(c.title)}</strong>
            <span>{t(c.desc)}</span>
          </Link>
        ))}
      </div>
      <HealthStatus />
      <footer>{t("footer.phase")}</footer>
    </main>
  );
}
