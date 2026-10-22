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
  ceo: { id: "ceo", center: [0, -7], size: [8, 5], color: "#8b5cf6" },
  engineering: { id: "engineering", center: [-10, -1], size: [9, 7], color: "#3b82f6" },
  marketing: { id: "marketing", center: [10, -1], size: [9, 7], color: "#d946ef" },
  meeting: { id: "meeting", center: [-8, 10.5], size: [7, 5], color: "#7c5cff" },
  lounge: { id: "lounge", center: [8, 10.5], size: [9, 5], color: "#2dd4bf" },
};

export const ROOM_ORDER: RoomId[] = ["ceo", "engineering", "marketing", "meeting", "lounge"];

// Ruang kerja tiap role (Bagian 7.2). Manager bekerja di Meeting Room; ruang CEO tidak berisi agent.
export const WORKROOM: Record<string, RoomId> = {
  manager: "meeting",
  analyst: "engineering", developer: "engineering", qa: "engineering", reviewer: "engineering", reporter: "engineering",
  market_research: "marketing", lead_generation: "marketing", content_promotion: "marketing", sales_client_relations: "marketing",
  seo_specialist: "marketing", marketing_analytics: "marketing",
};

export const DEPARTMENT_COLOR: Record<string, string> = { coordination: "#8b5cf6", engineering: "#3b82f6", marketing: "#d946ef" };

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

/** Klip animasi karakter untuk sebuah pose. Berjalan selalu "walk"; bekerja dan idle duduk (di meja atau sofa Lounge). */
export function clipFor(pose: Pose, walking: boolean): string {
  if (walking) return "walk";
  switch (pose) {
    case "working": case "idle": return "sit";
    case "waiting": return "interact-right"; // mengangkat tangan
    case "error": return "emote-no";
    case "done": return "emote-yes";
    default: return "idle"; // blocked
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

// Urutan tetap per role: kursi kerja dan kursi Lounge tiap role TETAP (tidak bergeser saat agent lain datang atau pergi),
// sehingga meja tidak berpindah dan avatar hanya berjalan antara kursi kerja dan kursi Lounge-nya.
const SEAT_ORDER = Object.keys(WORKROOM);

function gridSeat(room: RoomId, count: number, index: number): [number, number] {
  const r = ROOMS[room];
  const cols = Math.max(1, Math.min(count, room === "lounge" ? 5 : 3));
  const rows = Math.ceil(count / cols);
  const col = index % cols;
  const row = Math.floor(index / cols);
  const gapX = cols > 1 ? (r.size[0] - 2) / (cols - 1) : 0;
  const gapZ = rows > 1 ? (r.size[1] - 2.4) / (rows - 1) : 0;
  const x = cols === 1 ? r.center[0] : r.center[0] - (r.size[0] - 2) / 2 + col * gapX;
  const z = rows === 1 ? r.center[1] : r.center[1] - (r.size[1] - 2.4) / 2 + row * gapZ;
  return [Math.round(x * 100) / 100, Math.round(z * 100) / 100];
}

const roundPoint = ([x, z]: [number, number]): [number, number] => [Math.round(x * 100) / 100, Math.round(z * 100) / 100];

/** Kursi kerja tetap sebuah role di ruang kerjanya. Manager berdiri di sisi depan meja rapat. */
export function workSeat(role: string): [number, number] {
  const room = WORKROOM[role] ?? "lounge";
  if (room === "meeting") return roundPoint([ROOMS.meeting.center[0], ROOMS.meeting.center[1] + 1.2]);
  const mates = SEAT_ORDER.filter((r) => WORKROOM[r] === room);
  return gridSeat(room, mates.length, Math.max(0, mates.indexOf(role)));
}

/** Kursi Lounge tetap sebuah role (Lounge menampung semua role bila semuanya idle). */
export function loungeSeat(role: string): [number, number] {
  return gridSeat("lounge", SEAT_ORDER.length, Math.max(0, SEAT_ORDER.indexOf(role)));
}

/**
 * Menempatkan avatar dari potret agent backend.
 * Aturan (Bagian 7.2): agent tanpa task aktif (idle) berada di Lounge; Lounge tidak boleh memberi kesan agent sedang bekerja.
 * Agent yang menunggu approval, terblokir, atau error tetap di ruang kerjanya dengan pose yang berbeda dari "bekerja".
 */
export function layoutAvatars(agents: AgentSnapshot[]): Avatar[] {
  return agents.map((a) => {
    const workroom = WORKROOM[a.role] ?? "lounge";
    const pose = poseOf(a.status);
    const room: RoomId = pose === "idle" ? "lounge" : workroom;
    return {
      role: a.role,
      department: a.department,
      status: a.status,
      pose,
      tone: toneOf(a.status),
      room,
      workroom,
      position: room === "lounge" ? loungeSeat(a.role) : workSeat(a.role),
      queued: a.queued,
      taskId: a.current_task_id,
      taskTitle: a.current_task_title,
    };
  });
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
