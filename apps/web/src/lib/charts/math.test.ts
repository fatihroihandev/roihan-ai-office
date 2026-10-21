import { describe, expect, it } from "vitest";
import { ago, compact, intTicks, niceMax, parseUtc, pct, stack, stepRates, ticks } from "./math";

describe("skala dan tick", () => {
  it("niceMax membulatkan ke atas ke 1/2/5/10 x 10^n dan tidak pernah 0", () => {
    expect([0, 0.4, 1, 1.2, 3, 7, 12, 480, 1001].map(niceMax)).toEqual([1, 0.5, 1, 2, 5, 10, 20, 500, 2000]);
  });
  it("ticks dimulai dari 0 dan berakhir di batas bulat", () => {
    expect(ticks(7)).toEqual([0, 2.5, 5, 7.5, 10]);
    expect(ticks(0)[0]).toBe(0);
  });
});

describe("format", () => {
  it("compact: ringkas mulai 1000", () => {
    expect(compact(0)).toBe("0");
    expect(compact(999)).toBe("999");
    expect(compact(1500)).toBe("1,5K");
    expect(compact(2_400_000)).toBe("2,4JT");
    expect(compact(1500, "en")).toBe("1.5K");
  });
  it("pct: null tetap null (belum diketahui, bukan nol)", () => {
    expect(pct(null)).toBeNull();
    expect(pct(0)).toBe("0%");
    expect(pct(0.8333, 1)).toBe("83.3%");
  });
  it("ago", () => {
    const now = Date.parse("2026-10-21T10:00:00Z");
    expect(ago("2026-10-21T09:59:30", now)).toBe("30 dtk lalu");
    expect(ago("2026-10-21T09:55:00", now)).toBe("5 mnt lalu");
    expect(ago("2026-10-21T07:00:00", now, "en")).toBe("3h ago");
    expect(ago("2026-10-19T10:00:00Z", now)).toBe("2 h lalu");
  });
});

describe("corong dan tumpukan", () => {
  it("stepRates: konversi tahap ke tahap, tahap pertama dan pembagi nol = null", () => {
    expect(stepRates([10, 5, 5, 0, 0])).toEqual([null, 0.5, 1, 0, null]);
  });
  it("stack: kumulatif berurutan", () => {
    expect(stack([2, 0, 3])).toEqual([{ from: 0, to: 2 }, { from: 2, to: 2 }, { from: 2, to: 5 }]);
  });
});

describe("tick bilangan bulat dan waktu", () => {
  it("intTicks: bulat, mulai 0, menutup nilai maksimum, paling banyak 5 interval", () => {
    expect(intTicks(0)).toEqual([0, 1]);
    expect(intTicks(5)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(intTicks(12)).toEqual([0, 5, 10, 15]);
    expect(intTicks(47)).toEqual([0, 10, 20, 30, 40, 50]);
    for (const m of [1, 3, 7, 19, 101, 4800]) {
      const t = intTicks(m);
      expect(t[0]).toBe(0);
      expect(t[t.length - 1]).toBeGreaterThanOrEqual(m);
      expect(t.every(Number.isInteger)).toBe(true);
      expect(t.length - 1).toBeLessThanOrEqual(5);
    }
  });
  it("parseUtc menerima Z, offset, dan tanpa zona (dianggap UTC)", () => {
    const ms = Date.parse("2026-10-21T06:03:23Z");
    expect(parseUtc("2026-10-21T06:03:23")).toBe(ms);
    expect(parseUtc("2026-10-21T06:03:23Z")).toBe(ms);
    expect(parseUtc("2026-10-21T06:03:23+00:00")).toBe(ms);
    expect(parseUtc("2026-10-21T13:03:23+07:00")).toBe(ms);
  });
});
