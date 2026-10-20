import { makeProxyHandlers } from "@/lib/forward";

// Model lokal di CPU bisa lambat: beri waktu lebih lama dari batas backend (OLLAMA_TIMEOUT_S = 600 detik).
const h = makeProxyHandlers("api/ai", 630_000);
export const POST = h.POST;
