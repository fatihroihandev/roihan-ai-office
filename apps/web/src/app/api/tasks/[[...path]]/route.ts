import { makeProxyHandlers } from "@/lib/forward";

const h = makeProxyHandlers("api/tasks", 60_000);
export const GET = h.GET;
export const POST = h.POST;
