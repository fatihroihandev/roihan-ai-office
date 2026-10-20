import { makeProxyHandlers } from "@/lib/forward";

const h = makeProxyHandlers("api/events", 30_000);
export const GET = h.GET;
export const POST = h.POST;
