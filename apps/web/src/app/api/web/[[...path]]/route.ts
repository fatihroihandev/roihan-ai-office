import { makeProxyHandlers } from "@/lib/forward";

const h = makeProxyHandlers("api/web", 60_000);
export const GET = h.GET;
export const POST = h.POST;
export const PATCH = h.PATCH;
