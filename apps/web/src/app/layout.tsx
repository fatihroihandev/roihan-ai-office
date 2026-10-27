import type { Metadata } from "next";
import { cookies } from "next/headers";
import { AppShell } from "@/components/layout/AppShell";
import { LanguageProvider } from "@/i18n/LanguageProvider";
import { ensureRootEnv } from "@/lib/server-env";
import { isLang, translate, type Lang } from "@/i18n/dictionaries";
import "@fontsource-variable/montserrat";
import "./globals.css";
import "./cyber-ui.css";
import "./modern-ui.css";

async function resolveLang(): Promise<Lang> {
  const cookieLang = (await cookies()).get("lang")?.value;
  if (isLang(cookieLang)) return cookieLang;
  ensureRootEnv();
  const fallback = process.env.APP_DEFAULT_LANGUAGE;
  return isLang(fallback) ? fallback : "id";
}

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveLang();
  return { title: translate(lang, "app.name"), description: translate(lang, "app.tagline") };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = await resolveLang();
  return (
    <html lang={lang}>
      <body>
        <LanguageProvider initialLang={lang}>
          <AppShell>
            {children}
          </AppShell>
        </LanguageProvider>
      </body>
    </html>
  );
}
