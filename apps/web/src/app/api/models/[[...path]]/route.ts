import { makeProxyHandlers } from "@/lib/forward";

const h = makeProxyHandlers("api/models", 120_000);
export const GET = h.GET;
export const POST = h.POST;
