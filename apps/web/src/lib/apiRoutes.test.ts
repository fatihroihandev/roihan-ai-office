import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// Proxy hanya meneruskan metode yang diekspor rute. Metode yang dipakai klien tetapi tidak diekspor menghasilkan 405 diam-diam
// (contoh nyata: menyimpan kunci API provider lewat PATCH tidak pernah sampai ke backend).
const route = (name: string) => readFileSync(new URL(`../app/api/${name}/[[...path]]/route.ts`, import.meta.url), "utf-8");

describe("rute proxy mengekspor metode yang dipakai klien", () => {
  it("providers: PATCH untuk pengaturan provider", () => expect(route("providers")).toMatch(/export const PATCH/));
  it("web: GET, POST, PATCH untuk akses web", () => {
    for (const m of ["GET", "POST", "PATCH"]) expect(route("web")).toMatch(new RegExp(`export const ${m}`));
  });
  it("models dan ai: POST untuk sinkronisasi dan uji", () => {
    expect(route("models")).toMatch(/export const POST/);
    expect(route("ai")).toMatch(/export const POST/);
  });
  it("auth: GET, POST, PATCH, DELETE untuk single-owner authentication", () => {
    for (const m of ["GET", "POST", "PATCH", "DELETE"]) expect(route("auth")).toMatch(new RegExp(`export const ${m}`));
  });
});
