"use client";

// Model 3D berskeleton: robot agent (RobotExpressive, CC0) dan avatar CEO (Cesium Man, CC-BY 4.0). Lihat public/models/LICENSES.md.
import { useFrame, useLoader, useThree } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";
import { clipFor, DEPARTMENT_COLOR, type Avatar } from "@/lib/office/model";
import {
  CEO_RADIUS, CEO_START, INTERACT_RADIUS, moveWithCollision, nearestInteractable, RUN_SPEED, velocityFromInput, WALK_SPEED, type Nearby, type Point,
} from "@/lib/office/walk";

export const ROBOT_URL = "/models/RobotExpressive.glb";
export const CEO_URL = "/models/CesiumMan.glb";
const TONE_COLOR = { ok: "#39ff88", warn: "#ffb020", bad: "#ff3860", idle: "#4b5563" } as const;

/** Jika berkas model tidak dapat dimuat, tampilkan cadangan (avatar prosedural) alih-alih merusak adegan. */
export class ModelBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function prepare(source: THREE.Object3D, height: number, tint?: string) {
  const model = SkeletonUtils.clone(source);
  model.updateMatrixWorld(true);
  model.traverse((o) => {
    if ((o as THREE.SkinnedMesh).isSkinnedMesh) (o as THREE.SkinnedMesh).skeleton.update();
  });
  const box = new THREE.Box3().setFromObject(model, true); // presisi: memakai tulang, bukan kotak bind-pose
  const size = box.getSize(new THREE.Vector3());
  const k = height / Math.max(0.0001, size.y);
  model.scale.multiplyScalar(k);
  model.updateMatrixWorld(true);
  const after = new THREE.Box3().setFromObject(model, true);
  model.position.y -= after.min.y; // telapak kaki tepat di lantai
  const mats = new Map<string, THREE.Material>();
  model.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    m.castShadow = true;
    m.receiveShadow = true;
    m.frustumCulled = false; // mesh berskeleton: kotak pembatas bind-pose tidak selalu mewakili pose animasi
    const src = m.material as THREE.MeshStandardMaterial;
    let own = mats.get(src.uuid);
    if (!own) {
      own = src.clone();
      if (tint && src.name === "Main") {
        const std = own as THREE.MeshStandardMaterial;
        std.color = std.color.clone().lerp(new THREE.Color(tint), 0.6);
        std.emissive = new THREE.Color(tint);
        std.emissiveIntensity = 0.12;
      }
      mats.set(src.uuid, own);
    }
    m.material = own;
  });
  return model;
}

function lerpAngle(a: number, b: number, k: number) {
  let d = ((b - a + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (d < -Math.PI) d += Math.PI * 2;
  return a + d * k;
}

/** Nama-tag di atas kepala: tekstur kanvas kecil (peran + status). */
function tagTexture(lines: { text: string; color: string }[]): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 128 * lines.length;
  const g = c.getContext("2d")!;
  g.textAlign = "center";
  g.textBaseline = "middle";
  const lh = c.height / lines.length;
  lines.forEach((l, i) => {
    g.font = `700 ${Math.round(lh * 0.5)}px "Montserrat Variable", Montserrat, system-ui, sans-serif`;
    g.fillStyle = l.color;
    g.shadowColor = l.color;
    g.shadowBlur = 10;
    g.fillText(l.text, 256, lh * (i + 0.5), 490);
  });
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function Tag({ lines, y, scale }: { lines: { text: string; color: string }[]; y: number; scale: [number, number] }) {
  const key = lines.map((l) => `${l.text}|${l.color}`).join("§");
  const tex = useMemo(() => tagTexture(lines), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => tex.dispose(), [tex]);
  return (
    <sprite position={[0, y, 0]} scale={[scale[0], scale[1], 1]}>
      <spriteMaterial map={tex} transparent depthWrite={false} toneMapped={false} />
    </sprite>
  );
}

// ------------------------------------------------------------------ robot agent

export function RobotWalker({ a, selected, onSelect, name, status }: {
  a: Avatar; selected: boolean; onSelect: (role: string) => void; name: string; status: string;
}) {
  const gltf = useLoader(GLTFLoader, ROBOT_URL);
  const tint = DEPARTMENT_COLOR[a.department] ?? "#3b82f6";
  const model = useMemo(() => prepare(gltf.scene, 1.55, tint), [gltf.scene, tint]);
  const mixer = useMemo(() => new THREE.AnimationMixer(model), [model]);
  const actions = useMemo(() => Object.fromEntries(gltf.animations.map((c) => [c.name, mixer.clipAction(c)])), [mixer, gltf.animations]);
  const current = useRef<string | null>(null);
  const root = useRef<THREE.Group>(null);
  const ring = useRef<THREE.MeshBasicMaterial>(null);
  const start = useMemo<[number, number, number]>(() => [a.position[0], 0, a.position[1]], []); // eslint-disable-line react-hooks/exhaustive-deps
  const tone = TONE_COLOR[a.tone];

  useEffect(() => () => void mixer.stopAllAction(), [mixer]);

  useFrame((state, dt) => {
    const g = root.current;
    if (!g) return;
    const dx = a.position[0] - g.position.x;
    const dz = a.position[1] - g.position.z;
    const dist = Math.hypot(dx, dz);
    const walking = dist > 0.05;
    let facing: number;
    if (walking) {
      const step = Math.min(dist, WALK_SPEED * 0.8 * dt);
      g.position.x += (dx / dist) * step;
      g.position.z += (dz / dist) * step;
      facing = Math.atan2(dx, dz);
    } else {
      facing = a.pose === "idle" ? 0 : Math.PI; // di meja menghadap meja; di Lounge menghadap penonton
    }
    g.rotation.y = lerpAngle(g.rotation.y, facing, 1 - Math.exp(-9 * dt));

    const clip = clipFor(a.pose, walking);
    if (clip !== current.current && actions[clip]) {
      const next = actions[clip];
      next.reset().setLoop(clip === "Sitting" ? THREE.LoopRepeat : THREE.LoopRepeat, Infinity).fadeIn(0.25).play();
      if (current.current && actions[current.current]) actions[current.current].fadeOut(0.25);
      current.current = clip;
    }
    mixer.update(dt);
    if (ring.current) {
      const t = state.clock.elapsedTime;
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
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
        <ringGeometry args={[0.5, 0.62, 40]} />
        <meshBasicMaterial ref={ring} color={selected ? "#ffffff" : tone} transparent toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <primitive object={model} />
      <Tag lines={[{ text: name, color: "#e8ecff" }, { text: status, color: a.pose === "idle" ? "#7f8bb0" : tone }]} y={2.05} scale={[1.55, 0.52]} />
    </group>
  );
}

// ------------------------------------------------------------------ avatar CEO yang dikendalikan pengguna

export type WalkRigProps = {
  walking: boolean;
  start?: Point; // posisi awal (tautan ?pos=x,z); bawaan: depan CEO Office
  view: "third" | "first";
  avatars: Avatar[];
  label: string;
  onNearby: (n: Nearby | null) => void;
  onInteract: (n: Nearby) => void;
  onToggleView: () => void;
  onExit: () => void;
};

const KEYS: Record<string, string> = { KeyW: "f", ArrowUp: "f", KeyS: "b", ArrowDown: "b", KeyA: "l", KeyD: "r" };
// CesiumMan menghadap sumbu +x pada pose awal: koreksi agar arah hadap model = arah gerak
const CEO_FACING_OFFSET = 0;

/**
 * CEO: model berjalan menurut masukan papan ketik (hanya saat `walking`), kamera orang ketiga/pertama mengikutinya, dan objek terdekat dilaporkan.
 * Saat tidak berjalan, CEO berdiri diam di tempat terakhirnya dan kamera dikendalikan OrbitControls di luar komponen ini.
 */
export function CeoRig({ walking, start, view, avatars, label, onNearby, onInteract, onToggleView, onExit }: WalkRigProps) {
  const gltf = useLoader(GLTFLoader, CEO_URL);
  const { camera, gl } = useThree();
  const model = useMemo(() => prepare(gltf.scene, 1.78), [gltf.scene]);
  const mixer = useMemo(() => new THREE.AnimationMixer(model), [model]);
  const clip = gltf.animations[0];
  const actionRef = useRef<THREE.AnimationAction | null>(null);
  const root = useRef<THREE.Group>(null);
  const pos = useRef<Point>(start ? [...start] : [...CEO_START]);
  const yaw = useRef(0);
  const pitch = useRef(0.22);
  const heading = useRef(0);
  const keys = useRef(new Set<string>());
  const dragging = useRef(false);
  const shift = useRef(false);
  const nearby = useRef<Nearby | null>(null);
  const reported = useRef<string>("");
  const camPos = useMemo(() => new THREE.Vector3(), []);
  const look = useMemo(() => new THREE.Vector3(), []);

  useEffect(() => {
    const act = clip ? mixer.clipAction(clip) : null;
    act?.play();
    actionRef.current = act;
    return () => {
      actionRef.current = null;
      mixer.stopAllAction();
    };
  }, [clip, mixer]);

  // papan ketik dan mouse hanya aktif dalam mode jalan
  useEffect(() => {
    if (!walking) {
      keys.current.clear();
      return;
    }
    const typing = (t: EventTarget | null) => t instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName);
    const down = (e: KeyboardEvent) => {
      if (typing(e.target)) return;
      if (e.code in KEYS || e.code === "ArrowLeft" || e.code === "ArrowRight" || e.code === "Space") e.preventDefault();
      if (e.code === "ShiftLeft" || e.code === "ShiftRight") shift.current = true;
      if (e.code in KEYS) keys.current.add(KEYS[e.code]);
      if (e.code === "KeyV") onToggleView();
      if (e.code === "Escape") onExit();
      if (e.code === "KeyE" && nearby.current) onInteract(nearby.current);
      if (e.code === "ArrowLeft") keys.current.add("tl");
      if (e.code === "ArrowRight") keys.current.add("tr");
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "ShiftLeft" || e.code === "ShiftRight") shift.current = false;
      if (e.code in KEYS) keys.current.delete(KEYS[e.code]);
      if (e.code === "ArrowLeft") keys.current.delete("tl");
      if (e.code === "ArrowRight") keys.current.delete("tr");
    };
    const held = keys.current;
    const pd = (e: PointerEvent) => {
      dragging.current = true;
      (e.target as Element).setPointerCapture?.(e.pointerId);
    };
    const pu = () => {
      dragging.current = false;
    };
    const pm = (e: PointerEvent) => {
      if (!dragging.current && document.pointerLockElement !== gl.domElement) return;
      yaw.current -= e.movementX * 0.005;
      pitch.current = Math.max(-0.5, Math.min(1.1, pitch.current + e.movementY * 0.004));
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    gl.domElement.addEventListener("pointerdown", pd);
    window.addEventListener("pointerup", pu);
    gl.domElement.addEventListener("pointermove", pm);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      gl.domElement.removeEventListener("pointerdown", pd);
      window.removeEventListener("pointerup", pu);
      gl.domElement.removeEventListener("pointermove", pm);
      held.clear();
    };
  }, [walking, gl, onExit, onInteract, onToggleView]);

  useFrame((_, dt) => {
    const g = root.current;
    if (!g) return;
    let moving = false;
    if (walking) {
      const k = keys.current;
      if (k.has("tl")) yaw.current += 1.9 * dt;
      if (k.has("tr")) yaw.current -= 1.9 * dt;
      const input = { forward: (k.has("f") ? 1 : 0) - (k.has("b") ? 1 : 0), right: (k.has("r") ? 1 : 0) - (k.has("l") ? 1 : 0) };
      const speed = shift.current ? RUN_SPEED : WALK_SPEED;
      const v = velocityFromInput(input, yaw.current, speed);
      if (v[0] !== 0 || v[1] !== 0) {
        pos.current = moveWithCollision(pos.current, [v[0] * dt, v[1] * dt], CEO_RADIUS);
        heading.current = Math.atan2(v[0], v[1]);
        moving = true;
      }
      const n = nearestInteractable(pos.current, avatars);
      nearby.current = n;
      const id = n ? (n.kind === "agent" ? `a:${n.role}` : `p:${n.id}`) : "";
      if (id !== reported.current) {
        reported.current = id;
        onNearby(n);
      }
    } else if (reported.current !== "") {
      reported.current = "";
      nearby.current = null;
      onNearby(null);
    }
    g.position.set(pos.current[0], 0, pos.current[1]);
    g.rotation.y = lerpAngle(g.rotation.y, heading.current + CEO_FACING_OFFSET, 1 - Math.exp(-12 * dt));
    g.visible = !(walking && view === "first");
    const act = actionRef.current;
    if (act) {
      act.timeScale = moving ? (shift.current ? 1.7 : 1.05) : 0; // diam: berhenti pada pose berdiri
      if (!moving) act.time = 0;
    }
    mixer.update(dt);

    if (walking) {
      const head = 1.62;
      if (view === "first") {
        camPos.set(pos.current[0], head, pos.current[1]);
        camera.position.lerp(camPos, 1 - Math.exp(-30 * dt));
        look.set(pos.current[0] - Math.sin(yaw.current) * Math.cos(pitch.current - 0.22), head - Math.sin(pitch.current - 0.22), pos.current[1] - Math.cos(yaw.current) * Math.cos(pitch.current - 0.22));
      } else {
        const dist = 4.6;
        camPos.set(pos.current[0] + Math.sin(yaw.current) * Math.cos(pitch.current) * dist, 1.2 + Math.sin(pitch.current) * dist, pos.current[1] + Math.cos(yaw.current) * Math.cos(pitch.current) * dist);
        camera.position.lerp(camPos, 1 - Math.exp(-9 * dt));
        look.set(pos.current[0], 1.35, pos.current[1]);
      }
      camera.lookAt(look);
    }
  });

  return (
    <group ref={root} position={[CEO_START[0], 0, CEO_START[1]]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
        <ringGeometry args={[0.46, 0.6, 40]} />
        <meshBasicMaterial color="#ffd166" toneMapped={false} side={THREE.DoubleSide} />
      </mesh>
      <primitive object={model} />
      {!walking && <Tag lines={[{ text: label, color: "#ffd166" }]} y={2.05} scale={[1.1, 0.34]} />}
      <pointLight color="#ffd166" intensity={9} distance={5} decay={2} position={[0, 2.2, 0]} />
    </group>
  );
}

export { INTERACT_RADIUS };
