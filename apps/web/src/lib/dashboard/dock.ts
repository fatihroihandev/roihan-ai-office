// Daftar menu navigasi kanonis Roihan AI Office (Addendum v2.0 & v2.4)
export type DashboardView =
  | "overview"
  | "seo"
  | "content"
  | "social"
  | "campaigns"
  | "leads"
  | "email"
  | "analytics"
  | "operations"
  | "settings"
  | "projects"
  | "products"
  | "approvals"
  | "tasks"
  | "office"
  | "ai";

export type NavGroupKey = "strategy" | "content_growth" | "crm_outreach" | "system";

export interface DockItem {
  view: DashboardView;
  icon: string;
  title: string;
  subtitle: string;
  group: NavGroupKey;
}

export const NAV_GROUPS: { key: NavGroupKey; label: string }[] = [
  { key: "strategy", label: "Komando & Kampanye" },
  { key: "content_growth", label: "Pertumbuhan & Konten" },
  { key: "crm_outreach", label: "Prospek & Otomatisasi" },
  { key: "system", label: "Analitik & Operasi" },
];

export const DOCK: DockItem[] = [
  {
    view: "overview",
    icon: "grid",
    title: "Command Center",
    subtitle: "Ringkasan eksekutif, KPI utama, dan prioritas tindakan pemasaran",
    group: "strategy",
  },
  {
    view: "campaigns",
    icon: "target",
    title: "Campaigns & Ads",
    subtitle: "Perencanaan kampanye lintas kanal, riset pasar, dan anggaran",
    group: "strategy",
  },
  {
    view: "seo",
    icon: "globe",
    title: "Website & Growth",
    subtitle: "Audit SEO teknis, riset kata kunci, dan optimasi halaman",
    group: "content_growth",
  },
  {
    view: "content",
    icon: "pen",
    title: "Content Studio",
    subtitle: "Brief konten, penulisan artikel AI, dan pemeriksaan klaim produk",
    group: "content_growth",
  },
  {
    view: "social",
    icon: "share",
    title: "Social Media",
    subtitle: "Jadwal publikasi multi-platform, akun terhubung, dan interaksi",
    group: "content_growth",
  },
  {
    view: "leads",
    icon: "users",
    title: "Leads & CRM",
    subtitle: "Pipeline prospek B2B, kualifikasi skor, peluang, dan kepatuhan UU PDP",
    group: "crm_outreach",
  },
  {
    view: "email",
    icon: "mail",
    title: "Email & Automation",
    subtitle: "Kampanye email terarah, segmentasi audiens, dan alur kerja pemicu",
    group: "crm_outreach",
  },
  {
    view: "analytics",
    icon: "chart",
    title: "Analytics & Intel",
    subtitle: "Corong konversi penuh, atribusi kanal, ROI riil, dan ekspor CSV",
    group: "system",
  },
  {
    view: "operations",
    icon: "shield",
    title: "Operations",
    subtitle: "Persetujuan tindakan berisiko (Approval), antrean tugas AI, dan konektor",
    group: "system",
  },
  {
    view: "settings",
    icon: "sliders",
    title: "Settings & AI",
    subtitle: "Konfigurasi provider AI, anggaran bulanan, peran spesialis, dan keamanan",
    group: "system",
  },
];

export const VIEW_IDS: DashboardView[] = [
  "overview",
  "seo",
  "content",
  "social",
  "campaigns",
  "leads",
  "email",
  "analytics",
  "operations",
  "settings",
  "projects",
  "products",
  "approvals",
  "tasks",
  "office",
  "ai",
];

export const VIEW_META: Record<DashboardView, { title: string; subtitle: string; groupLabel: string }> = {
  overview: {
    title: "Command Center",
    subtitle: "Pusat komando pemasaran terpadu, ringkasan KPI, dan prioritas eksekusi harian",
    groupLabel: "Komando & Kampanye",
  },
  campaigns: {
    title: "Campaigns & Advertising",
    subtitle: "Perencanaan kampanye pemasaran, eksperimen kreatif, dan manajemen riset pasar",
    groupLabel: "Komando & Kampanye",
  },
  seo: {
    title: "Website & Growth (SEO)",
    subtitle: "Audit teknis website, pemantauan kata kunci, dan rekomendasi optimasi organik",
    groupLabel: "Pertumbuhan & Konten",
  },
  content: {
    title: "Content Studio",
    subtitle: "Penyusunan brief, draf artikel & media sosial, serta verifikasi klaim promosi",
    groupLabel: "Pertumbuhan & Konten",
  },
  social: {
    title: "Social Media Hub",
    subtitle: "Manajemen akun sosial resmi, antrean jadwal publikasi, dan metrik keterlibatan",
    groupLabel: "Pertumbuhan & Konten",
  },
  leads: {
    title: "Leads & CRM Pipeline",
    subtitle: "Pengelolaan prospek B2B, penilaian kesiapan sales, peluang deal, dan privasi data",
    groupLabel: "Prospek & Otomatisasi",
  },
  email: {
    title: "Email Marketing & Automation",
    subtitle: "Pengiriman kampanye email, daftar supresi, alur otomatisasi, dan deliverability",
    groupLabel: "Prospek & Otomatisasi",
  },
  analytics: {
    title: "Analytics & Intelligence",
    subtitle: "Evaluasi performa lintas kanal, corong konversi, atribusi, dan laporan ROI",
    groupLabel: "Analitik & Operasi",
  },
  operations: {
    title: "Operations & Approvals",
    subtitle: "Pengawasan eksekusi agen AI, persetujuan tindakan sensitif, dan status konektor",
    groupLabel: "Analitik & Operasi",
  },
  settings: {
    title: "Settings & AI Core",
    subtitle: "Pengaturan provider model AI, batas anggaran, tim spesialis, dan tata kelola",
    groupLabel: "Analitik & Operasi",
  },
  projects: {
    title: "Proyek & Aset Kampanye",
    subtitle: "Ruang kerja dokumen, berkas pendukung, dan repositori materi pemasaran",
    groupLabel: "Analitik & Operasi",
  },
  products: {
    title: "Katalog Produk & Layanan",
    subtitle: "Manajemen produk, klaim fitur terverifikasi, dan kesiapan gerbang promosi",
    groupLabel: "Komando & Kampanye",
  },
  approvals: {
    title: "Pusat Persetujuan (Approvals)",
    subtitle: "Tinjau dan setujui tindakan berdampak eksternal sebelum dieksekusi",
    groupLabel: "Analitik & Operasi",
  },
  tasks: {
    title: "Log & Antrean Tugas AI",
    subtitle: "Pemantauan tugas agen secara langsung, riwayat eksekusi, dan status worker",
    groupLabel: "Analitik & Operasi",
  },
  office: {
    title: "Visualisasi Ruang Kerja",
    subtitle: "Pemantauan status agen secara visual dan kontrol daya operasional",
    groupLabel: "Analitik & Operasi",
  },
  ai: {
    title: "AI Provider & Cost Control",
    subtitle: "Manajemen kunci API provider, sinkronisasi model, dan pemakaian token",
    groupLabel: "Analitik & Operasi",
  },
};
