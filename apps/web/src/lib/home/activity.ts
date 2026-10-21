// Aktivitas visual beranda sebagai fungsi murni dari potret backend (/api/dashboard): inti hologram berdenyut lebih cepat
// ketika ada task berjalan, berwarna kuning jika ada approval menunggu, dan merah jika ada task gagal/terblokir.
// Tidak ada keadaan yang disimulasikan: tanpa data, inti berada dalam keadaan tenang.
import type { Dashboard } from "@/lib/dashboardApi";

export type HeroTone = "idle" | "busy" | "wait" | "alert";
export type HeroActivity = { level: 0 | 1 | 2 | 3; tone: HeroTone; color: string; running: number };

export const TONE_COLOR: Record<HeroTone, string> = { idle: "#3b82f6", busy: "#39ff88", wait: "#ffb020", alert: "#ff3860" };

export function heroActivity(d: Dashboard | null): HeroActivity {
  if (!d) return { level: 0, tone: "idle", color: TONE_COLOR.idle, running: 0 };
  const running = d.tasks.running ?? 0;
  const problems = (d.tasks.failed ?? 0) + (d.tasks.blocked ?? 0);
  const level = running === 0 ? 0 : running === 1 ? 1 : running <= 3 ? 2 : 3;
  const tone: HeroTone = problems > 0 ? "alert" : d.approvals_pending > 0 ? "wait" : running > 0 ? "busy" : "idle";
  return { level, tone, color: TONE_COLOR[tone], running };
}
