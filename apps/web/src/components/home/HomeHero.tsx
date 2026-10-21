"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Component, useCallback, useRef, useState, type ReactNode } from "react";
import { useOfficeMode } from "@/components/office/OfficeView";
import { heroActivity } from "@/lib/home/activity";
import type { Dashboard } from "@/lib/dashboardApi";
import { useLanguage } from "@/i18n/LanguageProvider";

const HeroScene = dynamic(() => import("@/components/home/HeroScene"), { ssr: false, loading: () => null });

class Boundary extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/** Hero beranda: kota cyberpunk 3D di belakang judul. Tanpa WebGL atau dengan gerak berkurang: latar CSS statis bergaya sama. */
export function HomeHero({ data, connected }: { data: Dashboard | null; connected: boolean }) {
  const { t } = useLanguage();
  const { mode, onFail } = useOfficeMode();
  const [visible, setVisible] = useState(true);
  const observer = useRef<IntersectionObserver | null>(null);
  // render berhenti saat hero tidak terlihat (hemat baterai/GPU); ref callback agar tanpa setState di effect
  const watch = useCallback((el: HTMLDivElement | null) => {
    observer.current?.disconnect();
    if (!el || typeof IntersectionObserver === "undefined") return;
    observer.current = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0.05 });
    observer.current.observe(el);
  }, []);
  const activity = heroActivity(data);

  return (
    <section className="hero3d" ref={watch} aria-label={t("home.hero")}>
      <div className="hero3d-bg" aria-hidden="true">
        {mode === "3d" ? (
          <Boundary onError={onFail}>
            <HeroScene activity={activity} running={visible} onFail={onFail} />
          </Boundary>
        ) : (
          <div className="hero-fallback" />
        )}
      </div>
      <div className="hero3d-shade" aria-hidden="true" />
      <div className="hero3d-copy">
        <p className="eyebrow">
          <span className="badge" data-task={connected ? "completed" : "failed"}>{connected ? t("office.live") : t("office.polling")}</span>
          <span className="badge" data-task="completed">{t("office.ai.paidOff")}</span>
        </p>
        <h2>
          <span className="glitch" data-text="BUILD TODAY,">BUILD TODAY,</span>
          <br />
          <span className="neon-grad">CREATE TOMORROW</span>
        </h2>
        <p className="lead">{t("home.hero.sub")}</p>
        <div className="actions">
          <Link className="button primary" href="/office">{t("home.openOffice")}</Link>
          <Link className="button" href="/projects">{t("home.openProjects")}</Link>
          <Link className="button" href="/approvals">{t("nav.approvals")}</Link>
        </div>
      </div>
    </section>
  );
}
