// Tampilan tiap role: karakter Kenney (CC0) + aksesori prosedural yang menjelaskan pekerjaannya. Satuan: model mentah (tinggi karakter ~2,7).
import * as THREE from "three";

export type PropKind = "headphones" | "headset" | "magnifier" | "clipboard" | "notebook" | "binoculars" | "megaphone" | "briefcase" | "tablet" | "crown" | "stamp";
export type Look = { file: string; props: PropKind[] };

const base = "/models/characters/character-";
export const ROLE_LOOK: Record<string, Look> = {
  manager: { file: `${base}h.glb`, props: ["tablet"] },               // robot ungu: koordinator AI
  developer: { file: `${base}c.glb`, props: ["headphones"] },          // kaus gamer
  qa: { file: `${base}d.glb`, props: ["magnifier"] },                  // boneka uji tabrak
  analyst: { file: `${base}i.glb`, props: ["clipboard"] },             // jas lab dan kacamata
  reviewer: { file: `${base}j.glb`, props: ["stamp"] },                // seragam inspektur
  reporter: { file: `${base}b.glb`, props: ["notebook"] },             // kaus merah santai
  market_research: { file: `${base}m.glb`, props: ["binoculars"] },    // penjelajah
  lead_generation: { file: `${base}r.glb`, props: ["headset"] },       // pemburu prospek senyap
  content_promotion: { file: `${base}e.glb`, props: ["megaphone"] },   // kreatif
  sales_client_relations: { file: `${base}n.glb`, props: ["briefcase"] }, // penyambut klien
};
export const CEO_LOOK: Look = { file: `${base}q.glb`, props: ["crown"] }; // jas hitam berdasi merah
export const ALL_LOOK_FILES = [...new Set([...Object.values(ROLE_LOOK), CEO_LOOK].map((l) => l.file))];

const mat = (color: string, emissive = 0, metal = 0.2) =>
  new THREE.MeshStandardMaterial({ color, emissive: new THREE.Color(color), emissiveIntensity: emissive, metalness: metal, roughness: 0.55 });

function mesh(g: THREE.BufferGeometry, m: THREE.Material, p: [number, number, number], r: [number, number, number] = [0, 0, 0]) {
  const o = new THREE.Mesh(g, m);
  o.position.set(...p);
  o.rotation.set(...r);
  o.castShadow = true;
  return o;
}

/** Aksesori dengan simpul pemasangan: `torso` (kepala/dada) atau tangan. Posisi lokal pada simpul itu (satuan model mentah). */
export function buildProp(kind: PropKind): { node: "torso" | "arm-left" | "arm-right"; object: THREE.Object3D } {
  const g = new THREE.Group();
  switch (kind) {
    case "headphones": {
      const m = mat("#0b1226", 0.2, 0.6);
      g.add(mesh(new THREE.TorusGeometry(0.47, 0.045, 8, 28, Math.PI), m, [0, 1.62, 0]));
      for (const sx of [-1, 1]) g.add(mesh(new THREE.BoxGeometry(0.14, 0.34, 0.34), mat("#00e5ff", 0.9), [sx * 0.47, 1.6, 0]));
      return { node: "torso", object: g };
    }
    case "headset": {
      const m = mat("#0b1226", 0.2, 0.6);
      g.add(mesh(new THREE.TorusGeometry(0.47, 0.04, 8, 28, Math.PI), m, [0, 1.62, 0]));
      g.add(mesh(new THREE.BoxGeometry(0.14, 0.3, 0.3), mat("#d946ef", 0.9), [-0.47, 1.6, 0]));
      g.add(mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.42, 6), m, [-0.42, 1.38, 0.2], [Math.PI / 2.4, 0, 0.5]));
      g.add(mesh(new THREE.SphereGeometry(0.055, 8, 6), mat("#d946ef", 1), [-0.3, 1.34, 0.4]));
      return { node: "torso", object: g };
    }
    case "magnifier": {
      g.add(mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.5, 8), mat("#3a2a14"), [0, -0.9, 0.35], [Math.PI / 2, 0, 0]));
      g.add(mesh(new THREE.TorusGeometry(0.26, 0.04, 8, 24), mat("#c9a227", 0.2, 0.8), [0, -0.9, 0.72]));
      g.add(mesh(new THREE.CircleGeometry(0.24, 20), new THREE.MeshBasicMaterial({ color: "#7fe9ff", transparent: true, opacity: 0.45 }), [0, -0.9, 0.72]));
      return { node: "arm-right", object: g };
    }
    case "clipboard": {
      g.add(mesh(new THREE.BoxGeometry(0.5, 0.68, 0.05), mat("#7a5a34"), [0, -0.85, 0.3], [-0.3, 0, 0]));
      g.add(mesh(new THREE.BoxGeometry(0.42, 0.58, 0.02), mat("#f2f6ff", 0.15), [0, -0.85, 0.34], [-0.3, 0, 0]));
      for (let i = 0; i < 4; i++) g.add(mesh(new THREE.BoxGeometry(0.3, 0.03, 0.01), mat("#3b82f6", 0.6), [0, -0.68 - i * 0.12, 0.355 + i * 0.0], [-0.3, 0, 0]));
      return { node: "arm-left", object: g };
    }
    case "stamp": {
      g.add(mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.16, 12), mat("#5a1a1a"), [0, -0.95, 0.25]));
      g.add(mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.06, 14), mat("#e03f5e", 0.5), [0, -1.08, 0.25]));
      g.add(mesh(new THREE.BoxGeometry(0.5, 0.68, 0.05), mat("#7a5a34"), [0, -0.9, 0.5], [-0.3, 0, 0]));
      return { node: "arm-left", object: g };
    }
    case "notebook": {
      g.add(mesh(new THREE.BoxGeometry(0.38, 0.5, 0.06), mat("#1f8f5f", 0.2), [0, -0.9, 0.28], [-0.35, 0, 0]));
      g.add(mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.4, 6), mat("#ffd166", 0.6), [0.08, -0.9, 0.38], [0.4, 0, -0.3]));
      return { node: "arm-left", object: g };
    }
    case "binoculars": {
      for (const sx of [-1, 1]) g.add(mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.42, 10), mat("#0b1226", 0.1, 0.6), [sx * 0.13, 0.78, 0.42], [Math.PI / 2, 0, 0]));
      g.add(mesh(new THREE.BoxGeometry(0.16, 0.08, 0.14), mat("#0b1226", 0.1, 0.6), [0, 0.78, 0.4]));
      for (const sx of [-1, 1]) g.add(mesh(new THREE.CircleGeometry(0.085, 12), new THREE.MeshBasicMaterial({ color: "#00e5ff" }), [sx * 0.13, 0.78, 0.64]));
      return { node: "torso", object: g };
    }
    case "megaphone": {
      g.add(mesh(new THREE.CylinderGeometry(0.1, 0.34, 0.5, 14, 1, true), mat("#d946ef", 0.5), [0, -0.9, 0.55], [Math.PI / 2, 0, 0]));
      g.add(mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.22, 10), mat("#0b1226"), [0, -0.9, 0.2], [Math.PI / 2, 0, 0]));
      return { node: "arm-right", object: g };
    }
    case "briefcase": {
      g.add(mesh(new THREE.BoxGeometry(0.62, 0.46, 0.18), mat("#2a2f55", 0.1, 0.4), [0.1, -1.18, 0]));
      g.add(mesh(new THREE.BoxGeometry(0.16, 0.04, 0.2), mat("#ffd166", 0.6, 0.8), [0.1, -0.95, 0]));
      g.add(mesh(new THREE.BoxGeometry(0.08, 0.05, 0.2), mat("#ffd166", 0.8, 0.8), [0.1, -1.18, 0.1]));
      return { node: "arm-left", object: g };
    }
    case "tablet": {
      g.add(mesh(new THREE.BoxGeometry(0.5, 0.64, 0.04), mat("#0b1226", 0.2, 0.6), [0, -0.85, 0.3], [-0.35, 0, 0]));
      g.add(mesh(new THREE.PlaneGeometry(0.42, 0.56), new THREE.MeshBasicMaterial({ color: "#8b5cf6" }), [0, -0.85, 0.325], [-0.35, 0, 0]));
      return { node: "arm-left", object: g };
    }
    case "crown": {
      const gold = mat("#ffd166", 0.8, 0.9);
      g.add(mesh(new THREE.CylinderGeometry(0.34, 0.38, 0.14, 12, 1, true), gold, [0, 2.06, 0]));
      for (let i = 0; i < 5; i++) {
        const a = (i / 5) * Math.PI * 2;
        g.add(mesh(new THREE.ConeGeometry(0.07, 0.2, 5), gold, [Math.sin(a) * 0.34, 2.2, Math.cos(a) * 0.34]));
      }
      g.add(mesh(new THREE.SphereGeometry(0.06, 8, 6), new THREE.MeshBasicMaterial({ color: "#ff3b6b" }), [0, 2.1, 0.38]));
      return { node: "torso", object: g };
    }
  }
}

/** Pasang aksesori pada simpul bernama di dalam model (struktur Kenney: root > torso > arm-left/arm-right/head). */
export function attachProps(model: THREE.Object3D, kinds: PropKind[]) {
  for (const kind of kinds) {
    const { node, object } = buildProp(kind);
    const target = model.getObjectByName(node);
    if (target) target.add(object);
  }
}
