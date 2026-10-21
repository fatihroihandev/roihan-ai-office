"use client";

import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { BRAND } from "@/lib/brand";

/** Tekstur tanda logo "R" (PNG bertransparan dari berkas identitas). Null sampai selesai dimuat. */
export function useLogoTexture(): THREE.Texture | null {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  useEffect(() => {
    let disposed = false;
    let loaded: THREE.Texture | null = null;
    new THREE.TextureLoader().load(BRAND.logoMark, (t) => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = 4;
      if (disposed) t.dispose();
      else {
        loaded = t;
        setTex(t);
      }
    });
    return () => {
      disposed = true;
      loaded?.dispose();
    };
  }, []);
  return tex;
}

/** Menunggu font merek siap sebelum menggambar teks ke kanvas (agar tidak jatuh ke font cadangan). */
export function useBrandFont(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let off = false;
    const done = () => !off && setReady(true);
    if (typeof document === "undefined" || !document.fonts) {
      done();
      return () => void (off = true);
    }
    Promise.all([document.fonts.load('800 64px "Montserrat Variable"'), document.fonts.load('600 32px "Montserrat Variable"')]).then(done, done);
    return () => void (off = true);
  }, []);
  return ready;
}

/** Kanvas papan merek: ROIHAN / TECHNOLOGIES / tagline dengan huruf lebar, sesuai berkas identitas. */
export function useWordmarkTexture(withTagline: boolean): THREE.CanvasTexture | null {
  const fontReady = useBrandFont();
  const tex = useMemo(() => {
    if (!fontReady) return null;
    const w = 1200;
    const h = withTagline ? 420 : 300;
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    const g = c.getContext("2d")!;
    g.textBaseline = "middle";
    g.textAlign = "left";
    const set = (font: string, spacing: string) => {
      g.font = font;
      (g as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = spacing;
    };
    set('800 150px "Montserrat Variable", Montserrat, sans-serif', "34px");
    g.fillStyle = "#ffffff";
    g.shadowColor = "rgba(0,229,255,0.55)";
    g.shadowBlur = 24;
    g.fillText(BRAND.name, 8, 100);
    set('600 54px "Montserrat Variable", Montserrat, sans-serif', "40px");
    const grad = g.createLinearGradient(0, 0, w * 0.85, 0);
    grad.addColorStop(0, "#00e5ff");
    grad.addColorStop(0.5, "#8b5cf6");
    grad.addColorStop(1, "#d946ef");
    g.fillStyle = grad;
    g.shadowColor = "rgba(139,92,246,0.7)";
    g.fillText(BRAND.sub, 12, 218);
    if (withTagline) {
      set('500 36px "Montserrat Variable", Montserrat, sans-serif', "20px");
      g.fillStyle = "#9fb0d8";
      g.shadowBlur = 8;
      g.fillText(BRAND.tagline, 12, 330);
    }
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [fontReady, withTagline]);
  useEffect(() => () => tex?.dispose(), [tex]);
  return tex;
}
