"use client";

import { LANGS } from "@/i18n/dictionaries";
import { useLanguage } from "@/i18n/LanguageProvider";

export function LanguageSwitcher() {
  const { lang, setLang, t } = useLanguage();
  return (
    <div role="group" aria-label={t("lang.label")} className="lang">
      {LANGS.map((l) => (
        <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)}>
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
