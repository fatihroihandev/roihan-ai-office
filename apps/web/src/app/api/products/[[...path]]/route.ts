import { makeProxyHandlers } from "@/lib/forward";

const h = makeProxyHandlers("api/products", 60_000);
export const GET = h.GET;
export const POST = h.POST;
export const PATCH = h.PATCH;
export const DELETE = h.DELETE;
