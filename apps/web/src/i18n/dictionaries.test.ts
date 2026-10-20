import { describe, expect, it } from "vitest";
import { dictionaries, isLang, translate } from "./dictionaries";

describe("dictionaries", () => {
  it("id dan en memiliki kunci yang sama", () => {
    expect(Object.keys(dictionaries.en).sort()).toEqual(Object.keys(dictionaries.id).sort());
  });

  it("tidak ada terjemahan kosong", () => {
    for (const lang of ["id", "en"] as const) {
      for (const [key, value] of Object.entries(dictionaries[lang])) {
        expect(value.trim(), `${lang}:${key}`).not.toBe("");
      }
    }
  });

  it("translate mengikuti bahasa", () => {
    expect(translate("id", "status.title")).toBe("Status Sistem");
    expect(translate("en", "status.title")).toBe("System Status");
  });

  it("isLang hanya menerima id dan en", () => {
    expect(isLang("id")).toBe(true);
    expect(isLang("en")).toBe(true);
    expect(isLang("fr")).toBe(false);
    expect(isLang(undefined)).toBe(false);
  });
});
