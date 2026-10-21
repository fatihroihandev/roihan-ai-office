"use client";

// Render 3D saja. Tidak ada logika bisnis di sini: posisi, pose, dan warna datang dari lib/office/model (potret backend).
// Yang dilakukan di sini murni visual: avatar berjalan menuju kursi yang ditentukan model, meja menyala sesuai pose, dan seterusnya.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, type RefObject } from "react";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { useLogoTexture, useWordmarkTexture } from "@/components/brand/useBrandTextures";
import { CeoRig, ModelBoundary, RobotWalker, type WalkRigProps } from "@/components/office/scene/models";
import { DEPARTMENT_COLOR, loungeSeat, ROOM_ORDER, ROOMS, workSeat, WORKROOM, type Avatar, type Pose, type RoomId } from "@/lib/office/model";

const TONE_COLOR = { ok: "#39ff88", warn: "#ffb020", bad: "#ff3860", idle: "#4b5563" } as const;
const WALK_SPEED = 3.0; // meter per detik
const ROLES = Object.keys(WORKROOM);

export type HologramLine = { text: string; color: string };
export type Office3DProps = {
  avatars: Avatar[];
  selected: string | null;
  onSelect: (role: string) => void;
  hologram: HologramLine[];
  roomLabels: Record<RoomId, string>;
  roleLabels: Record<string, string>;
  statusLabels: Record<string, string>;
  onFail: () => void;
  quality: "high" | "low";
  ceo: Pick<WalkRigProps, "walking" | "start" | "view" | "label" | "onNearby" | "onInteract" | "onToggleView" | "onExit">;
};

// ------------------------------------------------------------------ tekstur

function labelTexture(lines: HologramLine[], w = 512, h = 128 * lines.length): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, w, h);
  const lh = h / Math.max(1, lines.length);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  lines.forEach((l, i) => {
    ctx.font = `bold ${Math.round(lh * 0.56)}px ui-monospace, Consolas, monospace`;
    ctx.fillStyle = l.color;
    ctx.shadowColor = l.color;
    ctx.shadowBlur = 14;
    ctx.fillText(l.text, w / 2, lh * (i + 0.5), w - 24);
  });
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function glowTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(255,255,255,0.9)");
  grad.addColorStop(0.45, "rgba(255,255,255,0.25)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

function SpriteLabel({ lines, position, scale }: { lines: HologramLine[]; position: [number, number, number]; scale: [number, number] }) {
  const key = lines.map((l) => `${l.text}|${l.color}`).join("§");
  const tex = useMemo(() => labelTexture(lines), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <sprite position={position} scale={[scale[0], scale[1], 1]}>
      <spriteMaterial map={tex} transparent depthWrite={false} toneMapped={false} />
    </sprite>
  );
}

function TextPlane({ lines, position, size }: { lines: HologramLine[]; position: [number, number, number]; size: [number, number] }) {
  const key = lines.map((l) => `${l.text}|${l.color}`).join("§");
  const tex = useMemo(() => labelTexture(lines), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <mesh position={position}>
      <planeGeometry args={size} />
      <meshBasicMaterial map={tex} transparent depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

// ------------------------------------------------------------------ papan merek Roihan Technologies

/** Logo "R" bercahaya + tulisan ROIHAN / TECHNOLOGIES / tagline sesuai berkas identitas. */
function BrandSign({ position, scale = 1, tagline = true }: { position: [number, number, number]; scale?: number; tagline?: boolean }) {
  const logo = useLogoTexture();
  const word = useWordmarkTexture(tagline);
  const wordH = tagline ? 3.5 : 2.5;
  return (
    <group position={position} scale={scale}>
      {logo && (
        <mesh position={[-4.6, 0, 0]}>
          <planeGeometry args={[3.6, 3.6]} />
          <meshBasicMaterial map={logo} transparent depthWrite={false} toneMapped={false} />
        </mesh>
      )}
      {word && (
        <mesh position={[2.5, 0, 0]}>
          <planeGeometry args={[10, wordH]} />
          <meshBasicMaterial map={word} transparent depthWrite={false} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

// ------------------------------------------------------------------ kamera

function Controls({ focus, enabled }: { focus: [number, number] | null; enabled: boolean }) {
  const { camera, gl } = useThree();
  const ref = useRef<OrbitControls | null>(null);
  useEffect(() => {
    const c = new OrbitControls(camera, gl.domElement);
    c.enableDamping = true;
    c.enablePan = false;
    c.maxPolarAngle = Math.PI / 2.15;
    c.minDistance = 7;
    c.maxDistance = 46;
    c.target.set(0, 0, 2);
    ref.current = c;
    return () => c.dispose();
  }, [camera, gl]);
  const goal = useMemo(() => new THREE.Vector3(), []);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    c.enabled = enabled;
    if (enabled) {
      camera.position.set(0, 18, 24); // kembali ke sudut pandang atas saat keluar dari mode jalan
      c.target.set(0, 0, 2);
    }
  }, [enabled, camera]);
  useFrame((_, dt) => {
    const c = ref.current;
    if (!c || !enabled) return;
    goal.set(focus ? focus[0] * 0.6 : 0, focus ? 0.8 : 0, focus ? focus[1] * 0.6 + 1 : 2); // mengikuti agent terpilih secara halus
    c.target.lerp(goal, 1 - Math.exp(-3 * dt));
    c.update();
  });
  return null;
}

// ------------------------------------------------------------------ latar kota

function makeSkyline() {
  let seed = 7;
  const rnd = () => {
    seed = (seed * 16807) % 2147483647; // deterministik: tampilan sama setiap dimuat
    return seed / 2147483647;
  };
  const buildings = Array.from({ length: 52 }, (_, i) => ({ x: -38 + i * 1.5, h: 3 + rnd() * 17, w: 0.9 + rnd() * 0.8, hue: ["#3b82f6", "#8b5cf6", "#d946ef"][Math.floor(rnd() * 3)] }));
  const windows = Array.from({ length: 520 }, () => {
    const b = buildings[Math.floor(rnd() * buildings.length)];
    return { x: b.x + (rnd() - 0.5) * (b.w - 0.25), y: 0.6 + rnd() * (b.h - 1), warm: rnd() > 0.6 };
  });
  return { buildings, windows };
}

function Skyline() {
  const { buildings, windows } = useMemo(() => makeSkyline(), []);
  const inst = useRef<THREE.InstancedMesh>(null);
  useEffect(() => {
    const m = inst.current;
    if (!m) return;
    const d = new THREE.Object3D();
    const col = new THREE.Color();
    windows.forEach((w, i) => {
      d.position.set(w.x, w.y, 0.52);
      d.scale.set(0.12, 0.16, 1);
      d.updateMatrix();
      m.setMatrixAt(i, d.matrix);
      m.setColorAt(i, col.set(w.warm ? "#ffd27a" : "#7fdcff"));
    });
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }, [windows]);
  return (
    <group position={[0, 0, -24]}>
      {buildings.map((b, i) => (
        <mesh key={i} position={[b.x, b.h / 2, 0]}>
          <boxGeometry args={[b.w, b.h, 1]} />
          <meshStandardMaterial color="#0b1022" emissive={b.hue} emissiveIntensity={0.1} />
        </mesh>
      ))}
      <instancedMesh ref={inst} args={[undefined, undefined, windows.length]}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial toneMapped={false} transparent opacity={0.85} />
      </instancedMesh>
    </group>
  );
}

function GlassWall() {
  return (
    <group position={[0, 0, -15.5]}>
      <mesh position={[0, 4.2, 0]}>
        <planeGeometry args={[46, 8.4]} />
        <meshBasicMaterial color="#5b7cff" transparent opacity={0.05} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      {Array.from({ length: 9 }, (_, i) => (
        <mesh key={i} position={[-23 + i * 5.75, 4.2, 0]}>
          <boxGeometry args={[0.1, 8.4, 0.1]} />
          <meshBasicMaterial color="#1d3b8a" toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 8.4, 0]}>
        <boxGeometry args={[46, 0.12, 0.12]} />
        <meshBasicMaterial color="#3b82f6" toneMapped={false} />
      </mesh>
    </group>
  );
}

function Particles() {
  const ref = useRef<THREE.Points>(null);
  const data = useMemo(() => {
    let seed = 11;
    const rnd = () => {
      seed = (seed * 16807) % 2147483647;
      return seed / 2147483647;
    };
    const pos = new Float32Array(180 * 3);
    for (let i = 0; i < 180; i++) {
      pos[i * 3] = (rnd() - 0.5) * 44;
      pos[i * 3 + 1] = rnd() * 9;
      pos[i * 3 + 2] = (rnd() - 0.5) * 34;
    }
    return pos;
  }, []);
  useFrame((_, dt) => {
    const p = ref.current?.geometry.attributes.position as THREE.BufferAttribute | undefined;
    if (!p) return;
    for (let i = 0; i < p.count; i++) {
      let y = p.getY(i) + dt * 0.18;
      if (y > 9) y = 0;
      p.setY(i, y);
    }
    p.needsUpdate = true;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[data, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#7fdcff" size={0.07} transparent opacity={0.55} depthWrite={false} sizeAttenuation />
    </points>
  );
}

// ------------------------------------------------------------------ ruangan dan perabot

function Plant({ position, s = 1 }: { position: [number, number, number]; s?: number }) {
  return (
    <group position={position} scale={s}>
      <mesh position={[0, 0.25, 0]}>
        <cylinderGeometry args={[0.28, 0.2, 0.5, 14]} />
        <meshStandardMaterial color="#141a33" metalness={0.5} roughness={0.4} />
      </mesh>
      {[0, 1, 2, 3, 4].map((i) => (
        <mesh key={i} position={[Math.sin(i * 1.26) * 0.14, 0.85, Math.cos(i * 1.26) * 0.14]} rotation={[Math.cos(i * 1.26) * 0.35, 0, -Math.sin(i * 1.26) * 0.35]}>
          <coneGeometry args={[0.13, 0.85, 7]} />
          <meshStandardMaterial color="#1f8f5f" emissive="#0b4d33" emissiveIntensity={0.6} />
        </mesh>
      ))}
    </group>
  );
}

function RoomShell({ id, name, glow, ceiling }: { id: RoomId; name: string; glow: THREE.Texture; ceiling: boolean }) {
  const r = ROOMS[id];
  const [w, d] = r.size;
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(w, 0.12, d)), [w, d]);
  useEffect(() => () => edges.dispose(), [edges]);
  const raised = id === "ceo" ? 0.35 : 0;
  const pane = (pos: [number, number, number], size: [number, number, number]) => (
    <group position={pos}>
      <mesh>
        <boxGeometry args={size} />
        <meshPhysicalMaterial color={r.color} transparent opacity={0.07} roughness={0.05} metalness={0.1} depthWrite={false} />
      </mesh>
      <mesh position={[0, size[1] / 2, 0]}>
        <boxGeometry args={[size[0] + 0.02, 0.05, size[2] + 0.02]} />
        <meshBasicMaterial color={r.color} toneMapped={false} />
      </mesh>
      <mesh position={[0, -size[1] / 2, 0]}>
        <boxGeometry args={[size[0] + 0.02, 0.05, size[2] + 0.02]} />
        <meshBasicMaterial color={r.color} toneMapped={false} />
      </mesh>
    </group>
  );
  return (
    <group position={[r.center[0], raised, r.center[1]]}>
      <mesh position={[0, -0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[w + 5, d + 5]} />
        <meshBasicMaterial map={glow} color={r.color} transparent opacity={0.35} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0.02, 0]} receiveShadow>
        <boxGeometry args={[w, 0.12, d]} />
        <meshStandardMaterial color="#0a1226" metalness={0.85} roughness={0.22} emissive={r.color} emissiveIntensity={0.06} />
      </mesh>
      <lineSegments geometry={edges} position={[0, 0.02, 0]}>
        <lineBasicMaterial color={r.color} toneMapped={false} />
      </lineSegments>
      {pane([0, 1.6, -d / 2], [w, 3.2, 0.06])}
      {pane([-w / 2, 1.6, 0], [0.06, 3.2, d])}
      {pane([w / 2, 1.6, 0], [0.06, 3.2, d])}
      {ceiling && [-1, 1].map((sx) => (
        <mesh key={sx} position={[sx * w * 0.28, 3.08, 0]}>
          <boxGeometry args={[w * 0.24, 0.04, 0.22]} />
          <meshBasicMaterial color="#8fb4ff" toneMapped={false} />
        </mesh>
      ))}
      <SpriteLabel lines={[{ text: name.toUpperCase(), color: r.color }]} position={[0, ceiling ? 3.6 : 1.0, d / 2 + 0.55]} scale={ceiling ? [w * 0.42, 0.55] : [w * 0.7, 0.9]} />
      <pointLight position={[0, 3.2, 0]} color={r.color} intensity={55} distance={14} decay={2} />
    </group>
  );
}

function Workstation({ role, pose, color }: { role: string; pose: Pose; color: string }) {
  const [x, z] = workSeat(role);
  const bars = useRef<(THREE.Mesh | null)[]>([]);
  const screen = useRef<THREE.MeshBasicMaterial>(null);
  const tone = pose === "error" ? "#ff3860" : pose === "waiting" || pose === "blocked" ? "#ffb020" : color;
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    bars.current.forEach((b, i) => {
      if (!b) return;
      const on = pose === "working";
      b.visible = on || pose === "done";
      b.scale.x = on ? 0.25 + 0.7 * Math.abs(Math.sin(t * 2.2 + i * 1.7 + x)) : 0.5;
    });
    if (screen.current) screen.current.opacity = pose === "idle" ? 0.05 : pose === "working" ? 0.22 : 0.3 + (pose === "error" ? 0.2 * Math.sin(t * 6) : 0);
  });
  return (
    <group position={[x, 0, z - 0.8]}>
      <mesh position={[0, 0.4, 0]}>
        <boxGeometry args={[1.6, 0.08, 0.75]} />
        <meshStandardMaterial color="#111a33" metalness={0.7} roughness={0.3} />
      </mesh>
      {[-0.7, 0.7].map((dx) => (
        <mesh key={dx} position={[dx, 0.2, 0]}>
          <boxGeometry args={[0.06, 0.4, 0.6]} />
          <meshStandardMaterial color="#0b1226" />
        </mesh>
      ))}
      <mesh position={[0, 1.0, -0.2]}>
        <boxGeometry args={[1.05, 0.62, 0.04]} />
        <meshStandardMaterial color="#05070f" emissive={tone} emissiveIntensity={pose === "idle" ? 0.05 : 0.35} />
      </mesh>
      <mesh position={[0, 1.0, -0.17]}>
        <planeGeometry args={[0.95, 0.52]} />
        <meshBasicMaterial ref={screen} color={tone} transparent opacity={0.2} toneMapped={false} />
      </mesh>
      {[0, 1, 2, 3, 4].map((i) => (
        <mesh key={i} position={[-0.3, 1.2 - i * 0.1, -0.165]} ref={(m) => void (bars.current[i] = m)}>
          <boxGeometry args={[0.6, 0.045, 0.01]} />
          <meshBasicMaterial color={tone} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 0.8, -0.2]}>
        <boxGeometry args={[0.06, 0.4, 0.06]} />
        <meshStandardMaterial color="#0b1226" />
      </mesh>
      <mesh position={[0, 0.45, 0.28]}>
        <boxGeometry args={[0.55, 0.03, 0.18]} />
        <meshBasicMaterial color={color} transparent opacity={pose === "working" ? 0.9 : 0.25} toneMapped={false} />
      </mesh>
      <group position={[0, 0, 1.05]}>
        <mesh position={[0, 0.46, 0]} castShadow>
          <boxGeometry args={[0.55, 0.08, 0.5]} />
          <meshStandardMaterial color="#10162f" roughness={0.6} />
        </mesh>
        <mesh position={[0, 0.82, 0.24]} castShadow>
          <boxGeometry args={[0.55, 0.62, 0.07]} />
          <meshStandardMaterial color="#10162f" emissive={color} emissiveIntensity={0.12} roughness={0.6} />
        </mesh>
        <mesh position={[0, 0.22, 0]}>
          <cylinderGeometry args={[0.04, 0.04, 0.4, 8]} />
          <meshStandardMaterial color="#1b2447" metalness={0.7} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.03, 0]}>
          <cylinderGeometry args={[0.3, 0.3, 0.04, 5]} />
          <meshStandardMaterial color="#1b2447" metalness={0.7} roughness={0.3} />
        </mesh>
      </group>
    </group>
  );
}

function Rack({ position }: { position: [number, number, number] }) {
  const leds = useRef<(THREE.Mesh | null)[]>([]);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    leds.current.forEach((m, i) => {
      if (m) m.visible = Math.sin(t * (2 + (i % 4)) + i * 2.3) > -0.2;
    });
  });
  return (
    <group position={position}>
      <mesh position={[0, 1.2, 0]}>
        <boxGeometry args={[0.8, 2.4, 0.7]} />
        <meshStandardMaterial color="#0a0f20" metalness={0.8} roughness={0.35} />
      </mesh>
      {Array.from({ length: 12 }, (_, i) => (
        <mesh key={i} position={[i % 2 ? 0.22 : -0.22, 0.3 + Math.floor(i / 2) * 0.35, 0.36]} ref={(m) => void (leds.current[i] = m)}>
          <boxGeometry args={[0.1, 0.05, 0.02]} />
          <meshBasicMaterial color={i % 3 === 0 ? "#39ff88" : "#3b82f6"} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

function WallChart({ position }: { position: [number, number, number] }) {
  const bars = useRef<(THREE.Mesh | null)[]>([]);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    bars.current.forEach((b, i) => {
      if (!b) return;
      const h = 0.4 + 0.9 * (0.5 + 0.5 * Math.sin(t * 0.7 + i * 1.1));
      b.scale.y = h;
      b.position.y = h / 2 - 0.65;
    });
  });
  return (
    <group position={position}>
      <mesh>
        <boxGeometry args={[4.4, 1.8, 0.08]} />
        <meshStandardMaterial color="#12061f" emissive="#d946ef" emissiveIntensity={0.18} />
      </mesh>
      {Array.from({ length: 7 }, (_, i) => (
        <mesh key={i} position={[-1.8 + i * 0.6, 0, 0.06]} ref={(m) => void (bars.current[i] = m)}>
          <boxGeometry args={[0.36, 1, 0.04]} />
          <meshBasicMaterial color={i % 2 ? "#d946ef" : "#00e5ff"} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

function HoloTable() {
  const holo = useRef<THREE.Mesh>(null);
  useFrame((_, dt) => {
    if (holo.current) holo.current.rotation.y += dt * 0.6;
  });
  const [cx, cz] = ROOMS.meeting.center;
  return (
    <group position={[cx, 0, cz - 0.9]}>
      <mesh position={[0, 0.7, 0]}>
        <cylinderGeometry args={[1.25, 1.25, 0.08, 36]} />
        <meshStandardMaterial color="#0e1530" metalness={0.8} roughness={0.25} emissive="#7c5cff" emissiveIntensity={0.15} />
      </mesh>
      <mesh position={[0, 0.35, 0]}>
        <cylinderGeometry args={[0.18, 0.4, 0.7, 14]} />
        <meshStandardMaterial color="#0b1226" />
      </mesh>
      <mesh ref={holo} position={[0, 1.55, 0]}>
        <icosahedronGeometry args={[0.45, 1]} />
        <meshBasicMaterial color="#7c5cff" wireframe toneMapped={false} />
      </mesh>
      {Array.from({ length: 5 }, (_, i) => (
        <mesh key={i} position={[Math.sin(i * 1.1 - 1.1) * 1.9, 0.3, -Math.cos(i * 1.1 - 1.1) * 1.9 + 0.2]}>
          <cylinderGeometry args={[0.22, 0.22, 0.5, 12]} />
          <meshStandardMaterial color="#10142c" metalness={0.4} roughness={0.5} />
        </mesh>
      ))}
    </group>
  );
}

function Sofa({ role }: { role: string }) {
  const [x, z] = loungeSeat(role);
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.22, 0.05]}>
        <boxGeometry args={[1.25, 0.34, 0.85]} />
        <meshStandardMaterial color="#0f2a30" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.6, -0.36]}>
        <boxGeometry args={[1.25, 0.6, 0.16]} />
        <meshStandardMaterial color="#0f2a30" metalness={0.3} roughness={0.55} />
      </mesh>
      <mesh position={[0, 0.41, 0.05]}>
        <boxGeometry args={[1.25, 0.03, 0.85]} />
        <meshBasicMaterial color="#2dd4bf" transparent opacity={0.35} toneMapped={false} />
      </mesh>
    </group>
  );
}

function CeoDesk() {
  const [cx, cz] = ROOMS.ceo.center;
  return (
    <group position={[cx, 0.35, cz + 0.8]}>
      <mesh position={[0, 0.4, 0]}>
        <boxGeometry args={[3.2, 0.1, 1]} />
        <meshStandardMaterial color="#160b2e" metalness={0.8} roughness={0.25} emissive="#8b5cf6" emissiveIntensity={0.18} />
      </mesh>
      <mesh position={[0, 0.2, 0]}>
        <boxGeometry args={[3.0, 0.4, 0.8]} />
        <meshStandardMaterial color="#0c0618" />
      </mesh>
      <mesh position={[0, 0.46, 0.46]}>
        <boxGeometry args={[3.2, 0.03, 0.03]} />
        <meshBasicMaterial color="#8b5cf6" toneMapped={false} />
      </mesh>
    </group>
  );
}

// ------------------------------------------------------------------ avatar

function lerpAngle(a: number, b: number, k: number) {
  let d = ((b - a + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * k;
}

function Limb({ gref, x, y, len, r, color }: { gref: RefObject<THREE.Group | null>; x: number; y: number; len: number; r: number; color: string }) {
  return (
    <group ref={gref} position={[x, y, 0]}>
      <mesh position={[0, -len / 2, 0]}>
        <capsuleGeometry args={[r, len - r * 2, 4, 8]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.25} roughness={0.5} />
      </mesh>
    </group>
  );
}

function Walker({ a, selected, onSelect, name, status }: { a: Avatar; selected: boolean; onSelect: (role: string) => void; name: string; status: string }) {
  const root = useRef<THREE.Group>(null);
  const body = useRef<THREE.Group>(null);
  const legL = useRef<THREE.Group>(null);
  const legR = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const ring = useRef<THREE.MeshBasicMaterial>(null);
  const start = useMemo<[number, number, number]>(() => [a.position[0], 0, a.position[1]], []); // eslint-disable-line react-hooks/exhaustive-deps
  const color = DEPARTMENT_COLOR[a.department] ?? "#3b82f6";
  const tone = TONE_COLOR[a.tone];

  useFrame((state, dt) => {
    const g = root.current;
    if (!g) return;
    const t = state.clock.elapsedTime;
    const dx = a.position[0] - g.position.x;
    const dz = a.position[1] - g.position.z;
    const dist = Math.hypot(dx, dz);
    const walking = dist > 0.04;
    let facing: number;
    if (walking) {
      const step = Math.min(dist, WALK_SPEED * dt);
      g.position.x += (dx / dist) * step;
      g.position.z += (dz / dist) * step;
      facing = Math.atan2(dx, dz);
    } else {
      facing = a.pose === "idle" ? 0 : Math.PI; // di kursi kerja menghadap meja; di Lounge menghadap penonton
    }
    g.rotation.y = lerpAngle(g.rotation.y, facing, 1 - Math.exp(-10 * dt));

    const swing = walking ? Math.sin(t * 10) * 0.75 : 0;
    if (legL.current) legL.current.rotation.x = swing;
    if (legR.current) legR.current.rotation.x = -swing;
    let la = -swing;
    let ra = swing;
    if (!walking && a.pose === "working") {
      la = -1.15 + Math.sin(t * 14) * 0.12; // mengetik
      ra = -1.15 + Math.sin(t * 14 + 1.3) * 0.12;
    } else if (!walking && a.pose === "waiting") {
      ra = -2.4 + Math.sin(t * 3) * 0.15; // mengangkat tangan: menunggu
    } else if (!walking && a.pose === "error") {
      la = -1.3;
      ra = -1.3;
    }
    if (armL.current) armL.current.rotation.x = la;
    if (armR.current) armR.current.rotation.x = ra;
    if (body.current) {
      body.current.position.y = walking ? Math.abs(Math.sin(t * 10)) * 0.05 : a.pose === "working" ? Math.sin(t * 6) * 0.01 : 0;
      body.current.rotation.z = a.pose === "error" && !walking ? Math.sin(t * 22) * 0.04 : 0;
    }
    if (ring.current) {
      ring.current.opacity = a.pose === "idle" ? 0.35 : a.pose === "error" ? 0.55 + 0.45 * Math.abs(Math.sin(t * 5)) : a.pose === "waiting" ? 0.6 + 0.4 * Math.sin(t * 2) ** 2 : 1;
    }
  });

  return (
    <group
      ref={root}
      position={start}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(a.role);
      }}
    >
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1, 0]}>
        <ringGeometry args={[0.5, 0.62, 40]} />
        <meshBasicMaterial ref={ring} color={selected ? "#ffffff" : tone} transparent toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <group ref={body}>
        <Limb gref={legL} x={-0.11} y={0.62} len={0.6} r={0.085} color="#1b2447" />
        <Limb gref={legR} x={0.11} y={0.62} len={0.6} r={0.085} color="#1b2447" />
        <mesh position={[0, 0.98, 0]}>
          <capsuleGeometry args={[0.21, 0.3, 6, 14]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={a.pose === "idle" ? 0.15 : 0.5} metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[0, 1.1, -0.2]}>
          <boxGeometry args={[0.26, 0.34, 0.1]} />
          <meshStandardMaterial color="#10162f" emissive={color} emissiveIntensity={0.3} />
        </mesh>
        <Limb gref={armL} x={-0.3} y={1.2} len={0.5} r={0.06} color={color} />
        <Limb gref={armR} x={0.3} y={1.2} len={0.5} r={0.06} color={color} />
        <mesh position={[0, 1.5, 0]}>
          <sphereGeometry args={[0.175, 20, 16]} />
          <meshStandardMaterial color="#cfe0ff" emissive="#6f9bff" emissiveIntensity={0.2} roughness={0.35} />
        </mesh>
        <mesh position={[0, 1.52, 0.125]}>
          <boxGeometry args={[0.26, 0.07, 0.07]} />
          <meshBasicMaterial color={a.pose === "idle" ? "#3b4a73" : tone} toneMapped={false} />
        </mesh>
        <mesh position={[0, 1.72, 0]}>
          <cylinderGeometry args={[0.012, 0.012, 0.16, 6]} />
          <meshBasicMaterial color={color} toneMapped={false} />
        </mesh>
      </group>
      <SpriteLabel
        lines={[{ text: name, color: "#e8eaff" }, { text: status, color: a.pose === "idle" ? "#7f8bb0" : tone }]}
        position={[0, 2.3, 0]}
        scale={[2.4, 0.8]}
      />
    </group>
  );
}

// ------------------------------------------------------------------ adegan

export default function Office3D({ avatars, selected, onSelect, hologram, roomLabels, roleLabels, statusLabels, onFail, quality, ceo }: Office3DProps) {
  const glow = useMemo(() => glowTexture(), []);
  useEffect(() => () => glow.dispose(), [glow]);
  const byRole = useMemo(() => new Map(avatars.map((a) => [a.role, a])), [avatars]);
  const focus = selected ? byRole.get(selected)?.position ?? null : null;
  const [ex, ez] = ROOMS.engineering.center;
  const [mx, mz] = ROOMS.marketing.center;
  const [lx, lz] = ROOMS.lounge.center;
  const [cx, cz] = ROOMS.ceo.center;

  return (
    <Canvas
      shadows={quality === "high"}
      dpr={[1, 1.5]}
      camera={{ position: [0, 18, 24], fov: 45, near: 0.5, far: 140 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.domElement.addEventListener("webglcontextlost", (e) => {
          e.preventDefault();
          onFail();
        });
      }}
      style={{ width: "100%", height: "100%", touchAction: "none" }}
    >
      <color attach="background" args={["#05060f"]} />
      <fog attach="fog" args={["#05060f", 40, 90]} />
      <ambientLight intensity={0.5} />
      <hemisphereLight args={["#5b7cff", "#1a0b2e", 0.55]} />
      <directionalLight position={[8, 16, 10]} intensity={0.6} color="#9fb4ff" castShadow={quality === "high"} shadow-mapSize={[2048, 2048]} shadow-camera-left={-26} shadow-camera-right={26} shadow-camera-top={22} shadow-camera-bottom={-18} shadow-camera-near={1} shadow-camera-far={60} shadow-bias={-0.0004} />
      <Controls focus={focus} enabled={!ceo.walking} />
      <Skyline />
      <GlassWall />
      <Particles />
      <mesh position={[0, -0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[120, 90]} />
        <meshStandardMaterial color="#060a18" metalness={0.9} roughness={0.2} />
      </mesh>
      <gridHelper args={[70, 70, "#1c2a55", "#0e1630"]} position={[0, -0.02, 0]} />
      <BrandSign position={[-0.6, 3.9, -14.2]} scale={0.72} />

      {ROOM_ORDER.map((id) => <RoomShell key={id} id={id} name={roomLabels[id]} glow={glow} ceiling={ceo.walking} />)}

      {ROLES.filter((r) => WORKROOM[r] === "engineering").map((r) => <Workstation key={r} role={r} pose={byRole.get(r)?.pose ?? "idle"} color={DEPARTMENT_COLOR.engineering} />)}
      <Rack position={[ex - 3.6, 0.06, ez - 3.0]} />
      <Rack position={[ex - 2.6, 0.06, ez - 3.0]} />
      <Rack position={[ex + 3.6, 0.06, ez - 3.0]} />
      <Plant position={[ex + 4.0, 0.06, ez + 2.6]} />

      {ROLES.filter((r) => WORKROOM[r] === "marketing").map((r) => <Workstation key={r} role={r} pose={byRole.get(r)?.pose ?? "idle"} color={DEPARTMENT_COLOR.marketing} />)}
      <WallChart position={[mx, 2.4, mz - 3.35]} />
      <Plant position={[mx - 4.0, 0.06, mz + 2.6]} />

      <HoloTable />
      <CeoDesk />
      <BrandSign position={[ROOMS.ceo.center[0], 0.85, ROOMS.ceo.center[1] - ROOMS.ceo.size[1] / 2 + 0.25]} scale={0.2} tagline={false} />
      <Plant position={[cx - 3.4, 0.4, cz - 1.6]} s={1.1} />
      <Plant position={[cx + 3.4, 0.4, cz - 1.6]} s={1.1} />
      <mesh position={[cx, 2.25, cz - 2.38]}>
        <planeGeometry args={[5.0, 2.3]} />
        <meshBasicMaterial color="#060a1c" transparent opacity={0.82} />
      </mesh>
      <TextPlane lines={hologram} position={[cx, 2.25, cz - 2.36]} size={[4.8, 2.1]} />

      {ROLES.map((r) => <Sofa key={r} role={r} />)}
      <Plant position={[lx + 4.1, 0.06, lz - 1.9]} s={1.2} />
      <Plant position={[lx - 4.1, 0.06, lz + 1.9]} s={1.2} />

      <ModelBoundary
        fallback={avatars.map((a) => (
          <Walker key={a.role} a={a} selected={selected === a.role} onSelect={onSelect} name={roleLabels[a.role] ?? a.role} status={statusLabels[a.status] ?? a.status} />
        ))}
      >
        <Suspense fallback={null}>
          {avatars.map((a) => (
            <RobotWalker key={a.role} a={a} selected={selected === a.role} onSelect={onSelect} name={roleLabels[a.role] ?? a.role} status={statusLabels[a.status] ?? a.status} />
          ))}
        </Suspense>
      </ModelBoundary>
      <ModelBoundary fallback={null}>
        <Suspense fallback={null}>
          <CeoRig {...ceo} avatars={avatars} />
        </Suspense>
      </ModelBoundary>
      {quality === "high" && (
        <EffectComposer multisampling={0}>
          <Bloom intensity={0.85} luminanceThreshold={0.62} luminanceSmoothing={0.25} mipmapBlur />
        </EffectComposer>
      )}
    </Canvas>
  );
}
