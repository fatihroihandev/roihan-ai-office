"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { BRAND } from "@/lib/brand";
import { DEFAULT_DOCK, NAV, navIndex, parseDock, snapDock, transitionFor, type Dock } from "@/lib/nav";
import { useLanguage } from "@/i18n/LanguageProvider";

// ---- posisi tombol: disimpan di peramban (hanya kenyamanan; tanpa penyimpanan tetap berfungsi dengan posisi bawaan)
const DOCK_KEY = "roihan.nav.dock";
const dockListeners = new Set<() => void>();
let dockCache: { raw: string | null; dock: Dock } = { raw: null, dock: DEFAULT_DOCK };

function readDock(): Dock {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(DOCK_KEY);
  } catch {
    /* penyimpanan tidak tersedia */
  }
  if (raw !== dockCache.raw) dockCache = { raw, dock: parseDock(raw) };
  return dockCache.dock;
}

function writeDock(d: Dock) {
  const raw = JSON.stringify(d);
  dockCache = { raw, dock: d };
  try {
    window.localStorage.setItem(DOCK_KEY, raw);
  } catch {
    /* hanya berlaku selama sesi */
  }
  dockListeners.forEach((l) => l());
}

const subscribeDock = (cb: () => void) => {
  dockListeners.add(cb);
  return () => void dockListeners.delete(cb);
};

const SIZE = 56;
const DRAG_THRESHOLD = 6;

/** Tombol menu melayang: menggantikan bilah navigasi agar layar penuh. Dapat diseret ke tepi kiri/kanan; M membuka, Esc menutup. */
export function FloatNav() {
  const { t } = useLanguage();
  const path = usePathname() ?? "/";
  const current = navIndex(path);
  const dock = useSyncExternalStore(subscribeDock, readDock, () => DEFAULT_DOCK);
  // menu terbuka hanya untuk path tempat ia dibuka: berpindah halaman menutupnya tanpa efek samping
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === path;
  const btn = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const suppressClick = useRef(false);
  const drag = useRef<{ id: number; sx: number; sy: number; moved: boolean } | null>(null);

  const toggle = useCallback(() => setOpenAt((v) => (v === path ? null : path)), [path]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenAt(null);
        return;
      }
      const el = e.target as HTMLElement | null;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if ((e.key === "m" || e.key === "M") && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) toggle();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);

  // fokus ke menu aktif saat dibuka (keyboard); kembali ke tombol saat ditutup lewat Esc
  useEffect(() => {
    if (open) panel.current?.querySelector<HTMLElement>('a[aria-current="page"]')?.focus();
  }, [open]);

  const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    drag.current = { id: e.pointerId, sx: e.clientX, sy: e.clientY, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    const el = btn.current;
    if (!d || d.id !== e.pointerId || !el) return;
    if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < DRAG_THRESHOLD) return;
    d.moved = true;
    // selama menyeret, posisi ditulis langsung ke DOM (tanpa render ulang)
    el.style.transition = "none";
    el.style.left = `${e.clientX - SIZE / 2}px`;
    el.style.top = `${e.clientY - SIZE / 2}px`;
    el.style.right = "auto";
    el.style.transform = "none";
  };
  const onPointerUp = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = drag.current;
    const el = btn.current;
    drag.current = null;
    if (!d || !el) return;
    if (!d.moved) return; // klik biasa ditangani onClick
    for (const k of ["transition", "left", "top", "right", "transform"] as const) el.style[k] = "";
    writeDock(snapDock(e.clientX, e.clientY, window.innerWidth, window.innerHeight, SIZE));
    setOpenAt(null);
    suppressClick.current = true;
  };
  const onClick = () => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    toggle();
  };

  return (
    <div className="fnav" data-side={dock.side} data-vert={dock.y > 0.5 ? "up" : "down"} data-open={open ? "true" : "false"} style={{ "--dock-y": dock.y } as React.CSSProperties}>
      {open && <div className="fnav-scrim" onClick={() => setOpenAt(null)} aria-hidden="true" />}
      <nav id="fnav-panel" className="fnav-panel" aria-label="Menu" hidden={!open} ref={panel}>
        <div className="fnav-head">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={BRAND.logoMark} alt="" width={34} height={34} />
          <span className="fnav-brand">
            <b>{BRAND.name}</b>
            <i>{BRAND.sub}</i>
          </span>
        </div>
        <ol className="fnav-list">
          {NAV.map((n, i) => (
            <li key={n.href}>
              <Link
                href={n.href} aria-current={i === current ? "page" : undefined} onClick={() => setOpenAt(null)}
                transitionTypes={(() => { const k = transitionFor(current, i); return k ? [k] : undefined; })()}
              >
                <span className="fnav-idx">{String(i + 1).padStart(2, "0")}</span>
                <span>{t(n.key)}</span>
              </Link>
            </li>
          ))}
        </ol>
        <div className="fnav-foot">
          <LanguageSwitcher />
          <span className="fnav-hint">{t("nav.hint")}</span>
        </div>
      </nav>
      <button
        type="button" ref={btn} className="fnav-btn" aria-label={open ? t("nav.close") : t("nav.menu")} aria-expanded={open} aria-controls="fnav-panel"
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onClick={onClick}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={BRAND.logoMark} alt="" width={30} height={30} draggable={false} />
        <span className="fnav-ring" aria-hidden="true" />
      </button>
    </div>
  );
}
