import { describe, expect, it } from "vitest";
import {
  chooseMode, layoutAvatars, loungeSeat, poseOf, ROOMS, shouldApply, toneOf, workSeat, WORKROOM, type AgentSnapshot, type RoomId,
} from "./model";

const ROLES = Object.keys(WORKROOM);
const DEPT: Record<string, string> = { manager: "coordination" };
const snap = (over: Record<string, Partial<AgentSnapshot>> = {}): AgentSnapshot[] =>
  ROLES.map((role) => ({
    role, department: DEPT[role] ?? (["analyst", "developer", "qa", "reviewer", "reporter"].includes(role) ? "engineering" : "marketing"),
    status: "idle", queued: 0, current_task_id: null, current_task_title: null, ...over[role],
  }));

const inside = (room: RoomId, [x, z]: [number, number]) => {
  const r = ROOMS[room];
  return Math.abs(x - r.center[0]) <= r.size[0] / 2 && Math.abs(z - r.center[1]) <= r.size[1] / 2;
};

describe("pose dan tone mengikuti status backend", () => {
  it.each([
    ["idle", "idle", "idle"], ["planning", "working", "ok"], ["working", "working", "ok"], ["testing", "working", "ok"], ["reviewing", "working", "ok"],
    ["researching", "working", "ok"], ["prospecting", "working", "ok"], ["creating_content", "working", "ok"], ["client_followup", "working", "ok"],
    ["awaiting_approval", "waiting", "warn"], ["blocked", "blocked", "warn"], ["error", "error", "bad"], ["completed", "done", "ok"],
  ])("%s -> %s/%s", (status, pose, tone) => {
    expect(poseOf(status)).toBe(pose);
    expect(toneOf(status)).toBe(tone);
  });

  it("status tak dikenal dianggap idle, bukan bekerja", () => {
    expect(poseOf("ngawur")).toBe("idle");
  });
});

describe("penempatan avatar", () => {
  it("semua agent idle berada di Lounge (tidak ada kesan bekerja)", () => {
    const av = layoutAvatars(snap());
    expect(av).toHaveLength(ROLES.length);
    expect(av.every((a) => a.room === "lounge" && a.pose === "idle" && inside("lounge", a.position))).toBe(true);
  });

  it("agent yang bekerja berada di ruang kerjanya sesuai role", () => {
    const av = layoutAvatars(snap({ developer: { status: "working" }, market_research: { status: "researching" }, manager: { status: "planning" } }));
    const get = (r: string) => av.find((a) => a.role === r)!;
    expect(get("developer").room).toBe("engineering");
    expect(get("market_research").room).toBe("marketing");
    expect(get("manager").room).toBe("meeting");
    expect(get("qa").room).toBe("lounge");
    for (const a of av) expect(inside(a.room, a.position), a.role).toBe(true);
  });

  it("menunggu approval, terblokir, dan error tetap di ruang kerja tetapi bukan pose bekerja", () => {
    const av = layoutAvatars(snap({ qa: { status: "awaiting_approval" }, reviewer: { status: "blocked" }, analyst: { status: "error" } }));
    expect(av.filter((a) => a.room === "engineering").map((a) => [a.role, a.pose]).sort()).toEqual([["analyst", "error"], ["qa", "waiting"], ["reviewer", "blocked"]]);
  });

  it("tidak ada dua avatar pada titik yang sama di ruangan yang sama", () => {
    const all = layoutAvatars(snap(Object.fromEntries(ROLES.map((r) => [r, { status: "working" }]))));
    const keys = all.map((a) => `${a.room}:${a.position.join(",")}`);
    expect(new Set(keys).size).toBe(keys.length);
    for (const a of all) expect(inside(a.room, a.position), a.role).toBe(true);
  });

  it("kursi tetap: posisi sebuah role tidak bergeser ketika agent lain berubah status", () => {
    const before = layoutAvatars(snap({ developer: { status: "working" } }));
    const after = layoutAvatars(snap({ developer: { status: "working" }, qa: { status: "working" }, analyst: { status: "working" }, manager: { status: "planning" } }));
    const pos = (av: ReturnType<typeof layoutAvatars>, r: string) => av.find((a) => a.role === r)!.position;
    expect(pos(after, "developer")).toEqual(pos(before, "developer"));
    expect(pos(after, "developer")).toEqual(workSeat("developer"));
    expect(pos(after, "reporter")).toEqual(loungeSeat("reporter")); // yang tetap idle tidak berpindah
    expect(pos(before, "reporter")).toEqual(pos(after, "reporter"));
  });

  it("membawa id dan judul task dari backend, serta antrean", () => {
    const [a] = layoutAvatars([{ role: "developer", department: "engineering", status: "working", queued: 3, current_task_id: "t1", current_task_title: "Bangun" }]);
    expect(a).toMatchObject({ taskId: "t1", taskTitle: "Bangun", queued: 3, status: "working" });
  });
});

describe("konsistensi setelah reconnect", () => {
  it("tampilan murni fungsi dari potret: potret yang sama memberi hasil yang sama, apa pun riwayat sebelumnya", () => {
    const latest = snap({ developer: { status: "working", current_task_id: "x" }, qa: { status: "error" } });
    const fresh = layoutAvatars(latest);
    // simulasi: klien melewatkan beberapa event dan melihat potret antara yang berbeda, lalu memuat ulang potret terbaru
    layoutAvatars(snap({ developer: { status: "testing" } }));
    layoutAvatars(snap({ qa: { status: "completed" } }));
    expect(layoutAvatars(latest)).toEqual(fresh);
  });

  it("respons lama tidak menimpa respons yang lebih baru", () => {
    expect(shouldApply(0, 1)).toBe(true);
    expect(shouldApply(5, 4)).toBe(false);
    expect(shouldApply(5, 5)).toBe(false);
    expect(shouldApply(5, 6)).toBe(true);
  });
});

describe("mode tampilan dan fallback 2D", () => {
  it("tanpa WebGL selalu 2D, termasuk jika dipaksa 3D", () => {
    for (const pref of ["auto", "3d", "2d"] as const) expect(chooseMode(pref, { webgl: false, reducedMotion: false })).toBe("2d");
  });
  it("auto memilih 3D hanya jika mampu dan tidak meminta gerak berkurang", () => {
    expect(chooseMode("auto", { webgl: true, reducedMotion: false })).toBe("3d");
    expect(chooseMode("auto", { webgl: true, reducedMotion: true })).toBe("2d");
  });
  it("pilihan manual dihormati jika perangkat mampu", () => {
    expect(chooseMode("3d", { webgl: true, reducedMotion: true })).toBe("3d");
    expect(chooseMode("2d", { webgl: true, reducedMotion: false })).toBe("2d");
  });
});
