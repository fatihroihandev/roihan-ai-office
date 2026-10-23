"""Executor SEO Specialist dan Marketing Analytics (Phase 14). Keduanya hanya MENGHASILKAN artefak untuk ditinjau:
tidak mengubah kode produksi, tidak memublikasikan, dan tidak mengirim apa pun (publikasi tetap lewat Content & Promotion + approval).
"""
import asyncio

from pydantic import BaseModel, Field, ValidationError
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.db.models import MarketingArtifact, SeoCampaignEvent, SeoKeyword, SeoRecommendation, Site
from app.marketing import access, seo, sites
from app.marketing.agents import _EMAIL_IN_TEXT, MAX_MATERIAL, _brief, _params
from app.marketing.privacy import PolicyError, assert_clean
from app.products.claims import check_claims
from app.tasks.executors import ExecutionContext, ExecutorError, ExecutorOutcome, extract_json
from app.web.guard import WebError

KEYWORD_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}, "items": {"type": "array", "maxItems": 25, "items": {
        "type": "object",
        "properties": {"keyword": {"type": "string"}, "intent": {"type": "string", "enum": sorted(seo.INTENTS)},
                       "priority": {"type": "string", "enum": ["high", "medium", "low"]}, "rationale": {"type": "string"},
                       "volume": {"type": ["integer", "null"]}, "competition": {"type": "string"}, "evidence_quote": {"type": "string"}},
        "required": ["keyword", "intent", "priority", "rationale", "volume", "competition", "evidence_quote"]}}},
    "required": ["summary", "items"],
}
BRIEF_SCHEMA = {
    "type": "object",
    "properties": {"title_options": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
                   "search_intent": {"type": "string"},
                   "outline": {"type": "array", "maxItems": 12, "items": {"type": "object", "properties": {"heading": {"type": "string"}, "points": {"type": "array", "items": {"type": "string"}}},
                                                                            "required": ["heading", "points"]}},
                   "faq": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                   "internal_links": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
                   "avoid_claims": {"type": "array", "maxItems": 8, "items": {"type": "string"}}},
    "required": ["title_options", "search_intent", "outline", "faq", "internal_links", "avoid_claims"],
}


class KeywordsOut(BaseModel):
    summary: str = Field(default="", max_length=2000)
    items: list[dict] = Field(default_factory=list, max_length=25)


class BriefOut(BaseModel):
    title_options: list[str] = Field(default_factory=list, max_length=5)
    search_intent: str = ""
    outline: list[dict] = Field(default_factory=list, max_length=12)
    faq: list[str] = Field(default_factory=list, max_length=8)
    internal_links: list[str] = Field(default_factory=list, max_length=8)
    avoid_claims: list[str] = Field(default_factory=list, max_length=8)


def _store(ctx: ExecutionContext, kind: str, title: str, summary: str, data: dict, verified: int = 0, unverified: int = 0) -> str:
    with ctx.session_factory() as s:
        row = MarketingArtifact(task_id=ctx.task.id, kind=kind, title=title[:200], summary=summary, data=data,
                                verified_count=verified, unverified_count=unverified, created_by=ctx.task.role)
        s.add(row)
        s.commit()
        return row.id


async def _ask(ctx: ExecutionContext, system: str, prompt: str, schema: dict, model_cls, max_tokens: int):
    parsed, error = None, None
    for _ in range(2):
        res = await ctx.generate(system, prompt + (f"\n\nJawaban sebelumnya ditolak: {error}" if error else ""), max_tokens=max_tokens, json_schema=schema)
        try:
            if res.truncated:
                raise ValueError("jawaban terpotong")
            parsed = model_cls.model_validate(extract_json(res.text))
            break
        except (ValidationError, ValueError) as e:
            error = str(e)[:300]
    if parsed is None:
        raise ExecutorError("invalid_seo_output", f"Keluaran tidak valid: {error}")
    return parsed


class SeoSpecialistExecutor:
    """seo_audit (deterministik, tanpa model), keyword_research, content_brief (model hanya mengusulkan; diperiksa terhadap materi)."""

    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        access.require("seo_specialist", "seo.write")
        action = ctx.task.action_type
        p = _params(ctx)
        if action == "seo_audit":
            return await self._audit(ctx, p)
        if action not in {"keyword_research", "content_brief"}:
            raise ExecutorError("unsupported_action", "SEO Specialist hanya mengerjakan seo_audit, keyword_research, content_brief", retryable=False)
        topic, material = (p.get("topic") or ctx.task.title).strip(), (p.get("material") or "").strip()
        if len(material) > MAX_MATERIAL:
            raise ExecutorError("invalid_material", f"Materi maks. {MAX_MATERIAL} karakter", retryable=False)
        if p.get("site_id"):  # fakta situs diambil dari kode sumbernya sendiri (bukan karangan model)
            site, bundle = self._site(ctx, p["site_id"])
            topic = (p.get("topic") or f"Situs {site.name}").strip()
            material = (sites.site_summary(bundle) + "\n" + material).strip()
        if action == "keyword_research" and not material:
            raise ExecutorError("invalid_material", "Materi riset kata kunci wajib diisi (data/pengetahuan yang Anda miliki)", retryable=False)
        if _EMAIL_IN_TEXT.search(material):
            raise ExecutorError("pii_in_material", "Materi tidak boleh memuat alamat email/data kontak pribadi", retryable=False)
        try:
            assert_clean(topic=topic, material=material)
        except PolicyError as e:
            raise ExecutorError("sensitive_data", e.message, retryable=False) from e
        with ctx.session_factory() as s:
            brief = _brief(s, p.get("product_id"), p.get("version_id"))
        brief_text = ""
        if brief is not None:
            brief_text = "\n".join([brief["product"]["name"], brief["product"].get("description") or ""] + [c["text"] for c in brief["claims"]])
        base = [f"TOPIK: {topic}", f"MATERI SUMBER (satu-satunya bahan fakta dan angka):\n{material or '(tidak ada)'}",
                f"INFORMASI PRODUK RESMI:\n{brief_text}" if brief_text else "INFORMASI PRODUK: (tidak ada)"]
        system = ("Kamu adalah SEO Specialist untuk Roihan Software House. Kamu tidak punya akses internet dan tidak boleh mengarang volume pencarian, "
                  "tingkat persaingan, atau klaim produk. Jangan menjanjikan atau menjamin peringkat atau pendapatan.")
        if action == "keyword_research":
            prompt = "\n\n".join(base + ["Usulkan kata kunci relevan untuk layanan software development, kelompokkan menurut niat pencarian. Isi volume dan "
                                         "competition HANYA bila angkanya tertulis di materi (salin kutipan PERSIS ke evidence_quote yang memuat kata kunci itu); "
                                         "jika tidak, volume=null, competition kosong, evidence_quote kosong. Balas HANYA JSON."])
            out = await _ask(ctx, system, prompt, KEYWORD_SCHEMA, KeywordsOut, 1800)
            items = seo.ground_keywords(out.items, material)
            if not items:
                raise ExecutorError("no_keywords", "Tidak ada kata kunci valid pada keluaran model")
            with_data = sum(1 for i in items if i["data_available"])
            flagged = sum(1 for i in items if i["flagged_claims"])
            campaign_id = p.get("campaign_id")
            text = f"Riset kata kunci '{topic}': {len(items)} kata kunci, {with_data} dengan data volume/persaingan dari materi, {len(items) - with_data} tanpa data (tidak diisi)."
            aid = _store(ctx, "keywords", f"Kata kunci: {topic}", out.summary, {"items": items, "flagged_items": flagged, "campaign_id": campaign_id}, with_data, len(items) - with_data)
            if campaign_id:
                with ctx.session_factory() as s:
                    for item in items:
                        keyword = " ".join(item["keyword"].split())
                        exists = s.query(SeoKeyword.id).filter(SeoKeyword.campaign_id == campaign_id, SeoKeyword.keyword == keyword).first()
                        if exists:
                            continue
                        s.add(SeoKeyword(campaign_id=campaign_id, keyword=keyword, intent=item["intent"], source="ai",
                                         rationale=item.get("rationale", ""), volume=item.get("volume"),
                                         competition=item.get("competition") or None, evidence_quote=item.get("evidence_quote", ""),
                                         approval_status="pending"))
                    s.add(SeoCampaignEvent(campaign_id=campaign_id, kind="keyword_suggestions_generated", actor="seo_specialist",
                                           details={"artifact_id": aid, "suggestion_count": len(items)}))
                    s.commit()
            return ExecutorOutcome(output=text, verified=True, verification={"method": "keyword_data_grounding", "passed": True, "with_data": with_data, "without_data": len(items) - with_data},
                                   result={"output": text, "artifact_id": aid})
        prompt = "\n\n".join(base + [f"Susun content brief untuk topik/kata kunci '{p.get('keyword') or topic}': opsi judul, niat pencarian, kerangka bagian, FAQ, saran tautan internal, "
                                     "dan klaim yang harus dihindari. Hanya sebut fitur produk yang ada pada INFORMASI PRODUK RESMI. Balas HANYA JSON."])
        out = await _ask(ctx, system, prompt, BRIEF_SCHEMA, BriefOut, 1800)
        all_text = " ".join(out.title_options + [out.search_intent] + [str(o.get("heading", "")) + " " + " ".join(map(str, o.get("points", []))) for o in out.outline] + out.faq)
        flagged = seo.lint_seo_claims(all_text)
        claims = check_claims(all_text, brief) if brief is not None else None
        if flagged or (claims is not None and not claims["ok"]):
            raise ExecutorError("claims_blocked", f"Brief memuat klaim terlarang: jaminan peringkat={flagged}; klaim produk={[f.get('message') for f in (claims or {}).get('findings', [])][:3]}", retryable=False)
        text = f"Content brief '{topic}': {len(out.outline)} bagian, {len(out.faq)} FAQ."
        aid = _store(ctx, "brief", f"Brief: {topic}", out.search_intent, {**out.model_dump(), "claims_check": claims, "campaign_id": p.get("campaign_id")}, 1, 0)
        return ExecutorOutcome(output=text, verified=True, verification={"method": "claim_lint", "passed": True}, result={"output": text, "artifact_id": aid})

    def _site(self, ctx: ExecutionContext, site_id: str):
        with ctx.session_factory() as s:
            site = s.get(Site, site_id)
            if site is None:
                raise ExecutorError("site_not_found", "Situs tidak ditemukan", retryable=False)
            s.expunge(site)
        return site, sites.collect_pages(sites.site_root(ctx.storage, site), site.url)

    async def _audit(self, ctx: ExecutionContext, p: dict) -> ExecutorOutcome:
        if p.get("site_id"):
            site, bundle = self._site(ctx, p["site_id"])
            report = sites.audit_site(site.url, bundle)
            report["site_id"] = site.id
            if p.get("campaign_id"):
                report["campaign_id"] = p["campaign_id"]
            c = report["counts"]
            text = (f"Audit SEO situs {site.name} ({len(report['pages'])} halaman): {c['critical']} kritis, {c['warning']} peringatan, "
                    f"{c['info']} info. Tidak diperiksa: {', '.join(report['not_checked'])}.")
            aid = _store(ctx, "audit", f"Audit situs: {site.name}", text, report, len(report["findings"]), 0)
            recommendations = 0
            if p.get("campaign_id"):
                with ctx.session_factory() as s:
                    order = {"critical": 0, "warning": 1, "info": 2}
                    findings = sorted(report["findings"], key=lambda f: (order.get(f.get("severity"), 3), f.get("id", "")))
                    for index, finding in enumerate(findings, start=1):
                        s.add(SeoRecommendation(campaign_id=p["campaign_id"], artifact_id=aid, finding_id=finding["id"],
                            category=finding["id"], title=finding["message"][:500], severity=finding["severity"],
                            evidence={"page": finding.get("page"), "detail": finding.get("evidence"), "observed_by": "deterministic_site_audit"},
                            recommendation=finding.get("recommendation", ""), impact_basis="unknown: no connected performance data",
                            confidence="observed", effort="unknown", risk="unknown", dependencies=[],
                            acceptance_criteria=["Address the documented finding without degrading content accuracy or usability",
                                                 "Re-run this SEO audit and review the resulting evidence"],
                            verification_method="Re-run the deterministic site audit and compare the finding evidence", priority_order=index))
                        recommendations += 1
                    s.add(SeoCampaignEvent(campaign_id=p["campaign_id"], kind="audit_completed", actor="seo_specialist",
                                           details={"artifact_id": aid, "counts": c, "page_count": len(report["pages"]),
                                                    "recommendations": recommendations}))
                    s.commit()
            return ExecutorOutcome(output=text, verified=True, verification={"method": "deterministic_site_audit", "passed": True, **c},
                                   result={"output": text, "artifact_id": aid})
        if p.get("campaign_id"):
            return await self._audit_campaign_website(ctx, p["campaign_id"])
        html = (p.get("html") or "")
        if not html.strip() or len(html) > seo.MAX_HTML:
            raise ExecutorError("invalid_html", f"HTML halaman wajib diisi (maks. {seo.MAX_HTML} karakter)", retryable=False)
        report = seo.audit_html(p.get("url") or "", html, p.get("robots_txt") or "", p.get("sitemap_xml") or "")
        c = report["counts"]
        text = f"Audit SEO {report['url'] or '(tanpa URL)'}: {c['critical']} kritis, {c['warning']} peringatan, {c['info']} info. Tidak diperiksa: {', '.join(report['not_checked'])}."
        aid = _store(ctx, "audit", f"Audit: {report['url'] or 'halaman'}", text, report, len(report["findings"]), 0)
        return ExecutorOutcome(output=text, verified=True, verification={"method": "deterministic_html_audit", "passed": True, **c}, result={"output": text, "artifact_id": aid})

    async def _audit_campaign_website(self, ctx: ExecutionContext, campaign_id: str) -> ExecutorOutcome:
        if ctx.web is None:
            raise ExecutorError("web_unavailable", "Layanan akses web tidak tersedia untuk audit situs", retryable=False)
        with ctx.session_factory() as s:
            from app.db.models import SeoCampaign
            campaign = s.get(SeoCampaign, campaign_id)
            if campaign is None:
                raise ExecutorError("campaign_not_found", "Kampanye SEO tidak ditemukan", retryable=False)
            root, name = campaign.website_url, campaign.name
            allowed_hosts = {str(host).lower().rstrip(".") for host in (campaign.allowed_domains or [])}
        root_host = (urlsplit(root).hostname or "").lower().rstrip(".")
        if root_host not in allowed_hosts:
            raise ExecutorError("campaign_domain_invalid", "Domain URL kampanye tidak cocok dengan allowlist", retryable=False)

        def canonical(raw: str) -> str | None:
            try:
                parts = urlsplit(urljoin(root, raw))
                host = (parts.hostname or "").lower().rstrip(".")
                if parts.scheme not in {"http", "https"} or host not in allowed_hosts or parts.username or parts.password or parts.port not in {None, 80, 443}:
                    return None
                path = parts.path or "/"
                if len(path) > 1500:
                    return None
                return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
            except ValueError:
                return None

        first = canonical(root)
        if not first:
            raise ExecutorError("campaign_url_invalid", "URL kampanye tidak valid", retryable=False)
        queue, seen, pages, findings, failures = [(first, 0)], set(), [], [], []
        total_bytes = 0
        while queue and len(pages) < 10 and total_bytes < 2_000_000:
            url, depth = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                fetched = await ctx.web.fetch(url, task_id=ctx.task.id, max_bytes=200_000, max_chars=3000,
                                              allowed_hosts=allowed_hosts)
            except WebError as exc:
                failures.append({"url": url, "reason": exc.code})
                if exc.code in {"disabled", "quota"} and not pages:
                    raise ExecutorError("web_" + exc.code, exc.message, retryable=False)
                continue
            final_url = canonical(fetched.get("url", ""))
            if not final_url:
                failures.append({"url": url, "reason": "redirect_outside_allowlist"})
                continue
            total_bytes += int(fetched.get("bytes") or 0)
            metadata = fetched.get("seo") or {}
            page_report = seo.audit_extracted_page(final_url, fetched.get("title", ""), fetched.get("description", ""),
                                                   fetched.get("links") or [], metadata)
            pages.append({"url": final_url, "status": fetched.get("status"), "bytes": fetched.get("bytes"),
                          "title": fetched.get("title", ""), "description": fetched.get("description", ""),
                          "metadata": metadata, "findings": page_report["findings"], "counts": page_report["counts"]})
            findings.extend(page_report["findings"])
            if queue:
                await asyncio.sleep(0.25)
            if depth < 2:
                for link in fetched.get("links") or []:
                    target = canonical(link)
                    if target and target not in seen and len(queue) < 100:
                        queue.append((target, depth + 1))
        if not pages:
            raise ExecutorError("website_unavailable", "Tidak ada halaman kampanye yang dapat diaudit; periksa akses web, robots.txt, dan URL publik", retryable=False)
        counts = {sev: sum(1 for f in findings if f.get("severity") == sev) for sev in ("critical", "warning", "info")}
        report = {"campaign_id": campaign_id, "website_url": first, "pages": pages, "findings": findings, "counts": counts,
                  "crawl": {"max_pages": 10, "max_depth": 2, "bytes_fetched": total_bytes, "failed_pages": failures},
                  "not_checked": ["Broken-link destination status was not fetched", "robots.txt and sitemap discovery are not audited",
                                  "Google indexation and Search Console metrics unavailable", "Core Web Vitals and JavaScript rendering unavailable",
                                  "Thin content is not inferred from bounded text snapshots"]}
        text = f"Audit SEO read-only {first} ({len(pages)} halaman): {counts['critical']} kritis, {counts['warning']} peringatan, {counts['info']} info. Halaman gagal: {len(failures)}."
        aid = _store(ctx, "audit", f"Audit SEO: {name}", text, report, len(findings), 0)
        order = {"critical": 0, "warning": 1, "info": 2}
        with ctx.session_factory() as s:
            for index, finding in enumerate(sorted(findings, key=lambda f: (order.get(f.get("severity"), 3), f.get("id", ""))), start=1):
                s.add(SeoRecommendation(campaign_id=campaign_id, artifact_id=aid, finding_id=finding["id"], category=finding["id"],
                    title=finding["message"][:500], severity=finding["severity"],
                    evidence={"page": finding.get("page"), "detail": finding.get("evidence"), "observed_by": "safe_external_crawler"},
                    recommendation=finding.get("recommendation", ""), impact_basis="unknown: no connected performance data",
                    confidence="observed", effort="unknown", risk="unknown", dependencies=[],
                    acceptance_criteria=["Address documented evidence without degrading accuracy or usability", "Re-run the read-only SEO audit"],
                    verification_method="Re-run the deterministic audit and compare evidence", priority_order=index))
            s.add(SeoCampaignEvent(campaign_id=campaign_id, kind="audit_completed", actor="seo_specialist",
                                   details={"artifact_id": aid, "counts": counts, "page_count": len(pages), "failed_pages": len(failures)}))
            s.commit()
        return ExecutorOutcome(output=text, verified=True, verification={"method": "safe_external_deterministic_audit", "passed": True, **counts},
                               result={"output": text, "artifact_id": aid})


class MarketingAnalyticsExecutor:
    """Laporan KPI deterministik dari data yang tercatat (tanpa model): nilai tidak diketahui tetap None, ROI hanya bila datanya lengkap."""

    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        access.require("marketing_analytics", "analytics.read")
        if ctx.task.action_type != "marketing_analysis":
            raise ExecutorError("unsupported_action", "Marketing Analytics hanya mengerjakan marketing_analysis", retryable=False)
        with ctx.session_factory() as s:
            k = seo.kpis(s)
        observations = []
        if k["organic"]["impressions"] is None:
            observations.append("Data impresi pencarian belum dicatat: kinerja organik belum dapat dinilai.")
        elif k["organic"]["ctr"] is not None:
            observations.append(f"CTR organik tercatat {k['organic']['ctr']:.2%} dari {int(k['organic']['impressions'])} impresi (data periode yang dicatat).")
        if k["funnel"]["lead_to_meeting_rate"] is None:
            observations.append("Rasio lead ke pertemuan belum diketahui (belum ada lead).")
        if k["money"]["roi"] is None:
            observations.append("ROI belum dihitung karena biaya dan pendapatan kampanye belum lengkap.")
        observations.append("Pengamatan ini deskriptif; bukan bukti sebab-akibat dan bukan jaminan hasil.")
        text = f"Laporan analitik pemasaran: {k['leads']['total']} lead, {sum(1 for v in _flat(k) if v is None)} indikator belum diketahui."
        aid = _store(ctx, "analysis", "Laporan analitik pemasaran", text, {"kpis": k, "observations": observations}, 1, 0)
        return ExecutorOutcome(output=text, verified=True, verification={"method": "deterministic_kpi_report", "passed": True}, result={"output": text, "artifact_id": aid})


def _flat(d):
    for v in d.values():
        if isinstance(v, dict):
            yield from _flat(v)
        elif not isinstance(v, (list, str)):
            yield v
