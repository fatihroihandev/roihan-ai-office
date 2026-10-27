"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useOfficeData } from "@/lib/office/useOfficeData";
import { seoApi, type Kpis, type SeoCampaign } from "@/lib/seoApi";
import { marketingApi } from "@/lib/marketingApi";
import { tasksApi, type Approval } from "@/lib/tasksApi";

import { SeoFeature } from "@/components/features/SeoFeature";
import { ContentFeature } from "@/components/features/ContentFeature";
import { LeadsFeature } from "@/components/features/LeadsFeature";
import { CampaignsFeature } from "@/components/features/CampaignsFeature";
import { ProjectsFeature } from "@/components/features/ProjectsFeature";
import { ProductsFeature } from "@/components/features/ProductsFeature";
import { ApprovalsFeature } from "@/components/features/ApprovalsFeature";
import { TasksFeature } from "@/components/features/TasksFeature";
import { OfficeFeature } from "@/components/features/OfficeFeature";
import { AiFeature } from "@/components/features/AiFeature";
import { SocialFeature } from "@/components/features/SocialFeature";
import { EmailFeature } from "@/components/features/EmailFeature";
import { AnalyticsFeature } from "@/components/features/AnalyticsFeature";
import { OperationsFeature } from "@/components/features/OperationsFeature";
import { SettingsFeature } from "@/components/features/SettingsFeature";

import { MarketingOverview } from "./MarketingOverview";
import { VIEW_IDS, type DashboardView } from "@/lib/dashboard/dock";

export function InspiredDashboard() {
  const { data } = useOfficeData();

  const [activeView, setActiveView] = useState<DashboardView>("overview");

  // Modals & toast state
  const [auditModalOpen, setAuditModalOpen] = useState(false);
  const [leadModalOpen, setLeadModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Quick Audit Form
  const [auditUrl, setAuditUrl] = useState("https://roihan.id");
  const [auditHtml, setAuditHtml] = useState(
    "<html><head><title>Roihan AI Office</title></head><body><h1>Marketing Operations Platform</h1></body></html>"
  );
  const [auditBusy, setAuditBusy] = useState(false);

  // Quick Lead Form
  const [leadCompany, setLeadCompany] = useState("");
  const [leadContact, setLeadContact] = useState("");
  const [leadEmail, setLeadEmail] = useState("");
  const [leadBusy, setLeadBusy] = useState(false);

  // Overview backend data
  const [approvalsList, setApprovalsList] = useState<Approval[]>([]);
  const [campaignsList, setCampaignsList] = useState<SeoCampaign[]>([]);
  const [kpis, setKpis] = useState<Kpis | null>(null);

  const navigateView = useCallback((view: DashboardView) => {
    setActiveView(view);
    const targetUrl = view === "overview" ? "/" : `/?view=${view}`;
    window.history.pushState({}, "", targetUrl);
    window.dispatchEvent(new CustomEvent<DashboardView>("roihan:view-changed", { detail: view }));
  }, []);

  // Sync view from initial ?view= query & AppShell navigation events
  useEffect(() => {
    const id = setTimeout(() => {
      const v = new URLSearchParams(window.location.search).get("view") as DashboardView | null;
      if (v && VIEW_IDS.includes(v)) {
        setActiveView(v);
        window.dispatchEvent(new CustomEvent<DashboardView>("roihan:view-changed", { detail: v }));
      }
    }, 0);

    const onNavigate = (e: Event) => {
      const next = (e as CustomEvent<DashboardView>).detail;
      if (next && VIEW_IDS.includes(next)) {
        setActiveView(next);
      }
    };
    window.addEventListener("roihan:navigate-view", onNavigate);
    return () => {
      clearTimeout(id);
      window.removeEventListener("roihan:navigate-view", onNavigate);
    };
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  useEffect(() => {
    tasksApi.approvals().then(setApprovalsList, () => undefined);
    seoApi.campaigns().then(setCampaignsList, () => undefined);
    seoApi.kpis().then(setKpis, () => undefined);
  }, []);

  const handleRunAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuditBusy(true);
    try {
      await seoApi.audit({ url: auditUrl, html: auditHtml });
      setAuditModalOpen(false);
      showToast("Audit SEO teknis berhasil diantrekan ke worker.");
    } catch (e) {
      showToast("Gagal memulai audit: " + (e as Error).message);
    } finally {
      setAuditBusy(false);
    }
  };

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadCompany.trim()) return;
    setLeadBusy(true);
    try {
      await marketingApi.createLead({
        company: { name: leadCompany, industry: "Technology", size_band: "medium" },
        contact: {
          name: leadContact || undefined,
          title: "Director",
          email: leadEmail || undefined,
          phone: undefined,
        },
        source: { source_type: "manual", url: undefined },
      });
      setLeadModalOpen(false);
      setLeadCompany("");
      setLeadContact("");
      setLeadEmail("");
      showToast("Prospek B2B baru berhasil dicatat ke dalam CRM.");
    } catch (e) {
      showToast("Gagal mencatat prospek: " + (e as Error).message);
    } finally {
      setLeadBusy(false);
    }
  };

  const pendingApprovals = approvalsList.filter((a) => a.status === "pending").length;

  return (
    <div className="inspired-dashboard-container">
      <div className="inspired-workspace">
        {/* 1. Command Center (Overview) */}
        {activeView === "overview" && (
          <MarketingOverview
            data={data}
            kpis={kpis}
            campaigns={campaignsList}
            pendingApprovals={pendingApprovals}
            onNavigate={navigateView}
            onAudit={() => setAuditModalOpen(true)}
            onLead={() => setLeadModalOpen(true)}
          />
        )}

        {/* 2. Canonical Marketing Modules */}
        {activeView === "seo" && (
          <div className="feature-view-container">
            <SeoFeature />
          </div>
        )}
        {activeView === "content" && (
          <div className="feature-view-container">
            <ContentFeature />
          </div>
        )}
        {activeView === "social" && (
          <div className="feature-view-container">
            <SocialFeature />
          </div>
        )}
        {activeView === "campaigns" && (
          <div className="feature-view-container">
            <CampaignsFeature />
          </div>
        )}
        {activeView === "leads" && (
          <div className="feature-view-container">
            <LeadsFeature />
          </div>
        )}
        {activeView === "email" && (
          <div className="feature-view-container">
            <EmailFeature />
          </div>
        )}
        {activeView === "analytics" && (
          <div className="feature-view-container">
            <AnalyticsFeature />
          </div>
        )}
        {activeView === "operations" && (
          <div className="feature-view-container">
            <OperationsFeature />
          </div>
        )}
        {activeView === "settings" && (
          <div className="feature-view-container">
            <SettingsFeature />
          </div>
        )}

        {/* 3. Supporting Views */}
        {activeView === "projects" && (
          <div className="feature-view-container">
            <ProjectsFeature />
          </div>
        )}
        {activeView === "products" && (
          <div className="feature-view-container">
            <ProductsFeature />
          </div>
        )}
        {activeView === "approvals" && (
          <div className="feature-view-container">
            <ApprovalsFeature />
          </div>
        )}
        {activeView === "tasks" && (
          <div className="feature-view-container">
            <TasksFeature />
          </div>
        )}
        {activeView === "office" && (
          <div className="feature-view-container">
            <Suspense fallback={null}>
              <OfficeFeature />
            </Suspense>
          </div>
        )}
        {activeView === "ai" && (
          <div className="feature-view-container">
            <AiFeature />
          </div>
        )}
      </div>

      {/* Quick Audit Modal */}
      {auditModalOpen && (
        <div
          className="inspired-modal-backdrop"
          onClick={() => setAuditModalOpen(false)}
        >
          <div className="inspired-modal" onClick={(e) => e.stopPropagation()}>
            <div className="inspired-modal-header">
              <h3>Jalankan Audit SEO Teknis</h3>
              <button
                type="button"
                className="inspired-modal-close"
                onClick={() => setAuditModalOpen(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleRunAudit}>
              <div className="inspired-form-group">
                <label>URL Website Target (Perlindungan SSRF Aktif)</label>
                <input
                  type="url"
                  className="inspired-form-input"
                  value={auditUrl}
                  onChange={(e) => setAuditUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                />
              </div>
              <div className="inspired-form-group">
                <label>Snapshot Konten HTML</label>
                <textarea
                  rows={4}
                  className="inspired-form-textarea"
                  value={auditHtml}
                  onChange={(e) => setAuditHtml(e.target.value)}
                  required
                />
              </div>
              <div className="inspired-modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setAuditModalOpen(false)}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="btn-primary-orange"
                  disabled={auditBusy}
                >
                  {auditBusy ? "Memproses..." : "Jalankan Audit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Quick Lead Modal */}
      {leadModalOpen && (
        <div
          className="inspired-modal-backdrop"
          onClick={() => setLeadModalOpen(false)}
        >
          <div className="inspired-modal" onClick={(e) => e.stopPropagation()}>
            <div className="inspired-modal-header">
              <h3>Catat Prospek B2B Baru</h3>
              <button
                type="button"
                className="inspired-modal-close"
                onClick={() => setLeadModalOpen(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateLead}>
              <div className="inspired-form-group">
                <label>Nama Perusahaan</label>
                <input
                  type="text"
                  className="inspired-form-input"
                  value={leadCompany}
                  onChange={(e) => setLeadCompany(e.target.value)}
                  placeholder="PT Sinar Gemilang"
                  required
                />
              </div>
              <div className="inspired-form-group">
                <label>Nama Kontak Bisnis (Opsional)</label>
                <input
                  type="text"
                  className="inspired-form-input"
                  value={leadContact}
                  onChange={(e) => setLeadContact(e.target.value)}
                  placeholder="Budi Setiawan"
                />
              </div>
              <div className="inspired-form-group">
                <label>Email Kontak Kantor (Opsional)</label>
                <input
                  type="email"
                  className="inspired-form-input"
                  value={leadEmail}
                  onChange={(e) => setLeadEmail(e.target.value)}
                  placeholder="budi@example.com"
                />
              </div>
              <div className="inspired-modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setLeadModalOpen(false)}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="btn-primary-orange"
                  disabled={leadBusy || !leadCompany.trim()}
                >
                  {leadBusy ? "Menyimpan..." : "Simpan Prospek ke CRM"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className="inspired-toast" role="status">
          <span>✓</span>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
