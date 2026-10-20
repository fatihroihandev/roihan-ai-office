import { NextResponse } from "next/server";
import { buildUpstreamUrl } from "@/lib/proxy";
import { ensureRootEnv } from "@/lib/server-env";

// Proxy sisi server ke backend: token lokal ditambahkan di sini dan tidak pernah dikirim ke browser.
type Ctx = { params: Promise<{ path?: string[] }> };

const PASS_HEADERS = ["content-type", "content-disposition", "content-length", "x-content-type-options"];

async function forward(request: Request, ctx: Ctx): Promise<Response> {
  ensureRootEnv();
  const { path = [] } = await ctx.params;
  const base = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
  const url = buildUpstreamUrl(base, "api/projects", path, new URL(request.url).search);
  if (!url) return NextResponse.json({ detail: "Path tidak valid" }, { status: 400 });

  const headers: Record<string, string> = { Authorization: `Bearer ${process.env.APP_LOCAL_TOKEN ?? ""}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;
  const hasBody = request.method !== "GET" && request.method !== "HEAD" && request.body !== null;

  try {
    const res = await fetch(url, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(60_000),
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);

    const out = new Headers();
    for (const h of PASS_HEADERS) {
      const v = res.headers.get(h);
      if (v) out.set(h, v);
    }
    return new Response(res.status === 204 ? null : res.body, { status: res.status, headers: out });
  } catch {
    return NextResponse.json({ detail: "API tidak dapat dihubungi" }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
