"use client";

// Render 3D saja. Tidak ada logika bisnis di sini: semua posisi, pose, dan warna datang dari lib/office/model (potret backend).
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { DEPARTMENT_COLOR, ROOM_ORDER, ROOMS, type Avatar, type RoomId } from "@/lib/office/model";

const TONE_COLOR = { ok: "#39ff88", warn: "#ffb020", bad: "#ff3860", idle: "#4b5563" } as const;

export type HologramLine = { text: string; color: string };
export type Office3DProps = {
  avatars: Avatar[];
  selected: string | null;
  onSelect: (role: string) => void;
  hologram: HologramLine[];
  roomLabels: Record<RoomId, string>;
  onFail: () => void;
};

function labelTexture(lines: HologramLine[], w = 512, h = 256): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, w, h);
  const lh = Math.min(64, h / Math.max(1, lines.length));
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  lines.forEach((l, i) => {
    ctx.font = `bold ${Math.round(lh * 0.62)}px ui-monospace, Consolas, monospace`;
    ctx.fillStyle = l.color;
    ctx.shadowColor = l.color;
    ctx.shadowBlur = 12;
    ctx.fillText(l.text, w / 2, lh * (i + 0.5) + (h - lh * lines.length) / 2, w - 24);
  });
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function Label({ lines, position, size = [6, 3], rotation = [0, 0, 0] as [number, number, number] }: { lines: HologramLine[]; position: [number, number, number]; size?: [number, number]; rotation?: [number, number, number] }) {
  const key = lines.map((l) => `${l.text}|${l.color}`).join("§");
  const tex = useMemo(() => labelTexture(lines), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <mesh position={position} rotation={rotation}>
      <planeGeometry args={size} />
      <meshBasicMaterial map={tex} transparent depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

function SpriteLabel({ lines, position, scale }: { lines: HologramLine[]; position: [number, number, number]; scale: [number, number] }) {
  const key = lines.map((l) => `${l.text}|${l.color}`).join("§");
  const tex = useMemo(() => labelTexture(lines, 512, 128 * lines.length), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <sprite position={position} scale={[scale[0], scale[1], 1]}>
      <spriteMaterial map={tex} transparent depthWrite={false} toneMapped={false} />
    </sprite>
  );
}

function Controls() {
  const { camera, gl } = useThree();
  const ref = useRef<OrbitControls | null>(null);
  useEffect(() => {
    const c = new OrbitControls(camera, gl.domElement);
    c.enableDamping = true;
    c.maxPolarAngle = Math.PI / 2.15;
    c.minDistance = 8;
    c.maxDistance = 48;
    c.target.set(0, 0, 2);
    ref.current = c;
    return () => c.dispose();
  }, [camera, gl]);
  useFrame(() => ref.current?.update());
  return null;
}

function makeSkyline() {
  let seed = 7;
  const rnd = () => {
    seed = (seed * 16807) % 2147483647; // deterministik: tampilan sama setiap dimuat
    return seed / 2147483647;
  };
  return Array.from({ length: 46 }, (_, i) => {
    const h = 3 + rnd() * 16;
    const hue = ["#00b8ff", "#a855f7", "#ff2bd6"][Math.floor(rnd() * 3)];
    return { x: -34 + i * 1.5, h, w: 0.9 + rnd() * 0.8, hue };
  });
}

function Skyline() {
  const boxes = useMemo(() => makeSkyline(), []);
  return (
    <group position={[0, 0, -22]}>
      {boxes.map((b, i) => (
        <mesh key={i} position={[b.x, b.h / 2, 0]}>
          <boxGeometry args={[b.w, b.h, 1]} />
          <meshStandardMaterial color="#0b1022" emissive={b.hue} emissiveIntensity={0.1} />
        </mesh>
      ))}
    </group>
  );
}

function RoomShell({ id, name }: { id: RoomId; name: string }) {
  const r = ROOMS[id];
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(r.size[0], 0.12, r.size[1])), [r.size]);
  useEffect(() => () => edges.dispose(), [edges]);
  const raised = id === "ceo" ? 0.35 : 0;
  return (
    <group position={[r.center[0], raised, r.center[1]]}>
      <mesh position={[0, 0.02, 0]} receiveShadow>
        <boxGeometry args={[r.size[0], 0.12, r.size[1]]} />
        <meshStandardMaterial color="#0a1226" metalness={0.85} roughness={0.28} emissive={r.color} emissiveIntensity={0.05} />
      </mesh>
      <lineSegments geometry={edges} position={[0, 0.02, 0]}>
        <lineBasicMaterial color={r.color} toneMapped={false} />
      </lineSegments>
      <SpriteLabel lines={[{ text: name.toUpperCase(), color: r.color }]} position={[0, 1.0, r.size[1] / 2 + 0.55]} scale={[r.size[0] * 0.7, 1.0]} />
      <pointLight position={[0, 3.2, 0]} color={r.color} intensity={55} distance={14} decay={2} />
    </group>
  );
}

function Seat({ a, selected, onSelect }: { a: Avatar; selected: boolean; onSelect: (role: string) => void }) {
  const body = useRef<THREE.Group>(null);
  const ring = useRef<THREE.MeshBasicMaterial>(null);
  const screen = useRef<THREE.MeshBasicMaterial>(null);
  const color = DEPARTMENT_COLOR[a.department] ?? "#00b8ff";
  const tone = TONE_COLOR[a.tone];
  const lounge = a.room === "lounge";
  const raised = a.room === "ceo" ? 0.35 : 0;

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (body.current) body.current.position.y = a.pose === "working" ? 0.62 + Math.sin(t * 6) * 0.025 : 0.62;
    if (ring.current) {
      const pulse = a.pose === "error" ? 0.55 + 0.45 * Math.abs(Math.sin(t * 5)) : a.pose === "waiting" ? 0.6 + 0.4 * Math.sin(t * 2) ** 2 : 1;
      ring.current.opacity = a.pose === "idle" ? 0.35 : pulse;
    }
    if (screen.current) screen.current.opacity = a.pose === "working" ? 0.75 + 0.25 * Math.sin(t * 9 + a.position[0]) : a.pose === "idle" ? 0 : 0.35;
  });

  return (
    <group position={[a.position[0], raised, a.position[1]]} scale={1.35}>
      {!lounge && (
        <group position={[0, 0, -0.75]}>
          <mesh position={[0, 0.38, 0]}>
            <boxGeometry args={[1.5, 0.08, 0.7]} />
            <meshStandardMaterial color="#111a33" metalness={0.7} roughness={0.35} />
          </mesh>
          <mesh position={[0, 0.9, -0.22]}>
            <planeGeometry args={[0.95, 0.55]} />
            <meshBasicMaterial ref={screen} color={color} transparent toneMapped={false} />
          </mesh>
        </group>
      )}
      {lounge && (
        <mesh position={[0, 0.2, 0.05]}>
          <boxGeometry args={[1.2, 0.4, 0.9]} />
          <meshStandardMaterial color="#10222a" metalness={0.3} roughness={0.6} />
        </mesh>
      )}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.1, 0.15]}>
        <ringGeometry args={[0.46, 0.56, 40]} />
        <meshBasicMaterial ref={ring} color={selected ? "#ffffff" : tone} transparent toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <group
        ref={body}
        position={[0, 0.62, 0.15]}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(a.role);
        }}
      >
        <mesh>
          <capsuleGeometry args={[0.2, 0.55, 6, 14]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={a.pose === "idle" ? 0.12 : 0.55} metalness={0.4} roughness={0.4} />
        </mesh>
        <mesh position={[0, 0.58, 0]}>
          <sphereGeometry args={[0.17, 18, 14]} />
          <meshStandardMaterial color="#d7e4ff" emissive="#7aa7ff" emissiveIntensity={0.25} />
        </mesh>
      </group>
    </group>
  );
}

export default function Office3D({ avatars, selected, onSelect, hologram, roomLabels, onFail }: Office3DProps) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [0, 20, 26], fov: 45, near: 0.5, far: 120 }}
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
      <fog attach="fog" args={["#05060f", 38, 80]} />
      <ambientLight intensity={0.45} />
      <hemisphereLight args={["#5b7cff", "#1a0b2e", 0.5]} />
      <Controls />
      <Skyline />
      <gridHelper args={[70, 70, "#1c2a55", "#0e1630"]} position={[0, -0.02, 0]} />
      <Label lines={[{ text: "ROIHAN SOFTWARE HOUSE", color: "#00e5ff" }, { text: "Build Today, Create Tomorrow", color: "#ff2bd6" }]} position={[0, 5.2, -13.5]} size={[16, 5]} />
      {ROOM_ORDER.map((id) => <RoomShell key={id} id={id} name={roomLabels[id]} />)}
      <SpriteLabel lines={hologram} position={[0, 2.6, -7]} scale={[7.5, 3.4]} />
      {avatars.map((a) => <Seat key={a.role} a={a} selected={selected === a.role} onSelect={onSelect} />)}
    </Canvas>
  );
}
