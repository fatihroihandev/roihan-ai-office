"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { HealthStatus } from "@/components/HealthStatus";
import { HomeHero } from "@/components/home/HomeHero";
import { LiveStrip } from "@/components/home/LiveStrip";
import { CommandDeck } from "@/components/charts/CommandDeck";
import { useInsights } from "@/lib/charts/useInsights";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

const MARKETING_CARDS: { href: string; title: MessageKey; desc: MessageKey; accent: string }[] = [
  { href: "/marketing/seo", title: "nav.websiteSeo", desc: "home.card.marketing", accent: "#2563eb" },
  { href: "/marketing/content", title: "nav.contentStudio", desc: "home.card.marketing", accent: "#3b82f6" },
  { href: "/marketing", title: "nav.marketing", desc: "home.card.marketing", accent: "#6366f1" },
  { href: "/approvals", title: "nav.approvals", desc: "home.card.approvals", accent: "#f59e0b" },
  { href: "/tasks", title: "nav.activityLog", desc: "home.card.tasks", accent: "#10b981" },
  { href: "/ai", title: "nav.ai", desc: "home.card.ai", accent: "#06b6d4" },
  { href: "/products", title: "nav.products", desc: "home.card.products", accent: "#8b5cf6" },
  { href: "/office", title: "nav.office", desc: "home.card.office", accent: "#64748b" },
];

export default function Home() {
  const { t } = useLanguage();
  const { data, stale, connected } = useOfficeData();
  const ins = useInsights(data?.generated_at ?? null);

  return (
    <PageTransition>
      <main data-home>
        <HomeHero data={data} connected={connected} />
        <LiveStrip data={data} stale={stale} ins={ins} />
        {data && <CommandDeck d={data} ins={ins} />}
        
        <h3 className="section-title">MARKETING COMMAND CENTER</h3>
        <div className="homegrid">
          {MARKETING_CARDS.map((c) => (
            <Link key={c.href} href={c.href} className="tile" style={{ ["--tile" as string]: c.accent }}>
              <strong>{t(c.title)}</strong>
              <span>{t(c.desc)}</span>
            </Link>
          ))}
        </div>
        
        <HealthStatus />
        <footer>{t("footer.phase")}</footer>
      </main>
    </PageTransition>
  );
}
