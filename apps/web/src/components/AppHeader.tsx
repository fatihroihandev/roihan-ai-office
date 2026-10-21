"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
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

const indexOf = (path: string) => {
  const i = NAV.findIndex((n) => (n.href === "/" ? path === "/" : path === n.href || path.startsWith(`${n.href}/`)));
  return i < 0 ? 0 : i;
};

/** Header persisten (di layout): tidak ikut dimuat ulang saat berpindah halaman. Pil aktif meluncur ke menu tujuan. */
export function AppHeader() {
  const { t } = useLanguage();
  const path = usePathname() ?? "/";
  const current = indexOf(path);
  const nav = useRef<HTMLElement>(null);
  const pill = useRef<HTMLSpanElement>(null);

  // posisi pil diukur dari tautan aktif dan ditulis langsung ke DOM (transisi CSS menghaluskan geraknya)
  useEffect(() => {
    const place = () => {
      const el = nav.current?.querySelector<HTMLElement>('a[aria-current="page"]');
      const p = pill.current;
      if (!el || !p) return;
      p.style.width = `${el.offsetWidth}px`;
      p.style.transform = `translateX(${el.offsetLeft}px)`;
      p.style.opacity = "1";
    };
    place();
    const ro = new ResizeObserver(place);
    if (nav.current) ro.observe(nav.current);
    window.addEventListener("resize", place);
    document.fonts?.ready.then(place, () => undefined);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", place);
    };
  }, [path]);

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
      <nav aria-label="Menu" ref={nav}>
        <span className="nav-pill" ref={pill} aria-hidden="true" />
        {NAV.map((n, i) => (
          <Link
            key={n.href} href={n.href} aria-current={i === current ? "page" : undefined}
            transitionTypes={i === current ? undefined : [i > current ? "nav-forward" : "nav-back"]}
          >
            {t(n.key)}
          </Link>
        ))}
      </nav>
      <LanguageSwitcher />
    </header>
  );
}
