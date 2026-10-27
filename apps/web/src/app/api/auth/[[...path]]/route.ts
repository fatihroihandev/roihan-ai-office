import { makeProxyHandlers } from "@/lib/forward";

// Proxy endpoint autentikasi pemilik tunggal (Single-Owner Auth - Addendum v2.1)
const h = makeProxyHandlers("api/auth", 30_000);

export const GET = h.GET;
export const POST = h.POST;
export const PATCH = h.PATCH;
export const DELETE = h.DELETE;
