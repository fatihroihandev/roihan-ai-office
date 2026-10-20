"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { Lang, MessageKey, dictionaries, translate } from "./dictionaries";

type Ctx = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: MessageKey) => string;
  /** Terjemahan untuk kunci dinamis (mis. dari backend); memakai `fallback` jika kunci tidak ada. */
  tOr: (key: string, fallback: string) => string;
};

const LanguageContext = createContext<Ctx | null>(null);

export function LanguageProvider({ initialLang, children }: { initialLang: Lang; children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    document.cookie = `lang=${next}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = next;
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      lang,
      setLang,
      t: (key) => translate(lang, key),
      tOr: (key, fallback) => (dictionaries[lang] as Record<string, string>)[key] ?? fallback,
    }),
    [lang, setLang],
  );
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): Ctx {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage harus dipakai di dalam LanguageProvider");
  return ctx;
}
