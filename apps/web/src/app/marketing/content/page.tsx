"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import {
  CONTENT_KINDS, marketingApi, type Campaign, type ContentAsset, type OutboundMessage, type Policy,
} from "@/lib/marketingApi";
import { productsApi, type Product } from "@/lib/productsApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function ContentPage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [contents, setContents] = useState<ContentAsset[] | null>(null);
  const [box, setBox] = useState<OutboundMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [productId, setProductId] = useState("");
  const [kind, setKind] = useState<string>("social_post");
  const [channel, setChannel] = useState("linkedin");
  const [campaignId, setCampaignId] = useState("");
  const [title, setTitle] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [angle, setAngle] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editBody, setEditBody] = useState("");

  const [cName, setCName] = useState("");
  const [cObjective, setCObjective] = useState("");
  const [cChannels, setCChannels] = useState("linkedin");

  const fetchAll = useCallback(
    () => Promise.all([marketingApi.contents(), marketingApi.campaigns(), marketingApi.outbox()]),
    [],
  );
  const apply = useCallback(([c, camp, ob]: Awaited<ReturnType<typeof fetchAll>>) => {
    setContents(c); setCampaigns(camp); setBox(ob);
  }, []);

  useEffect(() => {
    let cancelled = false;
    marketingApi.policy().then((p) => !cancelled && setPolicy(p), () => undefined);
    productsApi.list().then((p) => !cancelled && setProducts(p), () => undefined);
    fetchAll().then((d) => !cancelled && apply(d), (e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [fetchAll, apply]);

  async function run(action: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      if (done) setNotice(done);
      apply(await fetchAll());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const product = productId || products[0]?.id || "";
  const ext = policy?.external;

  return (
    <main>
      <AppHeader />
      <p><Link href="/marketing">← {t("ext.back")}</Link></p>
      <h2>{t("ext.title")}</h2>
      <p className="muted">{t("ext.hint")}</p>
      {error && <p className="bad" role="alert">{error}</p>}
      {notice && <p role="status">{notice} <Link href="/approvals">{t("nav.approvals")}</Link></p>}

      {ext && (
        <section className="card">
          <h3>{t("ext.policy")}</h3>
          <p className="small">
            {t("ext.policy.line")
              .replace("{c}", ext.content_channels.join(", ")).replace("{o}", ext.outreach_channels.join(", "))
              .replace("{p}", String(ext.content_max_publish_per_day)).replace("{d}", String(ext.outreach_max_per_day))
              .replace("{n}", String(ext.outreach_min_days_between_contacts))}
          </p>
        </section>
      )}

      <section className="card">
        <h3>{t("ext.outbox")}</h3>
        {box.length === 0 && <p className="muted">{t("ext.outbox.empty")}</p>}
        <ul className="list">
          {box.map((m) => (
            <li key={m.id} className="card">
              <div>
                <strong>{m.subject}</strong>
                <span className="badge">{m.kind}/{m.channel}</span>
                <span className="badge" data-task={m.status === "cancelled" ? "failed" : "completed"}>{label(`ext.obstatus.${m.status}`)}</span>
                <pre className="output">{m.body}</pre>
              </div>
              {m.status === "queued_manual" && (
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.dispatch(m.id))}>{t("ext.outbox.dispatch")}</button>
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.cancelOutbox(m.id))}>{t("ext.outbox.cancel")}</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>{t("ext.campaigns")}</h3>
        {campaigns.length === 0 && <p className="muted">{t("ext.campaigns.empty")}</p>}
        <ul className="list">
          {campaigns.map((c) => (
            <li key={c.id} className="card">
              <div>
                <strong>{c.name}</strong>
                <span className="badge">{label(`ext.campstatus.${c.status}`)}</span>
                <div className="small muted">{c.channels.join(", ")}</div>
              </div>
              <Link className="button" href={`/marketing/campaigns/${c.id}`}>{t("ext.campaign.open")}</Link>
            </li>
          ))}
        </ul>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await marketingApi.createCampaign({
                name: cName, product_id: product, objective: cObjective, channels: cChannels.split(",").map((x) => x.trim()).filter(Boolean),
              });
              setCName(""); setCObjective("");
            });
          }}
        >
          <h4>{t("ext.campaigns.new")}</h4>
          <div className="row">
            <label>{t("ext.campaign.name")}<input value={cName} onChange={(e) => setCName(e.target.value)} required maxLength={120} /></label>
            <label>{t("ext.product")}
              <select value={product} onChange={(e) => setProductId(e.target.value)}>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          </div>
          <label>{t("ext.campaign.objective")}<input value={cObjective} onChange={(e) => setCObjective(e.target.value)} /></label>
          <label>{t("ext.campaign.channels")}<input value={cChannels} onChange={(e) => setCChannels(e.target.value)} /></label>
          <p className="small muted">{t("ext.campaign.budget")}</p>
          <button type="submit" disabled={busy || !cName.trim() || !product}>{t("ext.campaign.create")}</button>
        </form>
      </section>

      <section className="card">
        <h3>{t("ext.content")}</h3>
        {contents === null && !error && <p>{t("common.loading")}</p>}
        {contents?.length === 0 && <p className="muted">{t("ext.content.empty")}</p>}
        <ul className="list">
          {(contents ?? []).map((a) => (
            <li key={a.id} className="card">
              <div>
                <strong>{a.title}</strong>
                <span className="badge">{label(`ext.kind.${a.kind}`)} · {a.channel}</span>
                <span className="badge" data-task={a.status === "ready_for_review" || a.status === "published_manual" ? "completed" : "failed"}>{label(`ext.cstatus.${a.status}`)}</span>
                {editing === a.id ? (
                  <label><textarea rows={6} value={editBody} onChange={(e) => setEditBody(e.target.value)} /></label>
                ) : (
                  <pre className="output">{a.body}</pre>
                )}
                {a.claim_check && !a.claim_check.ok && (
                  <div className="small bad">
                    {t("ext.claimIssues")}:
                    <ul>{a.claim_check.findings.map((f, i) => <li key={i}>{f.detail}{f.match ? ` — “${f.match}”` : ""}</li>)}</ul>
                  </div>
                )}
              </div>
              <div className="actions">
                {["draft", "blocked_by_claim_check", "ready_for_review"].includes(a.status) && (
                  editing === a.id ? (
                    <button type="button" disabled={busy} onClick={() => void run(async () => { await marketingApi.updateContent(a.id, { body: editBody }); setEditing(null); })}>{t("ext.save")}</button>
                  ) : (
                    <button type="button" onClick={() => { setEditing(a.id); setEditBody(a.body); }}>{t("ext.edit")}</button>
                  )
                )}
                {a.status === "ready_for_review" && (
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.requestPublish(a.id), t("ext.requested"))}>{t("ext.requestPublish")}</button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>{t("ext.content.agent")}</h3>
        <p className="muted small">{t("ext.content.agent.hint")}</p>
        <div className="row">
          <label>{t("ext.product")}
            <select value={product} onChange={(e) => setProductId(e.target.value)}>
              {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label>{t("ext.kind")}
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {CONTENT_KINDS.map((k) => <option key={k} value={k}>{label(`ext.kind.${k}`)}</option>)}
            </select>
          </label>
          <label>{t("ext.channel")}
            <select value={channel} onChange={(e) => setChannel(e.target.value)}>
              {(ext?.content_channels ?? ["linkedin"]).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label>{t("ext.campaign")}
            <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)}>
              <option value="">{t("ext.noCampaign")}</option>
              {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
        </div>
        <label>{t("ext.angle")}<input value={angle} maxLength={500} onChange={(e) => setAngle(e.target.value)} /></label>
        <button
          type="button" disabled={busy || !product}
          onClick={() => void run(() => marketingApi.contentTask({ product_id: product, kind, channel, angle, campaign_id: campaignId }))}
        >
          {t("ext.draft")}
        </button>

        <h4>{t("ext.content.new")}</h4>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await marketingApi.createContent({ product_id: product, kind, channel, title, body: bodyText, campaign_id: campaignId });
              setTitle(""); setBodyText("");
            });
          }}
        >
          <label>{t("ext.titleField")}<input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} required /></label>
          <label>{t("ext.bodyField")}<textarea rows={5} value={bodyText} onChange={(e) => setBodyText(e.target.value)} required /></label>
          <button type="submit" disabled={busy || !product || !title.trim() || !bodyText.trim()}>{t("ext.create")}</button>
        </form>
      </section>
    </main>
  );
}
