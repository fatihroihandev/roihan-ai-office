// Template Next.js dibuat ulang pada setiap navigasi: memberi transisi masuk halaman bergaya "boot" (memudar + garis pindai).
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
