// Matematika grafik murni (tanpa DOM) agar dapat diuji: skala, tick, format ringkas, dan konversi corong.

/** Batas atas "bulat" untuk sumbu: 0 selalu menjadi dasar. */
export function niceMax(value: number): number {
  if (!(value > 0)) return 1;
  const pow = 10 ** Math.floor(Math.log10(value));
  const n = value / pow;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * pow;
}

/** Tick sumbu y dari 0 sampai batas bulat; jumlah tick kecil agar tenang. */
export function ticks(max: number, count = 4): number[] {
  const top = niceMax(max);
  const step = top / count;
  return Array.from({ length: count + 1 }, (_, i) => Math.round(step * i * 100) / 100);
}

/** Tick bilangan bulat untuk hitungan (task, panggilan): langkah 1/2/5/10... dengan paling banyak 5 interval; dasar selalu 0. */
export function intTicks(max: number): number[] {
  const need = Math.max(1, Math.ceil(max));
  for (let p = 1; p <= 1_000_000; p *= 10) {
    for (const m of [1, 2, 5]) {
      const step = m * p; // langkah terkecil yang menghasilkan paling banyak 5 interval
      if (need / step <= 5) return Array.from({ length: Math.ceil(need / step) + 1 }, (_, i) => i * step);
    }
  }
  return [0, need];
}

/** Waktu UTC dari string ISO dengan atau tanpa zona (`Z`, `+00:00`, atau tanpa akhiran = UTC). */
export function parseUtc(iso: string): number {
  return new Date(/(Z|[+-]\d{2}:\d{2})$/.test(iso) ? iso : `${iso}Z`).getTime();
}

/** 0 / 1K / 2,5K / 1,2JT: ringkas mulai 1.000. */
export function compact(n: number, locale = "id"): string {
  if (n < 1000) return String(Math.round(n * 10) / 10).replace(".", locale === "id" ? "," : ".");
  const [v, s] = n >= 1_000_000 ? [n / 1_000_000, locale === "id" ? "JT" : "M"] : [n / 1000, "K"];
  return `${(Math.round(v * 10) / 10).toString().replace(".", locale === "id" ? "," : ".")}${s}`;
}

/** Persentase dengan satu desimal bila perlu; null berarti belum diketahui. */
export function pct(v: number | null, digits = 0): string | null {
  return v === null ? null : `${(v * 100).toFixed(digits)}%`;
}

/** Konversi antar-tahap corong: reached[i] / reached[i-1]. Tahap pertama tidak punya konversi (null). */
export function stepRates(reached: number[]): (number | null)[] {
  return reached.map((r, i) => (i === 0 || reached[i - 1] === 0 ? null : r / reached[i - 1]));
}

/** Potong segmen bertumpuk menjadi [mulai, akhir] kumulatif dengan celah tetap di antaranya (dihitung pemanggil). */
export function stack(values: number[]): { from: number; to: number }[] {
  let acc = 0;
  return values.map((v) => {
    const seg = { from: acc, to: acc + v };
    acc += v;
    return seg;
  });
}

/** "5 mnt lalu", "3 j lalu", "2 h lalu" (id) / "5m ago" (en). */
export function ago(iso: string, now: number, lang: "id" | "en" = "id"): string {
  const sec = Math.max(0, Math.round((now - parseUtc(iso)) / 1000));
  const [n, u] = sec < 60 ? [sec, lang === "id" ? "dtk" : "s"] : sec < 3600 ? [Math.floor(sec / 60), lang === "id" ? "mnt" : "m"]
    : sec < 86400 ? [Math.floor(sec / 3600), lang === "id" ? "j" : "h"] : [Math.floor(sec / 86400), lang === "id" ? "h" : "d"];
  return lang === "id" ? `${n} ${u} lalu` : `${n}${u} ago`;
}
