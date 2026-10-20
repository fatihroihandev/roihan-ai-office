export const dictionaries = {
  id: {
    "app.name": "Roihan Software House",
    "app.tagline": "Build Today, Create Tomorrow",
    "status.title": "Status Sistem",
    "status.overall": "Keseluruhan",
    "status.database": "Database",
    "status.ollama": "Ollama (AI lokal)",
    "status.paidCalls": "API berbayar",
    "status.paidCalls.off": "Nonaktif",
    "status.paidCalls.on": "Aktif",
    "status.loading": "Memeriksa...",
    "status.unreachable": "API tidak dapat dihubungi",
    "status.refresh": "Periksa ulang",
    "value.ok": "Normal",
    "value.degraded": "Terbatas",
    "value.error": "Gangguan",
    "value.up": "Aktif",
    "value.down": "Mati",
    "value.disabled": "Dinonaktifkan",
    "lang.label": "Bahasa",
    "footer.phase": "Phase 1 — Foundation. Fitur lain belum tersedia.",
  },
  en: {
    "app.name": "Roihan Software House",
    "app.tagline": "Build Today, Create Tomorrow",
    "status.title": "System Status",
    "status.overall": "Overall",
    "status.database": "Database",
    "status.ollama": "Ollama (local AI)",
    "status.paidCalls": "Paid APIs",
    "status.paidCalls.off": "Disabled",
    "status.paidCalls.on": "Enabled",
    "status.loading": "Checking...",
    "status.unreachable": "API is unreachable",
    "status.refresh": "Check again",
    "value.ok": "Healthy",
    "value.degraded": "Degraded",
    "value.error": "Error",
    "value.up": "Up",
    "value.down": "Down",
    "value.disabled": "Disabled",
    "lang.label": "Language",
    "footer.phase": "Phase 1 — Foundation. Other features are not available yet.",
  },
} as const;

export type Lang = keyof typeof dictionaries;
export type MessageKey = keyof (typeof dictionaries)["id"];
export const LANGS: Lang[] = ["id", "en"];

export function isLang(value: unknown): value is Lang {
  return value === "id" || value === "en";
}

export function translate(lang: Lang, key: MessageKey): string {
  return dictionaries[lang][key];
}
