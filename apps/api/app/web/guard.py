"""Perlindungan SSRF untuk akses web agent: hanya http/https publik di port 80/443; tujuan privat, loopback, link-local, dan cadangan ditolak.

Alamat diperiksa setelah resolusi DNS dan pada SETIAP lompatan redirect. Celah yang diketahui: DNS rebinding antara pemeriksaan dan koneksi
(sempit untuk penggunaan lokal satu pengguna; mitigasi: batas waktu pendek dan tidak ada kredensial yang dikirim).
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Callable
from urllib.parse import urlsplit

ALLOWED_PORTS = {None, 80, 443}
Resolver = Callable[[str], list[str]]


class WebError(Exception):
    """Galat akses web yang aman ditampilkan. `code` dipakai API untuk memilih status HTTP."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def default_resolver(host: str) -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)})
    except socket.gaierror as e:
        raise WebError("dns_failed", f"Nama host tidak dapat diresolusi: {host}") from e


def _is_public(addr: str) -> bool:
    ip = ipaddress.ip_address(addr.split("%")[0])
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_global and not ip.is_multicast


def check_url(url: str, resolver: Resolver = default_resolver) -> str:
    """Kembalikan URL yang sudah dinormalisasi atau lempar WebError. Tidak melakukan permintaan jaringan selain resolusi DNS."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as e:
        raise WebError("invalid_url", "URL tidak valid") from e
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise WebError("invalid_url", "URL harus berawalan http:// atau https://")
    if parts.username or parts.password:
        raise WebError("invalid_url", "URL tidak boleh memuat kredensial")
    if port not in ALLOWED_PORTS:
        raise WebError("blocked_port", "Hanya port 80 dan 443 yang diizinkan")
    host = parts.hostname
    try:
        literal = ipaddress.ip_address(host)
        addrs = [str(literal)]
    except ValueError:
        if host.lower() in {"localhost"} or host.lower().endswith((".local", ".internal", ".localhost")):
            raise WebError("blocked_host", "Alamat lokal/internal tidak diizinkan") from None
        addrs = resolver(host)
    if not addrs or not all(_is_public(a) for a in addrs):
        raise WebError("blocked_host", "Alamat tujuan bukan alamat internet publik (jaringan lokal/privat ditolak)")
    return parts._replace(fragment="").geturl()
