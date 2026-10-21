"use client";

import { PageTransition } from "@/components/ui/PageTransition";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { INTERACTION_KINDS, marketingApi, NEXT_LEAD, NEXT_STAGE, type Lead } from "@/lib/marketingApi";
import { productsApi, type Product } from "@/lib/productsApi";
import { useLanguage } from "@/i18n/LanguageProvider";
import type { MessageKey } from "@/i18n/dictionaries";

export default function LeadDetailPage() {
  const { t } = useLanguage();
  const label = (key: string) => t(key as MessageKey);
  const { id } = useParams<{ id: string }>();
  const [lead, setLead] = useState<Lead | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [kind, setKind] = useState<string>("call");
  const [summary, setSummary] = useState("");
  const [reason, setReason] = useState("");
  const [override, setOverride] = useState("");
  const [draftProduct, setDraftProduct] = useState("");
  const [oppTitle, setOppTitle] = useState("");
  const [oppValue, setOppValue] = useState("");
  const [stageReason, setStageReason] = useState("");
  const [wonValue, setWonValue] = useState("");
  const [req, setReq] = useState("");
  const [handedOff, setHandedOff] = useState<string[]>([]);

  const load = useCallback(async (reveal: boolean) => {
    setLead(await marketingApi.lead(id, reveal));
  }, [id]);

  useEffect(() => {
    let cancelled = false;
    marketingApi.lead(id, false).then((l) => !cancelled && setLead(l), (e: Error) => !cancelled && setError(e.message));
    productsApi.list().then((p) => !cancelled && setProducts(p), () => undefined);
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function run(action: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      if (done) setNotice(done);
      await load(revealed);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!lead) return <PageTransition>
<main>{error ? <p className="bad" role="alert">{error}</p> : <p>{t("common.loading")}</p>}</main>
</PageTransition>;

  const closed = lead.anonymized || lead.do_not_contact;
  const nexts = NEXT_LEAD[lead.status] ?? [];
  const canForward = ["qualified", "contacted", "meeting"].includes(lead.status) && !closed;

  return (
    <PageTransition>
<main>
      <p><Link href="/marketing">← {t("mkt.lead.back")}</Link></p>
      <h2>{lead.company.name}</h2>
      <div className="chips">
        <span className="badge">{label(`mkt.status.${lead.status}`)}</span>
        <span className="badge">{t("mkt.score")} {lead.score ?? "-"}</span>
        {lead.forwarded_at && <span className="badge" data-task="completed">{t("mkt.lead.forwarded")}</span>}
        {lead.do_not_contact && <span className="badge" data-task="failed">{t("mkt.lead.dnc")}</span>}
        {lead.anonymized && <span className="badge">{t("mkt.lead.anonymized")}</span>}
      </div>
      {error && <p className="bad" role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}

      <section className="card">
        <h3>{t("mkt.lead.contact")}</h3>
        <dl>
          <dt>{t("mkt.contactName")}</dt><dd>{lead.contact.name ?? "-"}</dd>
          <dt>{t("mkt.contactTitle")}</dt><dd>{lead.contact.title ?? "-"}</dd>
          <dt>{t("mkt.contactEmail")}</dt><dd>{lead.contact.email ?? "-"}</dd>
          <dt>{t("mkt.contactPhone")}</dt><dd>{lead.contact.phone ?? "-"}</dd>
        </dl>
        {!lead.anonymized && (
          lead.contact.masked ? (
            <>
              <p className="small muted">{t("mkt.lead.masked")}</p>
              <button type="button" disabled={busy} onClick={() => void (async () => { setRevealed(true); await load(true); })()}>{t("mkt.lead.reveal")}</button>
            </>
          ) : (
            <button type="button" onClick={() => void (async () => { setRevealed(false); await load(false); })()}>{t("mkt.lead.hide")}</button>
          )
        )}
      </section>

      <section className="card">
        <h3>{t("mkt.lead.provenance")}</h3>
        <dl>
          <dt>{t("mkt.sourceType")}</dt><dd>{label(`mkt.source.${lead.source.type}`)}</dd>
          <dt>URL</dt><dd>{lead.source.url ? <a href={lead.source.url} rel="noopener noreferrer" target="_blank">{lead.source.url}</a> : "-"}</dd>
          <dt>{t("mkt.lead.collected")}</dt><dd>{new Date(lead.source.collected_at).toLocaleString()} {t("mkt.lead.by")} {lead.source.collected_by} ({lead.source.method})</dd>
          <dt>{t("mkt.lead.basis")}</dt><dd>{lead.basis}</dd>
        </dl>
        <h4>{t("mkt.lead.breakdown")}</h4>
        <table>
          <tbody>
            {(lead.score_breakdown ?? []).map((r) => (
              <tr key={r.factor}><td>{r.factor}</td><td>{r.points}/{r.max}</td><td className="small muted">{r.note}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h3>{t("mkt.lead.interactions")}</h3>
        <p className="small muted">{t("mkt.lead.interactions.hint")}</p>
        <ul>
          {(lead.interactions ?? []).map((i) => (
            <li key={i.id}><span className="badge">{label(`mkt.kind.${i.kind}`)}</span> {new Date(i.occurred_at).toLocaleString()} — {i.summary}</li>
          ))}
        </ul>
        {!lead.anonymized && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => { await marketingApi.interact(lead.id, kind, summary); setSummary(""); });
            }}
          >
            <div className="row">
              <label>
                {t("mkt.lead.kind")}
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  {INTERACTION_KINDS.map((k) => <option key={k} value={k}>{label(`mkt.kind.${k}`)}</option>)}
                </select>
              </label>
              <label>{t("mkt.lead.summary")}<input value={summary} maxLength={4000} onChange={(e) => setSummary(e.target.value)} required /></label>
            </div>
            <button type="submit" disabled={busy || !summary.trim()}>{t("mkt.lead.addInteraction")}</button>
          </form>
        )}
      </section>

      {!closed && (
        <section className="card">
          <h3>{t("mkt.lead.actions")}</h3>
          <div className="row">
            <label>{t("mkt.lead.reason")}<input value={reason} onChange={(e) => setReason(e.target.value)} /></label>
            <label>{t("mkt.lead.override")}<input value={override} onChange={(e) => setOverride(e.target.value)} /></label>
          </div>
          {nexts.length > 0 && (
            <div className="actions">
              <span className="muted">{t("mkt.lead.setStatus")}:</span>
              {nexts.map((n) => (
                <button key={n} type="button" disabled={busy} onClick={() => void run(() => marketingApi.setStatus(lead.id, n, reason, override))}>{label(`mkt.status.${n}`)}</button>
              ))}
            </div>
          )}
          {canForward && !lead.forwarded_at && (
            <div className="row">
              <label>
                {t("mkt.lead.forwardDraft")}
                <select value={draftProduct} onChange={(e) => setDraftProduct(e.target.value)}>
                  <option value="">{t("mkt.lead.noProduct")}</option>
                  {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <button
                type="button" disabled={busy}
                onClick={() => void run(() => marketingApi.forward(lead.id, override, draftProduct || undefined), draftProduct ? t("mkt.taskQueued") : undefined)}
              >
                {t("mkt.lead.forward")}
              </button>
            </div>
          )}
          <div className="actions">
            <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.optOut(lead.id, reason))}>{t("mkt.lead.optOut")}</button>
            <button
              type="button" disabled={busy}
              onClick={() => window.confirm(t("mkt.lead.eraseConfirm")) && void run(() => marketingApi.erase(lead.id, reason))}
            >
              {t("mkt.lead.erase")}
            </button>
          </div>
        </section>
      )}

      {lead.anonymized && <p className="muted">{t("mkt.lead.anonymized")}</p>}

      {canForward && (
        <form
          className="card"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => { await marketingApi.convert(lead.id, oppTitle, oppValue ? Number(oppValue) : undefined); setOppTitle(""); setOppValue(""); });
          }}
        >
          <h3>{t("mkt.lead.convert")}</h3>
          <div className="row">
            <label>{t("mkt.lead.oppTitle")}<input value={oppTitle} onChange={(e) => setOppTitle(e.target.value)} required /></label>
            <label>{t("mkt.lead.oppValue")}<input type="number" min={0} value={oppValue} onChange={(e) => setOppValue(e.target.value)} /></label>
          </div>
          <button type="submit" disabled={busy || !oppTitle.trim()}>{t("mkt.lead.convert")}</button>
        </form>
      )}

      {(lead.opportunities ?? []).map((o) => (
        <section key={o.id} className="card">
          <h3>{o.title} <span className="badge">{label(`mkt.stage.${o.stage}`)}</span></h3>
          {o.outcome_reason && <p className="small muted">{o.outcome_reason}</p>}
          {(NEXT_STAGE[o.stage] ?? []).length > 0 && (
            <>
              <div className="row">
                <label>{t("mkt.lead.reason")}<input value={stageReason} onChange={(e) => setStageReason(e.target.value)} /></label>
                <label>{t("mkt.lead.wonValue")}<input type="number" min={0} value={wonValue} onChange={(e) => setWonValue(e.target.value)} /></label>
              </div>
              <div className="actions">
                {(NEXT_STAGE[o.stage] ?? []).map((st) => (
                  <button key={st} type="button" disabled={busy} onClick={() => void run(() => marketingApi.stage(o.id, st, stageReason, wonValue ? Number(wonValue) : undefined))}>
                    {t("mkt.lead.stage")}: {label(`mkt.stage.${st}`)}
                  </button>
                ))}
              </div>
            </>
          )}
          {o.stage === "won" && (
            <div>
              <p className="small muted">{t("ext.handoff.hint")}</p>
              <button type="button" disabled={busy || handedOff.includes(o.id)} onClick={() => void run(async () => { await marketingApi.handoff(o.id); setHandedOff((h) => [...h, o.id]); }, t("ext.handoff.done"))}>
                {handedOff.includes(o.id) ? t("ext.handoff.done") : t("ext.handoff")}
              </button>
            </div>
          )}
          <h4>{t("mkt.lead.requirements")}</h4>
          <ul>{o.requirements.map((r) => <li key={r.id}>{r.text}</li>)}</ul>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => { await marketingApi.requirement(o.id, req); setReq(""); });
            }}
          >
            <label><input value={req} onChange={(e) => setReq(e.target.value)} required /></label>
            <button type="submit" disabled={busy || !req.trim()}>{t("mkt.lead.addRequirement")}</button>
          </form>
        </section>
      ))}

      {(lead.outreach ?? []).length > 0 && (
        <section className="card">
          <h3>{t("mkt.outreach")}</h3>
          {(lead.outreach ?? []).map((d) => (
            <div key={d.id}>
              <strong>{d.subject}</strong> <span className="badge">{label(`mkt.ostatus.${d.status}`)}</span>
              <pre className="output">{d.body}</pre>
              {d.claim_check && !d.claim_check.ok && (
                <ul className="small bad">{d.claim_check.findings.map((f, i) => <li key={i}>{f.detail}{f.match ? ` — “${f.match}”` : ""}</li>)}</ul>
              )}
              {d.status === "ready_for_review" && (
                <div className="actions">
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.requestSend(d.id), t("ext.requested"))}>{t("ext.requestSend")}</button>
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.markSent(d.id))}>{t("mkt.outreach.markSent")}</button>
                  <button type="button" disabled={busy} onClick={() => void run(() => marketingApi.cancelOutreach(d.id))}>{t("mkt.outreach.cancel")}</button>
                </div>
              )}
            </div>
          ))}
        </section>
      )}
    </main>
</PageTransition>
  );
}
