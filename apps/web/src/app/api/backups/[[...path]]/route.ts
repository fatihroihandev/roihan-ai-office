import { makeProxyHandlers } from "@/lib/forward";

// Proxy endpoint manajemen backup
const h = makeProxyHandlers("api/backups", 60_000);

export const GET = h.GET;
export const POST = h.POST;
