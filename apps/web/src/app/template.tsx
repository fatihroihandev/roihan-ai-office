// Template dibuat ulang pada setiap navigasi: memicu garis pindai neon yang menyapu layar (animasi CSS murni).
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div className="wipe" aria-hidden="true" />
      {children}
    </>
  );
}
