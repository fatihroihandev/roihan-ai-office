"""Pengambil halaman web yang aman: SSRF-guard, redirect manual yang diperiksa, batas ukuran/waktu, patuh robots.txt, dan ekstraksi teks."""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx

from app.web.guard import Resolver, WebError, check_url, default_resolver

USER_AGENT = "RoihanSoftwareHouseBot/1.0 (agen riset lokal; patuh robots.txt)"
MAX_REDIRECTS = 4
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "application/json", "text/xml", "application/xml")
_ROBOTS: dict[str, tuple[float, robotparser.RobotFileParser | None]] = {}
ROBOTS_TTL_S = 3600.0


class _Extract(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title, self._in_title, self._skip = "", False, 0
        self.meta: dict[str, str] = {}
        self.parts: list[str] = []
        self.links: list[str] = []
        self.lang: str | None = None
        self.canonical: str | None = None
        self.h1 = self.h2 = 0
        self.images = self.images_no_alt = 0
        self.jsonld: list[str] = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang") or None
        elif tag in {"script", "style", "noscript", "svg", "template"}:
            self._skip += 1
            if tag == "script" and a.get("type", "").lower() == "application/ld+json":
                self._in_jsonld = True
                self.jsonld.append("")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            if name in {"description", "robots", "viewport"} or prop.startswith("og:"):
                self.meta[prop if prop.startswith("og:") else name] = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").lower():
            self.canonical = a.get("href") or None
        elif tag == "h1":
            self.h1 += 1
        elif tag == "h2":
            self.h2 += 1
        elif tag == "img":
            self.images += 1
            if not a.get("alt", "").strip():
                self.images_no_alt += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._skip = max(0, self._skip - 1)
            if tag == "script":
                self._in_jsonld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_jsonld and self.jsonld:
            self.jsonld[-1] += data
        elif self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.parts.append(data)


def extract(html: str, base_url: str = "", max_chars: int = 6000) -> dict:
    p = _Extract()
    p.feed(html[:600_000])
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(p.parts))
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)  # buang karakter kontrol
    links = []
    for href in p.links:
        full = urljoin(base_url, href) if base_url else href
        if full.startswith(("http://", "https://")) and full not in links:
            links.append(full)
    return {"title": re.sub(r"\s+", " ", p.title).strip()[:200], "description": p.meta.get("description", "")[:300],
            "text": text[:max_chars], "truncated": len(text) > max_chars, "links": links[:20],
            "seo": {"robots": p.meta.get("robots", "")[:200], "canonical": p.canonical, "lang": p.lang,
                    "h1": p.h1, "h2": p.h2, "images": p.images, "images_no_alt": p.images_no_alt,
                    "viewport": bool(p.meta.get("viewport")),
                    "og_tags": [key for key in p.meta if key.startswith("og:")],
                    "jsonld_validity": [is_json for blob in p.jsonld for is_json in [_valid_json(blob)]]}}


def _valid_json(blob: str) -> bool:
    import json
    try:
        json.loads(blob)
        return True
    except (TypeError, ValueError):
        return False


async def _get(client: httpx.AsyncClient, url: str, resolver: Resolver, max_bytes: int,
               allowed_hosts: set[str] | None = None) -> tuple[httpx.Response, bytes, str]:
    """GET dengan redirect manual (tiap lompatan diperiksa), membaca tubuh sampai `max_bytes`."""
    def validate_domain(raw: str) -> None:
        if allowed_hosts is None:
            return
        host = (urlsplit(raw).hostname or "").lower().rstrip(".")
        if host not in allowed_hosts:
            raise WebError("domain_not_allowed", "Redirect berada di luar domain yang diizinkan")

    validate_domain(url)
    current = check_url(url, resolver)
    for _ in range(MAX_REDIRECTS + 1):
        async with client.stream("GET", current, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"}) as r:
            if r.status_code in {301, 302, 303, 307, 308} and r.headers.get("location"):
                redirected = urljoin(current, r.headers["location"])
                validate_domain(redirected)
                current = check_url(redirected, resolver)
                continue
            ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if r.status_code >= 400:
                raise WebError("http_error", f"Situs membalas status {r.status_code}")
            if ctype and not ctype.startswith(TEXT_TYPES):
                raise WebError("unsupported_type", f"Jenis konten tidak didukung: {ctype}")
            body = bytearray()
            async for chunk in r.aiter_bytes():
                body += chunk
                if len(body) >= max_bytes:
                    break
            return r, bytes(body[:max_bytes]), current
    raise WebError("too_many_redirects", "Terlalu banyak pengalihan (redirect)")


async def _robots_allows(client: httpx.AsyncClient, url: str, resolver: Resolver,
                         allowed_hosts: set[str] | None = None) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    cached = _ROBOTS.get(origin)
    if cached is None or time.monotonic() - cached[0] > ROBOTS_TTL_S:
        rp: robotparser.RobotFileParser | None = None
        try:
            r, body, _ = await _get(client, origin + "/robots.txt", resolver, 100_000, allowed_hosts)
            rp = robotparser.RobotFileParser()
            rp.parse(body.decode("utf-8", "replace").splitlines())
        except WebError:
            rp = None   # tidak ada robots.txt (atau tidak terbaca): tidak melarang
        _ROBOTS[origin] = cached = (time.monotonic(), rp)
    rp = cached[1]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


async def fetch_page(url: str, *, max_bytes: int = 500_000, max_chars: int = 6000, timeout_s: float = 15.0,
                     allowed_hosts: set[str] | None = None, resolver: Resolver = default_resolver,
                     transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """Ambil satu halaman publik. Lempar WebError untuk semua kegagalan yang dapat diduga."""
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=False, transport=transport) as client:
            if not await _robots_allows(client, check_url(url, resolver), resolver, allowed_hosts):
                raise WebError("robots_disallow", "robots.txt situs melarang pengambilan halaman ini")
            r, body, final = await _get(client, url, resolver, max_bytes, allowed_hosts)
    except WebError:
        raise
    except httpx.TimeoutException as e:
        raise WebError("timeout", "Situs tidak merespons dalam batas waktu") from e
    except httpx.HTTPError as e:
        raise WebError("network_error", f"Gagal menghubungi situs: {type(e).__name__}") from e
    enc = r.encoding or "utf-8"
    page = extract(body.decode(enc, "replace"), final, max_chars)
    return {"url": final, "status": r.status_code, "bytes": len(body), **page}
