import { makeProxyHandlers } from "@/lib/forward";

const h = makeProxyHandlers("api/providers", 30_000);
export const GET = h.GET;
