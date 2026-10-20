import "server-only";
import path from "node:path";
import { loadEnvConfig } from "@next/env";

let loaded = false;

/** Memuat .env di root repository ke process.env (hanya sisi server). Aman dipanggil berulang. */
export function ensureRootEnv(): void {
  if (loaded) return;
  loadEnvConfig(path.resolve(process.cwd(), "../.."));
  loaded = true;
}
