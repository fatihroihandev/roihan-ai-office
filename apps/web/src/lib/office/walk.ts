// Logika mode jalan CEO (tanpa rendering): tabrakan dengan dinding dan perabot, kecepatan dari masukan, dan objek yang dapat diajak berinteraksi.
// Posisi CEO hanya hidup di peramban ini; tidak dikirim ke backend dan tidak mengubah status agent mana pun.
import { ROOMS, workSeat, loungeSeat, WORKROOM, type Avatar } from "./model";

export type Box = [number, number, number, number]; // [minX, minZ, maxX, maxZ]
export type Point = [number, number];

export const CEO_RADIUS = 0.34;
export const BOUNDS: Box = [-18.2, -12.2, 18.2, 15.2];
export const CEO_START: Point = [0, ROOMS.ceo.center[1] + 2.9];
export const WALK_SPEED = 3.0;
export const RUN_SPEED = 5.6;
const WALL = 0.16; // setengah tebal dinding

const centered = (cx: number, cz: number, w: number, d: number): Box => [cx - w / 2, cz - d / 2, cx + w / 2, cz + d / 2];

/** Dinding belakang, kiri, dan kanan tiap ruangan; sisi depan terbuka sebagai pintu. */
function roomWalls(): Box[] {
  return Object.values(ROOMS).flatMap((r) => {
    const [cx, cz] = r.center;
    const [w, d] = r.size;
    return [
      [cx - w / 2, cz - d / 2 - WALL, cx + w / 2, cz - d / 2 + WALL],
      [cx - w / 2 - WALL, cz - d / 2, cx - w / 2 + WALL, cz + d / 2],
      [cx + w / 2 - WALL, cz - d / 2, cx + w / 2 + WALL, cz + d / 2],
    ] as Box[];
  });
}

/** Perabot: meja kerja + kursi, sofa Lounge, meja rapat, rak server, meja CEO, dan tanaman besar. */
function furniture(): Box[] {
  const out: Box[] = [];
  for (const role of Object.keys(WORKROOM)) {
    if (WORKROOM[role] === "meeting") continue;
    const [x, z] = workSeat(role);
    out.push(centered(x, z - 0.8, 1.7, 0.85), centered(x, z + 0.25, 0.7, 0.7));
  }
  for (const role of Object.keys(WORKROOM)) {
    const [x, z] = loungeSeat(role);
    out.push(centered(x, z + 0.05, 1.3, 1.0));
  }
  const [mx, mz] = ROOMS.meeting.center;
  out.push(centered(mx, mz - 0.9, 2.7, 2.7));
  const [ex, ez] = ROOMS.engineering.center;
  for (const dx of [-3.6, -2.6, 3.6]) out.push(centered(ex + dx, ez - 3.0, 0.9, 0.8));
  const [cx, cz] = ROOMS.ceo.center;
  out.push(centered(cx, cz + 0.8, 3.3, 1.05));
  return out;
}

export const OBSTACLES: Box[] = [...roomWalls(), ...furniture()];

/** Apakah lingkaran (x, z, r) menyentuh salah satu kotak atau keluar dari batas dunia? */
export function collides(x: number, z: number, r: number, boxes: Box[] = OBSTACLES): boolean {
  if (x - r < BOUNDS[0] || x + r > BOUNDS[2] || z - r < BOUNDS[1] || z + r > BOUNDS[3]) return true;
  return boxes.some(([a, b, c, d]) => {
    const nx = Math.max(a, Math.min(x, c));
    const nz = Math.max(b, Math.min(z, d));
    return (x - nx) ** 2 + (z - nz) ** 2 < r * r;
  });
}

/** Gerak dengan tabrakan per sumbu: menyusuri dinding alih-alih berhenti, dan tidak pernah berakhir di dalam rintangan. */
export function moveWithCollision(pos: Point, delta: Point, r = CEO_RADIUS, boxes: Box[] = OBSTACLES): Point {
  let [x, z] = pos;
  const steps = Math.max(1, Math.ceil(Math.hypot(delta[0], delta[1]) / 0.15)); // langkah kecil: tidak menembus dinding tipis
  const dx = delta[0] / steps;
  const dz = delta[1] / steps;
  for (let i = 0; i < steps; i++) {
    if (!collides(x + dx, z, r, boxes)) x += dx;
    if (!collides(x, z + dz, r, boxes)) z += dz;
  }
  return [x, z];
}

/** Kecepatan dunia dari masukan (maju/mundur, kanan/kiri) relatif terhadap arah kamera (yaw 0 = menghadap -z). */
export function velocityFromInput(input: { forward: number; right: number }, yaw: number, speed: number): Point {
  const len = Math.hypot(input.forward, input.right);
  if (len === 0) return [0, 0];
  const f = input.forward / len;
  const s = input.right / len;
  return [(-Math.sin(yaw) * f + Math.cos(yaw) * s) * speed, (-Math.cos(yaw) * f - Math.sin(yaw) * s) * speed];
}

// ---------------------------------------------------------------- interaksi

export type Place = { id: string; position: Point; href: string };
const [CX, CZ] = ROOMS.ceo.center;
const [EX, EZ] = ROOMS.engineering.center;
const [MX, MZ] = ROOMS.marketing.center;
const [TX, TZ] = ROOMS.meeting.center;
export const PLACES: Place[] = [
  { id: "approvals", position: [CX, CZ + 2.1], href: "/approvals" },
  { id: "engineering", position: [EX - 3.1, EZ - 2.0], href: "/tasks" },
  { id: "marketing", position: [MX, MZ - 2.2], href: "/marketing" },
  { id: "meeting", position: [TX, TZ + 0.9], href: "/projects" },
];
export const INTERACT_RADIUS = 2.3;

export type Nearby =
  | { kind: "agent"; role: string; distance: number }
  | { kind: "place"; id: string; href: string; distance: number };

/** Objek terdekat dalam jangkauan: agent (di posisi avatarnya saat ini) atau tempat penting. Null jika tidak ada. */
export function nearestInteractable(pos: Point, avatars: Pick<Avatar, "role" | "position">[]): Nearby | null {
  let best: Nearby | null = null;
  const consider = (n: Nearby) => {
    if (n.distance <= INTERACT_RADIUS && (best === null || n.distance < best.distance)) best = n;
  };
  for (const a of avatars) consider({ kind: "agent", role: a.role, distance: Math.hypot(a.position[0] - pos[0], a.position[1] - pos[1]) });
  for (const p of PLACES) consider({ kind: "place", id: p.id, href: p.href, distance: Math.hypot(p.position[0] - pos[0], p.position[1] - pos[1]) });
  return best;
}
