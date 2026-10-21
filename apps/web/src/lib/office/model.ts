// Logika kantor virtual TANPA rendering (Bagian 7.4: pisahkan komponen 3D dari logika bisnis).
// Seluruh keadaan visual adalah fungsi murni dari potret backend (/api/dashboard): tidak ada status yang disimpan atau diperkirakan di klien,
// sehingga tampilan yang dimuat ulang setelah reconnect selalu sama dengan backend.

export type RoomId = "ceo" | "engineering" | "marketing" | "meeting" | "lounge";
export type Department = "coordination" | "engineering" | "marketing";
export type Tone = "ok" | "warn" | "bad" | "idle";
export type Pose = "working" | "waiting" | "blocked" | "error" | "done" | "idle";

export type AgentSnapshot = {
  role: string;
  department: string;
  status: string;
  queued: number;
  current_task_id: string | null;
  current_task_title: string | null;
};

export type Room = { id: RoomId; center: [number, number]; size: [number, number]; color: string };

// Denah (satuan meter, sumbu x ke kanan, z ke arah penonton). Warna: biru elektrik, ungu, magenta.
export const ROOMS: Record<RoomId, Room> = {
  ceo: { id: "ceo", center: [0, -7], size: [8, 5], color: "#a855f7" },
  engineering: { id: "engineering", center: [-10, -1], size: [9, 7], color: "#00b8ff" },
  marketing: { id: "marketing", center: [10, -1], size: [9, 7], color: "#ff2bd6" },
  meeting: { id: "meeting", center: [-8, 10.5], size: [7, 5], color: "#7c5cff" },
  lounge: { id: "lounge", center: [8, 10.5], size: [9, 5], color: "#2dd4bf" },
};

export const ROOM_ORDER: RoomId[] = ["ceo", "engineering", "marketing", "meeting", "lounge"];

// Ruang kerja tiap role (Bagian 7.2). Manager bekerja di Meeting Room; ruang CEO tidak berisi agent.
export const WORKROOM: Record<string, RoomId> = {
  manager: "meeting",
  analyst: "engineering", developer: "engineering", qa: "engineering", reviewer: "engineering", reporter: "engineering",
  market_research: "marketing", lead_generation: "marketing", content_promotion: "marketing", sales_client_relations: "marketing",
};

export const DEPARTMENT_COLOR: Record<string, string> = { coordination: "#a855f7", engineering: "#00b8ff", marketing: "#ff2bd6" };

const WORKING = new Set(["planning", "working", "testing", "reviewing", "researching", "prospecting", "creating_content", "client_followup"]);

export function poseOf(status: string): Pose {
  if (WORKING.has(status)) return "working";
  switch (status) {
    case "awaiting_approval": return "waiting";
    case "blocked": return "blocked";
    case "error": return "error";
    case "completed": return "done";
    default: return "idle";
  }
}

export function toneOf(status: string): Tone {
  switch (poseOf(status)) {
    case "working": case "done": return "ok";
    case "waiting": case "blocked": return "warn";
    case "error": return "bad";
    default: return "idle";
  }
}

export type Avatar = {
  role: string;
  department: string;
  status: string;
  pose: Pose;
  tone: Tone;
  room: RoomId;      // ruangan tempat avatar BERADA saat ini
  workroom: RoomId;  // ruang kerja role ini
  position: [number, number]; // koordinat (x, z) pada denah
  queued: number;
  taskId: string | null;
  taskTitle: string | null;
};

// Urutan tetap per role dalam ruangan agar posisi stabil antar pembaruan.
const SEAT_ORDER = Object.keys(WORKROOM);

function seatsIn(room: RoomId, roles: string[], role: string): [number, number] {
  const r = ROOMS[room];
  const i = roles.indexOf(role);
  const cols = Math.max(1, Math.min(roles.length, room === "lounge" ? 5 : 3));
  const rows = Math.ceil(roles.length / cols);
  const col = i % cols;
  const row = Math.floor(i / cols);
  const gapX = (r.size[0] - 2) / Math.max(1, cols - 1 || 1);
  const gapZ = rows > 1 ? (r.size[1] - 2.4) / (rows - 1) : 0;
  const x = cols === 1 ? r.center[0] : r.center[0] - (r.size[0] - 2) / 2 + col * gapX;
  const z = rows === 1 ? r.center[1] : r.center[1] - (r.size[1] - 2.4) / 2 + row * gapZ;
  return [Math.round(x * 100) / 100, Math.round(z * 100) / 100];
}

/**
 * Menempatkan avatar dari potret agent backend.
 * Aturan (Bagian 7.2): agent tanpa task aktif (idle) berada di Lounge; Lounge tidak boleh memberi kesan agent sedang bekerja.
 * Agent yang menunggu approval, terblokir, atau error tetap di ruang kerjanya dengan pose yang berbeda dari "bekerja".
 */
export function layoutAvatars(agents: AgentSnapshot[]): Avatar[] {
  const byRole = new Map(agents.map((a) => [a.role, a]));
  const roles = SEAT_ORDER.filter((r) => byRole.has(r)).concat(agents.map((a) => a.role).filter((r) => !SEAT_ORDER.includes(r)));
  const placed = roles.map((role) => {
    const a = byRole.get(role)!;
    const workroom = WORKROOM[role] ?? "lounge";
    const pose = poseOf(a.status);
    return { a, workroom, room: (pose === "idle" ? "lounge" : workroom) as RoomId, pose };
  });
  const inRoom = (room: RoomId) => placed.filter((p) => p.room === room).map((p) => p.a.role);
  const sortedLounge = inRoom("lounge");
  return placed.map(({ a, workroom, room, pose }) => ({
    role: a.role,
    department: a.department,
    status: a.status,
    pose,
    tone: toneOf(a.status),
    room,
    workroom,
    position: seatsIn(room, room === "lounge" ? sortedLounge : inRoom(room), a.role),
    queued: a.queued,
    taskId: a.current_task_id,
    taskTitle: a.current_task_title,
  }));
}

// ---------------------------------------------------------------- mode tampilan (3D atau fallback 2D)

export type ModePref = "auto" | "3d" | "2d";
export type Capabilities = { webgl: boolean; reducedMotion: boolean };

/** 3D hanya dipakai jika perangkat mampu; pilihan manual "3d" tetap ditolak jika WebGL tidak tersedia. */
export function chooseMode(pref: ModePref, caps: Capabilities): "3d" | "2d" {
  if (!caps.webgl) return "2d";
  if (pref === "2d") return "2d";
  if (pref === "3d") return "3d";
  return caps.reducedMotion ? "2d" : "3d";
}

export function isModePref(v: unknown): v is ModePref {
  return v === "auto" || v === "3d" || v === "2d";
}

// ---------------------------------------------------------------- potret terbaru menang (tahan balapan jaringan dan reconnect)

/** Respons yang diminta lebih lama tidak boleh menimpa respons yang lebih baru. */
export function shouldApply(latestApplied: number, seq: number): boolean {
  return seq > latestApplied;
}
