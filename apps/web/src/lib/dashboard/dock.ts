// Daftar menu dock kanonis Master Addendum v2.0
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

export const DOCK: { view: DashboardView; icon: string; title: string }[] = [
  { view: "overview", icon: "⊞", title: "Command Center" },
  { view: "seo", icon: "🌐", title: "Website & Growth" },
  { view: "content", icon: "✍️", title: "Content Studio" },
  { view: "social", icon: "📱", title: "Social Media" },
  { view: "campaigns", icon: "🚀", title: "Campaigns & Ads" },
  { view: "leads", icon: "👥", title: "Leads & CRM" },
  { view: "email", icon: "✉️", title: "Email & Automation" },
  { view: "analytics", icon: "📊", title: "Analytics & Intel" },
  { view: "operations", icon: "🛡️", title: "Operations" },
  { view: "settings", icon: "⚙️", title: "Settings & AI" },
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
