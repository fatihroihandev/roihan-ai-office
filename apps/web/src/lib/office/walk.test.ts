import { describe, expect, it } from "vitest";
import { ROOMS, workSeat } from "./model";
import {
  BOUNDS, CEO_RADIUS, CEO_START, collides, INTERACT_RADIUS, moveWithCollision, nearestInteractable, OBSTACLES, PLACES, velocityFromInput,
} from "./walk";

describe("titik awal dan rintangan", () => {
  it("CEO mulai di area bebas di depan CEO Office", () => {
    expect(collides(CEO_START[0], CEO_START[1], CEO_RADIUS)).toBe(false);
    expect(CEO_START[1]).toBeGreaterThan(ROOMS.ceo.center[1]);
  });
  it("dinding, meja, sofa, dan batas dunia menghalangi", () => {
    const [cx, cz] = ROOMS.engineering.center;
    expect(collides(cx, cz - ROOMS.engineering.size[1] / 2, CEO_RADIUS)).toBe(true);        // dinding belakang
    const [dx, dz] = workSeat("developer");
    expect(collides(dx, dz - 0.8, CEO_RADIUS)).toBe(true);                                  // meja kerja
    expect(collides(BOUNDS[2] + 1, 0, CEO_RADIUS)).toBe(true);                              // luar dunia
  });
  it("pintu: sisi depan ruangan terbuka", () => {
    const [cx, cz] = ROOMS.engineering.center;
    expect(collides(cx - 3, cz + ROOMS.engineering.size[1] / 2 + 0.2, CEO_RADIUS)).toBe(false);
  });
});

describe("gerak dengan tabrakan", () => {
  it("bergerak bebas di ruang kosong", () => {
    const [x, z] = moveWithCollision(CEO_START, [1, 0]);
    expect(x).toBeCloseTo(CEO_START[0] + 1, 5);
    expect(z).toBeCloseTo(CEO_START[1], 5);
  });
  it("tidak menembus dinding tipis walau langkah besar", () => {
    const [cx, cz] = ROOMS.marketing.center;
    const start: [number, number] = [cx, cz - ROOMS.marketing.size[1] / 2 - 1];            // di belakang dinding belakang Marketing
    const [, z] = moveWithCollision(start, [0, 6]);                                          // mendorong ke dalam ruangan dari belakang
    expect(z).toBeLessThan(cz - ROOMS.marketing.size[1] / 2 + 0.1);
  });
  it("menyusuri dinding: komponen sejajar tetap bergerak", () => {
    const [cx, cz] = ROOMS.engineering.center;
    const wallX = cx + ROOMS.engineering.size[0] / 2;                                        // sisi kanan Engineering
    const start: [number, number] = [wallX + CEO_RADIUS + 0.3, cz];
    const [x, z] = moveWithCollision(start, [-2, 1.5]);
    expect(z).toBeCloseTo(cz + 1.5, 1);
    expect(x).toBeGreaterThan(wallX);
  });
  it("properti: jalan acak ribuan langkah tidak pernah berakhir di dalam rintangan atau di luar dunia", () => {
    let s = 17;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647) * 2 - 1;
    let p: [number, number] = [...CEO_START];
    for (let i = 0; i < 4000; i++) {
      p = moveWithCollision(p, [rnd() * 0.6, rnd() * 0.6]);
      expect(collides(p[0], p[1], CEO_RADIUS, OBSTACLES)).toBe(false);
    }
  });
});

describe("kecepatan dari masukan", () => {
  it("maju pada yaw 0 menuju -z; kanan menuju +x", () => {
    const [vx, vz] = velocityFromInput({ forward: 1, right: 0 }, 0, 3);
    expect(vx).toBeCloseTo(0, 6);
    expect(vz).toBeCloseTo(-3, 6);
    const [rx, rz] = velocityFromInput({ forward: 0, right: 1 }, 0, 3);
    expect(rx).toBeCloseTo(3, 6);
    expect(rz).toBeCloseTo(0, 6);
  });
  it("diagonal tidak lebih cepat; tanpa masukan diam; mengikuti yaw", () => {
    const d = velocityFromInput({ forward: 1, right: 1 }, 0, 3);
    expect(Math.hypot(d[0], d[1])).toBeCloseTo(3, 6);
    expect(velocityFromInput({ forward: 0, right: 0 }, 1.2, 3)).toEqual([0, 0]);
    const [x, z] = velocityFromInput({ forward: 1, right: 0 }, Math.PI / 2, 2);   // menghadap -x
    expect(x).toBeCloseTo(-2, 6);
    expect(z).toBeCloseTo(0, 6);
  });
});

describe("interaksi", () => {
  const avatars = [{ role: "developer", position: [-10, -2] as [number, number] }, { role: "qa", position: [-8, -2] as [number, number] }];
  it("tidak ada objek dalam jangkauan di ruang kosong", () => {
    expect(nearestInteractable([0, 12], avatars)).toBeNull();
  });
  it("memilih agent terdekat dalam jangkauan", () => {
    const n = nearestInteractable([-9.4, -0.9], avatars);
    expect(n).toMatchObject({ kind: "agent", role: "developer" });
  });
  it("tempat penting menaut ke halamannya", () => {
    const p = PLACES.find((x) => x.id === "approvals")!;
    const n = nearestInteractable([p.position[0], p.position[1] + 0.5], []);
    expect(n).toMatchObject({ kind: "place", id: "approvals", href: "/approvals" });
    expect(n!.distance).toBeLessThanOrEqual(INTERACT_RADIUS);
  });
  it("agent yang lebih dekat mengalahkan tempat yang lebih jauh", () => {
    const p = PLACES.find((x) => x.id === "approvals")!;
    const pos: [number, number] = [p.position[0], p.position[1] + 1.2];                   // 1,2 m dari tempat
    const n = nearestInteractable(pos, [{ role: "manager", position: [pos[0] + 0.4, pos[1]] }]);   // agent 0,4 m
    expect(n).toMatchObject({ kind: "agent", role: "manager" });
  });
});
