// Navigasi aplikasi dan logika tombol menu melayang (murni, tanpa DOM, agar mudah diuji).
export const NAV = [
  { href: "/", key: "nav.home" },
  { href: "/office", key: "nav.office" },
  { href: "/projects", key: "nav.projects" },
  { href: "/tasks", key: "nav.tasks" },
  { href: "/products", key: "nav.products" },
  { href: "/marketing", key: "nav.marketing" },
  { href: "/approvals", key: "nav.approvals" },
  { href: "/ai", key: "nav.ai" },
] as const;

/** Indeks menu untuk sebuah path (sub-halaman ikut menu induknya); path tak dikenal dianggap beranda. */
export function navIndex(path: string): number {
  const i = NAV.findIndex((n) => (n.href === "/" ? path === "/" : path === n.href || path.startsWith(`${n.href}/`)));
  return i < 0 ? 0 : i;
}

/** Jenis transisi halaman: menu di kanan (indeks lebih besar) menggeser ke kiri, menu di kiri ke kanan. */
export function transitionFor(from: number, to: number): "nav-forward" | "nav-back" | undefined {
  if (from === to) return undefined;
  return to > from ? "nav-forward" : "nav-back";
}

export type Dock = { side: "left" | "right"; y: number }; // y = pecahan tinggi layar (0 atas, 1 bawah) untuk titik tengah tombol
export const DEFAULT_DOCK: Dock = { side: "right", y: 0.88 };

/** Setelah tombol dilepas: tempel ke sisi layar terdekat dan jaga tetap di dalam layar (menyisakan `pad` piksel di tepi). */
export function snapDock(x: number, y: number, vw: number, vh: number, size: number, pad = 12): Dock {
  const side = x < vw / 2 ? "left" : "right";
  if (!(vh > 0)) return { side, y: DEFAULT_DOCK.y };
  const min = (size / 2 + pad) / vh;
  const max = 1 - min;
  const frac = y / vh;
  return { side, y: Math.min(max, Math.max(min, Number.isFinite(frac) ? frac : DEFAULT_DOCK.y)) };
}

/** Baca nilai tersimpan dengan aman; apa pun yang tidak valid menghasilkan posisi bawaan. */
export function parseDock(raw: string | null): Dock {
  try {
    const v = raw ? (JSON.parse(raw) as Partial<Dock>) : null;
    if (v && (v.side === "left" || v.side === "right") && typeof v.y === "number" && v.y >= 0 && v.y <= 1) return { side: v.side, y: v.y };
  } catch {
    /* data rusak */
  }
  return DEFAULT_DOCK;
}
