import { describe, expect, it } from "vitest";
import { MIN_FRAMES, sanitizeFrames, shouldDowngrade, summarizeFrames } from "./perf";

const steady = (ms: number, n = 200) => Array.from({ length: n }, () => ms);

describe("summarizeFrames", () => {
  it("menghitung FPS dan p95 dari durasi frame", () => {
    const s = summarizeFrames(steady(16.67, 120));
    expect(s.fps).toBeGreaterThan(59);
    expect(s.fps).toBeLessThan(61);
    expect(s.frames).toBe(120);
  });
  it("kosong atau data tidak valid menghasilkan nol", () => {
    expect(summarizeFrames([])).toEqual({ fps: 0, p95Ms: 0, worstMs: 0, frames: 0 });
    expect(summarizeFrames([NaN, -3, 0]).frames).toBe(0);
  });
  it("p95 menangkap frame lambat sesekali", () => {
    const frames = [...steady(16, 90), ...steady(120, 10)];
    expect(summarizeFrames(frames).p95Ms).toBe(120);
    expect(summarizeFrames(frames).worstMs).toBe(120);
  });
});

describe("shouldDowngrade", () => {
  it("menurunkan kualitas saat FPS rendah dan stabil buruk", () => {
    expect(shouldDowngrade(summarizeFrames(steady(60)), "high")).toBe(true);
  });
  it("tidak menurunkan saat kinerja baik", () => {
    expect(shouldDowngrade(summarizeFrames(steady(16.7)), "high")).toBe(false);
  });
  it("menunggu cukup frame sebelum memutuskan", () => {
    expect(shouldDowngrade(summarizeFrames(steady(80, MIN_FRAMES - 1)), "high")).toBe(false);
  });
  it("tidak menurunkan karena lonjakan sesaat", () => {
    expect(shouldDowngrade(summarizeFrames([...steady(16, 180), ...steady(400, 4)]), "high")).toBe(false);
  });
  it("tidak melakukan apa pun bila sudah rendah", () => {
    expect(shouldDowngrade(summarizeFrames(steady(100)), "low")).toBe(false);
  });
});

describe("sanitizeFrames", () => {
  it("membuang jeda panjang dan nilai tak wajar", () => {
    expect(sanitizeFrames([16, 5000, 0, -1, 20])).toEqual([16, 20]);
  });
});
