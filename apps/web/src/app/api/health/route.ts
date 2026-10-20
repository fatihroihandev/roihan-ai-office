import { NextResponse } from "next/server";
import { ensureRootEnv } from "@/lib/server-env";

// Proxy sisi server: token lokal tidak pernah dikirim ke browser.
export async function GET() {
  ensureRootEnv();
  const base = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const token = process.env.APP_LOCAL_TOKEN ?? "";
  try {
    const res = await fetch(`${base}/api/health/details`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return NextResponse.json({ error: "upstream" }, { status: 502 });
    return NextResponse.json(await res.json());
  } catch {
    return NextResponse.json({ error: "unreachable" }, { status: 502 });
  }
}
