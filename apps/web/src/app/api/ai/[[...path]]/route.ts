import { makeProxyHandlers } from "@/lib/forward";

// Model lokal di CPU bisa lambat: beri waktu lebih lama dari batas backend (OLLAMA_TIMEOUT_S = 300 detik).
const h = makeProxyHandlers("api/ai", 330_000);
export const POST = h.POST;
