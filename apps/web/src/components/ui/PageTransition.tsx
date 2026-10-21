"use client";

import { ViewTransition, type ReactNode } from "react";

// Transisi antarhalaman memakai View Transitions API lewat <ViewTransition> React: menu yang lebih kanan membuat halaman bergeser ke kiri
// (nav-forward), menu yang lebih kiri ke kanan (nav-back), navigasi lain memudar halus. Tanpa dukungan peramban: berpindah biasa.
const kinds = { "nav-forward": "nav-forward", "nav-back": "nav-back", default: "page-fade" } as const;

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <ViewTransition enter={kinds} exit={kinds} default="none">
      {children}
    </ViewTransition>
  );
}
