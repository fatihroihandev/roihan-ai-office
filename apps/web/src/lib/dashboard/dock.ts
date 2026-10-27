// Daftar menu dock tunggal; dipakai dashboard dan halaman detail agar menu selalu sama.
export type DashboardView = "overview" | "seo" | "content" | "leads" | "campaigns" | "projects" | "products" | "approvals" | "tasks" | "office" | "ai";

export const DOCK: { view: DashboardView; icon: string; title: string }[] = [
  { view: "overview", icon: "⊞", title: "Overview" },
  { view: "seo", icon: "🌐", title: "Website & SEO" },
  { view: "content", icon: "✍️", title: "Content Studio" },
  { view: "leads", icon: "👥", title: "Leads & CRM" },
  { view: "campaigns", icon: "🚀", title: "Kampanye & Analitik" },
  { view: "projects", icon: "📁", title: "Proyek" },
  { view: "products", icon: "📦", title: "Produk" },
  { view: "approvals", icon: "🛡️", title: "Pusat Persetujuan" },
  { view: "tasks", icon: "📋", title: "Tugas & Antrean Worker" },
  { view: "office", icon: "🏢", title: "Kantor Virtual" },
  { view: "ai", icon: "⚙️", title: "AI Core & Integrasi" },
];

export const VIEW_IDS = DOCK.map((d) => d.view);
