// Logika murni pengukuran kinerja 3D (tanpa DOM/three) agar mudah diuji.

export type FrameStats = { fps: number; p95Ms: number; worstMs: number; frames: number };

/** Ringkas daftar durasi frame (milidetik). Daftar kosong menghasilkan nol. */
export function summarizeFrames(frameMs: number[]): FrameStats {
  const xs = frameMs.filter((x) => Number.isFinite(x) && x > 0);
  if (xs.length === 0) return { fps: 0, p95Ms: 0, worstMs: 0, frames: 0 };
  const total = xs.reduce((a, b) => a + b, 0);
  const sorted = [...xs].sort((a, b) => a - b);
  const p95 = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))];
  return { fps: (xs.length / total) * 1000, p95Ms: p95, worstMs: sorted[sorted.length - 1], frames: xs.length };
}

export const SLOW_FPS = 24;
export const MIN_FRAMES = 90;

/**
 * Putuskan apakah kualitas efek perlu diturunkan. Hanya menurunkan (tidak pernah menaikkan sendiri, agar tidak berosilasi),
 * hanya setelah cukup frame terkumpul, dan hanya jika FPS rata-rata DAN frame persentil-95 sama-sama buruk,
 * sehingga satu lonjakan sesaat (mis. memuat model) tidak memicu penurunan.
 */
export function shouldDowngrade(stats: FrameStats, current: "high" | "low"): boolean {
  if (current === "low" || stats.frames < MIN_FRAMES) return false;
  return stats.fps < SLOW_FPS && stats.p95Ms > 1000 / 20;
}

/** Buang durasi frame yang jelas bukan beban render (tab di latar belakang / jeda panjang). */
export function sanitizeFrames(frameMs: number[], capMs = 500): number[] {
  return frameMs.filter((x) => x > 0 && x < capMs);
}
