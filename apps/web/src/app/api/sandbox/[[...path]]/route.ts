import { makeProxyHandlers } from "@/lib/forward";

// Uji isolasi menjalankan beberapa proses di sandbox dan bisa memakan waktu; beri batas yang longgar.
const h = makeProxyHandlers("api/sandbox", 180_000);
export const GET = h.GET;
export const POST = h.POST;
