import { describe, expect, it } from "vitest";
import { DEFAULT_DOCK, NAV, navIndex, parseDock, snapDock, transitionFor } from "./nav";

describe("navIndex", () => {
  it("memetakan path dan sub-halamannya ke menu induk", () => {
    expect(navIndex("/")).toBe(0);
    expect(navIndex("/office")).toBe(1);
    expect(navIndex("/marketing/leads/abc")).toBe(NAV.findIndex((n) => n.href === "/marketing"));
    expect(navIndex("/tasks/xyz")).toBe(NAV.findIndex((n) => n.href === "/tasks"));
  });
  it("path tak dikenal dan awalan palsu tidak cocok", () => {
    expect(navIndex("/tidak-ada")).toBe(0);
    expect(navIndex("/officeX")).toBe(0);
  });
});

describe("transitionFor", () => {
  it("menentukan arah geser", () => {
    expect(transitionFor(1, 4)).toBe("nav-forward");
    expect(transitionFor(4, 1)).toBe("nav-back");
    expect(transitionFor(2, 2)).toBeUndefined();
  });
});

describe("snapDock", () => {
  it("menempel ke sisi terdekat", () => {
    expect(snapDock(100, 400, 1400, 900, 56).side).toBe("left");
    expect(snapDock(1300, 400, 1400, 900, 56).side).toBe("right");
  });
  it("menjaga tombol tetap di dalam layar", () => {
    const top = snapDock(10, -50, 1400, 900, 56);
    const bottom = snapDock(10, 5000, 1400, 900, 56);
    expect(top.y).toBeGreaterThan(0);
    expect(bottom.y).toBeLessThan(1);
    expect(top.y * 900).toBeGreaterThanOrEqual(56 / 2 + 12 - 0.001);
    expect((1 - bottom.y) * 900).toBeGreaterThanOrEqual(56 / 2 + 12 - 0.001);
  });
  it("tinggi layar nol tidak menghasilkan NaN", () => {
    expect(Number.isFinite(snapDock(10, 10, 800, 0, 56).y)).toBe(true);
  });
});

describe("parseDock", () => {
  it("membaca nilai valid", () => {
    expect(parseDock('{"side":"left","y":0.3}')).toEqual({ side: "left", y: 0.3 });
  });
  it("nilai rusak atau di luar jangkauan memakai bawaan", () => {
    expect(parseDock(null)).toEqual(DEFAULT_DOCK);
    expect(parseDock("bukan json")).toEqual(DEFAULT_DOCK);
    expect(parseDock('{"side":"atas","y":0.3}')).toEqual(DEFAULT_DOCK);
    expect(parseDock('{"side":"left","y":7}')).toEqual(DEFAULT_DOCK);
  });
});
