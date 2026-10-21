"use client";

// Adegan 3D beranda: terbang menyusuri kota cyberpunk bertabur hujan neon menuju inti AI hologram.
// Murni visual; satu-satunya masukan dari backend adalah `activity` (kecepatan denyut dan warna inti) yang dihitung lib/home/activity.
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useLogoTexture } from "@/components/brand/useBrandTextures";
import type { HeroActivity } from "@/lib/home/activity";

const SEG = 90; // panjang satu segmen kota (m); dua salinan bergulir agar tak berujung
const NEON = ["#00e5ff", "#d946ef", "#8b5cf6", "#3b82f6", "#ff7a2b"];

function rngFrom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647; // deterministik: kota yang sama setiap dimuat
    return s / 2147483647;
  };
}

// ------------------------------------------------------------------ data kota

type Building = { x: number; z: number; w: number; d: number; h: number; shade: number; cap: string | null };
type Win = { x: number; y: number; z: number; side: 1 | -1; warm: boolean };

function makeCity() {
  const rnd = rngFrom(42);
  const buildings: Building[] = [];
  for (const side of [-1, 1] as const) {
    for (let z = -SEG; z < 0; z += 3 + rnd() * 2.5) {
      const w = 2.2 + rnd() * 3;
      const d = 2.4 + rnd() * 2.6;
      buildings.push({
        x: side * (10 + w / 2 + rnd() * 10), z, w, d, h: 6 + rnd() * rnd() * 46 + (rnd() > 0.9 ? 22 : 0), shade: rnd(),
        cap: rnd() > 0.55 ? NEON[Math.floor(rnd() * NEON.length)] : null,
      });
    }
  }
  const windows: Win[] = [];
  for (const b of buildings) {
    const side: 1 | -1 = b.x > 0 ? 1 : -1;
    const n = Math.floor(b.h * 1.3);
    for (let i = 0; i < n; i++) {
      windows.push({ x: b.x - side * (b.w / 2 + 0.02), y: 1 + rnd() * (b.h - 1.5), z: b.z + (rnd() - 0.5) * (b.d - 0.5), side, warm: rnd() > 0.55 });
    }
  }
  return { buildings, windows };
}

function CitySegment({ city }: { city: ReturnType<typeof makeCity> }) {
  const blocks = useRef<THREE.InstancedMesh>(null);
  const caps = useRef<THREE.InstancedMesh>(null);
  const wins = useRef<THREE.InstancedMesh>(null);
  const capList = useMemo(() => city.buildings.filter((b) => b.cap), [city]);
  const edges = useRef<THREE.InstancedMesh>(null);

  useLayoutEffect(() => {
    const d = new THREE.Object3D();
    const col = new THREE.Color();
    city.buildings.forEach((b, i) => {
      d.position.set(b.x, b.h / 2, b.z);
      d.scale.set(b.w, b.h, b.d);
      d.rotation.set(0, 0, 0);
      d.updateMatrix();
      blocks.current?.setMatrixAt(i, d.matrix);
      blocks.current?.setColorAt(i, col.setHSL(0.64 + b.shade * 0.16, 0.55, 0.1 + b.shade * 0.09));
    });
    capList.forEach((b, i) => {
      d.position.set(b.x, b.h + 0.06, b.z);
      d.scale.set(b.w + 0.1, 0.3, b.d + 0.1);
      d.updateMatrix();
      caps.current?.setMatrixAt(i, d.matrix);
      caps.current?.setColorAt(i, col.set(b.cap!));
    });
    capList.forEach((b, i) => {
      const side = b.x > 0 ? 1 : -1;
      d.position.set(b.x - side * (b.w / 2 + 0.03), b.h / 2, b.z + b.d / 2);
      d.rotation.set(0, 0, 0);
      d.scale.set(0.12, b.h, 0.12);
      d.updateMatrix();
      edges.current?.setMatrixAt(i, d.matrix);
      edges.current?.setColorAt(i, col.set(b.cap!));
    });
    city.windows.forEach((w, i) => {
      d.position.set(w.x, w.y, w.z);
      d.rotation.set(0, (-w.side * Math.PI) / 2, 0);
      d.scale.set(0.26, 0.38, 1);
      d.updateMatrix();
      wins.current?.setMatrixAt(i, d.matrix);
      wins.current?.setColorAt(i, col.set(w.warm ? "#ffcf70" : "#6fe3ff"));
    });
    for (const m of [blocks.current, caps.current, edges.current, wins.current]) {
      if (!m) continue;
      m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor) m.instanceColor.needsUpdate = true;
    }
  }, [city, capList]);

  return (
    <group>
      <instancedMesh ref={blocks} args={[undefined, undefined, city.buildings.length]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.6} metalness={0.5} />
      </instancedMesh>
      <instancedMesh ref={caps} args={[undefined, undefined, capList.length]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial toneMapped={false} />
      </instancedMesh>
      <instancedMesh ref={edges} args={[undefined, undefined, capList.length]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial toneMapped={false} />
      </instancedMesh>
      <instancedMesh ref={wins} args={[undefined, undefined, city.windows.length]}>
        <planeGeometry args={[1, 1]} />
        <meshBasicMaterial toneMapped={false} transparent opacity={0.85} />
      </instancedMesh>
    </group>
  );
}

function ScrollingCity({ speed }: { speed: number }) {
  const city = useMemo(() => makeCity(), []);
  const a = useRef<THREE.Group>(null);
  const b = useRef<THREE.Group>(null);
  const offset = useRef(0);
  useFrame((_, dt) => {
    offset.current = (offset.current + dt * speed) % SEG;
    if (a.current) a.current.position.z = offset.current;
    if (b.current) b.current.position.z = offset.current - SEG;
  });
  return (
    <>
      <group ref={a}><CitySegment city={city} /></group>
      <group ref={b}><CitySegment city={city} /></group>
    </>
  );
}

// ------------------------------------------------------------------ jalan, kendaraan, hujan

function Road({ speed }: { speed: number }) {
  const grid = useRef<THREE.Group>(null);
  const off = useRef(0);
  const lines = useMemo(() => Array.from({ length: 36 }, (_, i) => i), []);
  useFrame((_, dt) => {
    off.current = (off.current + dt * speed) % 5;
    if (grid.current) grid.current.position.z = off.current;
  });
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, -60]}>
        <planeGeometry args={[220, 220]} />
        <meshStandardMaterial color="#04060f" metalness={0.95} roughness={0.18} />
      </mesh>
      <group ref={grid}>
        {lines.map((i) => (
          <mesh key={i} position={[0, 0.01, -i * 5 + 8]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[60, 0.05]} />
            <meshBasicMaterial color="#3b82f6" transparent opacity={0.55} toneMapped={false} />
          </mesh>
        ))}
      </group>
      {[-1, 1].map((s) => (
        <mesh key={s} position={[s * 6, 0.02, -60]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.12, 200]} />
          <meshBasicMaterial color={s < 0 ? "#d946ef" : "#00e5ff"} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0, 0.02, -60]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.1, 200]} />
        <meshBasicMaterial color="#8b5cf6" transparent opacity={0.6} toneMapped={false} />
      </mesh>
    </group>
  );
}

type Car = { x: number; y: number; z: number; v: number; len: number; color: string };

function Traffic() {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const cars = useMemo<Car[]>(() => {
    const rnd = rngFrom(9);
    return Array.from({ length: 34 }, () => ({
      x: (rnd() - 0.5) * 30, y: 1.2 + rnd() * 14, z: -rnd() * 130 + 20,
      v: (rnd() > 0.5 ? 1 : -1) * (14 + rnd() * 22), len: 1.4 + rnd() * 2.2, color: NEON[Math.floor(rnd() * NEON.length)],
    }));
  }, []);
  useLayoutEffect(() => {
    const col = new THREE.Color();
    cars.forEach((c, i) => mesh.current?.setColorAt(i, col.set(c.color)));
    if (mesh.current?.instanceColor) mesh.current.instanceColor.needsUpdate = true;
  }, [cars]);
  const d = useMemo(() => new THREE.Object3D(), []);
  useFrame((_, dt) => {
    const m = mesh.current;
    if (!m) return;
    cars.forEach((c, i) => {
      c.z += c.v * dt;
      if (c.z > 26) c.z = -110;
      if (c.z < -110) c.z = 26;
      d.position.set(c.x, c.y, c.z);
      d.scale.set(0.5, 0.16, c.len);
      d.updateMatrix();
      m.setMatrixAt(i, d.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
  });
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, cars.length]} frustumCulled={false}>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}

function Rain() {
  const ref = useRef<THREE.LineSegments>(null);
  const drops = useMemo(() => {
    const rnd = rngFrom(5);
    return Array.from({ length: 700 }, () => ({ x: (rnd() - 0.5) * 60, y: rnd() * 40, z: -rnd() * 110 + 15 }));
  }, []);
  const pos = useMemo(() => new Float32Array(drops.length * 6), [drops]);
  useFrame((_, dt) => {
    const g = ref.current?.geometry;
    if (!g) return;
    drops.forEach((p, i) => {
      p.y -= dt * 38;
      if (p.y < 0) p.y = 40;
      pos.set([p.x, p.y, p.z, p.x - 0.03, p.y + 0.9, p.z], i * 6);
    });
    (g.attributes.position as THREE.BufferAttribute).needsUpdate = true;
  });
  return (
    <lineSegments ref={ref} frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[pos, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color="#7fdcff" transparent opacity={0.28} toneMapped={false} />
    </lineSegments>
  );
}

// ------------------------------------------------------------------ inti AI, papan hologram, langit

function glowTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.35, "rgba(255,255,255,0.3)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

function textTexture(lines: { text: string; color: string }[], w = 1024, h = 256): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d")!;
  const lh = h / lines.length;
  g.textAlign = "center";
  g.textBaseline = "middle";
  lines.forEach((l, i) => {
    g.font = `800 ${Math.round(lh * 0.6)}px ui-monospace, Consolas, monospace`;
    g.fillStyle = l.color;
    g.shadowColor = l.color;
    g.shadowBlur = 22;
    g.fillText(l.text, w / 2, lh * (i + 0.5), w - 40);
  });
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function Core({ activity }: { activity: HeroActivity }) {
  const root = useRef<THREE.Group>(null);
  const ring1 = useRef<THREE.Mesh>(null);
  const ring2 = useRef<THREE.Mesh>(null);
  const ring3 = useRef<THREE.Mesh>(null);
  const inner = useRef<THREE.Mesh>(null);
  const wire = useRef<THREE.Mesh>(null);
  const glow = useMemo(() => glowTexture(), []);
  useEffect(() => () => glow.dispose(), [glow]);
  const color = useMemo(() => new THREE.Color(activity.color), [activity.color]);
  const speed = 0.35 + activity.level * 0.55;

  useFrame(({ clock }, dt) => {
    const t = clock.elapsedTime;
    if (root.current) root.current.position.y = 11 + Math.sin(t * 0.8) * 0.5;
    if (ring1.current) ring1.current.rotation.x += dt * speed * 1.3;
    if (ring2.current) ring2.current.rotation.y += dt * speed * 1.7;
    if (ring3.current) ring3.current.rotation.z += dt * speed * 2.1;
    if (wire.current) {
      wire.current.rotation.y += dt * speed * 0.6;
      wire.current.rotation.x += dt * speed * 0.3;
    }
    if (inner.current) inner.current.scale.setScalar(1 + Math.sin(t * (2 + activity.level * 1.8)) * 0.06);
  });
  const ringMat = <meshBasicMaterial color={color} toneMapped={false} />;
  return (
    <group ref={root} position={[11, 11, -30]} scale={1.35}>
      <mesh ref={inner}>
        <icosahedronGeometry args={[1.6, 2]} />
        <meshBasicMaterial color={color} transparent opacity={0.28} toneMapped={false} />
      </mesh>
      <mesh ref={wire}>
        <icosahedronGeometry args={[2.5, 1]} />
        <meshBasicMaterial color={color} wireframe toneMapped={false} />
      </mesh>
      <mesh ref={ring1}><torusGeometry args={[3.6, 0.045, 8, 96]} />{ringMat}</mesh>
      <mesh ref={ring2}><torusGeometry args={[4.4, 0.045, 8, 96]} />{ringMat}</mesh>
      <mesh ref={ring3}><torusGeometry args={[5.2, 0.045, 8, 96]} />{ringMat}</mesh>
      <sprite scale={[22, 22, 1]}>
        <spriteMaterial map={glow} color={color} transparent opacity={0.55} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <mesh position={[0, -14, 0]}>
        <cylinderGeometry args={[0.05, 1.6, 28, 24, 1, true]} />
        <meshBasicMaterial color={color} transparent opacity={0.1} depthWrite={false} blending={THREE.AdditiveBlending} side={THREE.DoubleSide} toneMapped={false} />
      </mesh>
      <pointLight color={color} intensity={400} distance={60} decay={2} />
    </group>
  );
}

/** Tanda logo Roihan melayang di atas inti AI (sprite menghadap kamera, bercahaya). */
function LogoHolo() {
  const logo = useLogoTexture();
  const ref = useRef<THREE.Sprite>(null);
  useFrame(({ clock }) => {
    if (ref.current) ref.current.position.y = 22.5 + Math.sin(clock.elapsedTime * 0.9) * 0.4;
  });
  if (!logo) return null;
  return (
    <sprite ref={ref} position={[11, 22.5, -30]} scale={[7.5, 7.5, 1]}>
      <spriteMaterial map={logo} transparent depthWrite={false} toneMapped={false} />
    </sprite>
  );
}

function Billboard({ position, rotY, lines }: { position: [number, number, number]; rotY: number; lines: { text: string; color: string }[] }) {
  const tex = useMemo(() => textTexture(lines), [lines]);
  const mat = useRef<THREE.MeshBasicMaterial>(null);
  useEffect(() => () => tex.dispose(), [tex]);
  useFrame(({ clock }) => {
    if (mat.current) mat.current.opacity = 0.8 + 0.2 * Math.sin(clock.elapsedTime * 7 + position[0]) * (Math.sin(clock.elapsedTime * 0.9) > 0.92 ? 3 : 0.4);
  });
  return (
    <mesh position={position} rotation={[0, rotY, 0]}>
      <planeGeometry args={[11, 2.75]} />
      <meshBasicMaterial ref={mat} map={tex} transparent depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

function Sky() {
  const glow = useMemo(() => glowTexture(), []);
  useEffect(() => () => glow.dispose(), [glow]);
  return (
    <group position={[0, 0, -118]}>
      <sprite position={[0, 8, 0]} scale={[260, 80, 1]}>
        <spriteMaterial map={glow} color="#d946ef" transparent opacity={0.55} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <sprite position={[-40, 24, 0]} scale={[160, 110, 1]}>
        <spriteMaterial map={glow} color="#5b2bff" transparent opacity={0.4} depthWrite={false} blending={THREE.AdditiveBlending} toneMapped={false} />
      </sprite>
      <mesh position={[42, 34, 8]}>
        <sphereGeometry args={[9, 32, 24]} />
        <meshBasicMaterial color="#2b1060" toneMapped={false} />
      </mesh>
      <mesh position={[42, 34, 8]} rotation={[1.2, 0.2, 0.3]}>
        <torusGeometry args={[15, 0.35, 8, 120]} />
        <meshBasicMaterial color="#d946ef" toneMapped={false} />
      </mesh>
    </group>
  );
}

// ------------------------------------------------------------------ kamera dan adegan

function Rig() {
  useFrame(({ clock, camera, pointer }) => {
    const t = clock.elapsedTime;
    const tx = Math.sin(t * 0.15) * 3 + pointer.x * 4;
    const ty = 5.5 + Math.sin(t * 0.22) * 0.7 + pointer.y * 1.5;
    camera.position.x += (tx - camera.position.x) * 0.04; // paralaks halus mengikuti penunjuk
    camera.position.y += (ty - camera.position.y) * 0.04;
    camera.lookAt(3 + pointer.x * 3, 9 + pointer.y, -26);
  });
  return null;
}

const SIGN_A = [{ text: "BUILD TODAY", color: "#00e5ff" }];
const SIGN_B = [{ text: "CREATE TOMORROW", color: "#d946ef" }];

export default function HeroScene({ activity, running, onFail }: { activity: HeroActivity; running: boolean; onFail: () => void }) {
  const speed = 6 + activity.level * 5; // kota bergulir lebih cepat saat sistem sibuk
  return (
    <Canvas
      dpr={[1, 1.5]}
      frameloop={running ? "always" : "never"}
      camera={{ position: [0, 5.5, 16], fov: 52, near: 0.5, far: 220 }}
      gl={{ antialias: false, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        gl.domElement.addEventListener("webglcontextlost", (e) => {
          e.preventDefault();
          onFail();
        });
      }}
      style={{ width: "100%", height: "100%" }}
    >
      <color attach="background" args={["#04050d"]} />
      <fog attach="fog" args={["#1a0b3a", 50, 170]} />
      <ambientLight intensity={0.6} />
      <hemisphereLight args={["#6b4bff", "#0a0420", 0.7]} />
      <pointLight position={[-9, 9, -6]} color="#d946ef" intensity={260} distance={50} decay={2} />
      <pointLight position={[9, 9, -22]} color="#00e5ff" intensity={260} distance={50} decay={2} />
      <Rig />
      <Sky />
      <ScrollingCity speed={speed} />
      <Road speed={speed} />
      <Traffic />
      <Rain />
      <Core activity={activity} />
      <LogoHolo />
      <Billboard position={[-17, 12, -34]} rotY={0.5} lines={SIGN_A} />
      <Billboard position={[17, 15, -44]} rotY={-0.5} lines={SIGN_B} />
    </Canvas>
  );
}
