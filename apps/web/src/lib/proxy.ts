const SEGMENT = /^[A-Za-z0-9._-]+$/;

/**
 * Susun URL backend dari segmen path yang diterima proxy.
 * Menolak segmen kosong, "." dan "..", serta karakter di luar [A-Za-z0-9._-]
 * agar proxy tidak bisa diarahkan ke endpoint lain.
 */
export function buildUpstreamUrl(base: string, allowedPrefix: string, segments: string[], search: string): string | null {
  if (segments.some((s) => !SEGMENT.test(s) || s === "." || s === "..")) return null;
  const path = [allowedPrefix, ...segments].join("/");
  return `${base.replace(/\/$/, "")}/${path}${search}`;
}
