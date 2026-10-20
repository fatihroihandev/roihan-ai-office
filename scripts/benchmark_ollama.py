"""Benchmark model lokal Ollama sesuai Bagian 11.1 MASTER_DEVELOPMENT.md.

Hanya memakai pustaka standar. Hasil mentah disimpan di data/benchmarks/.
Kode hasil model dijalankan sebagai subprocess dengan timeout dan filter impor;
ini BUKAN sandbox (sandbox sebenarnya: Phase 5).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "benchmarks"
FORBIDDEN = re.compile(r"\b(import\s+(os|sys|subprocess|socket|shutil|pathlib|requests)|open\s*\(|__import__|eval\s*\(|exec\s*\()")

# --- Tugas output terstruktur -------------------------------------------------
JSON_DESCRIPTIONS = [
    "Buat halaman login dengan validasi email dan password",
    "Perbaiki bug tombol checkout tidak merespons di Safari",
    "Migrasi database pelanggan dari MySQL ke PostgreSQL",
    "Tambahkan fitur ekspor laporan penjualan ke PDF",
    "Optimalkan query dashboard yang lambat lebih dari 5 detik",
    "Siapkan pipeline CI untuk menjalankan unit test otomatis",
    "Tulis dokumentasi API untuk modul pembayaran",
    "Implementasikan notifikasi email saat pesanan dikirim",
    "Ganti library autentikasi lama yang memiliki celah keamanan",
    "Rancang skema database untuk modul inventaris",
    "Buat komponen tabel dengan sorting dan pagination",
    "Tambahkan dark mode pada aplikasi web",
    "Perbaiki memory leak pada worker pengolah gambar",
    "Buat endpoint REST untuk manajemen pengguna",
    "Siapkan backup database harian otomatis",
    "Tambahkan rate limiting pada API publik",
    "Buat landing page produk baru",
    "Lakukan code review untuk modul keranjang belanja",
    "Tulis test end-to-end untuk alur pendaftaran",
    "Konfigurasi logging terstruktur untuk backend",
]
JSON_PROMPT = (
    "Ubah deskripsi tugas berikut menjadi JSON dengan tepat 4 kunci: "
    '"title" (string), "priority" ("low", "medium", atau "high"), '
    '"estimated_hours" (angka), "tags" (array string). '
    "Balas HANYA dengan JSON, tanpa teks lain.\n\nDeskripsi: {d}"
)
PRIORITIES = {"low", "medium", "high"}


def valid_json_output(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return False
    try:
        o = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False
    return (
        set(o) == {"title", "priority", "estimated_hours", "tags"}
        and isinstance(o["title"], str) and o["title"].strip() != ""
        and o["priority"] in PRIORITIES
        and isinstance(o["estimated_hours"], (int, float)) and not isinstance(o["estimated_hours"], bool)
        and isinstance(o["tags"], list) and all(isinstance(t, str) for t in o["tags"])
    )


# --- Tugas kode: (nama fungsi, deskripsi, tes) --------------------------------
CODEGEN = [
    ("is_palindrome", "menerima string s dan mengembalikan True jika palindrom, mengabaikan huruf besar/kecil dan karakter non-alfanumerik",
     "assert is_palindrome('A man, a plan, a canal: Panama') is True\nassert is_palindrome('hello') is False\nassert is_palindrome('') is True"),
    ("fizzbuzz", "menerima n dan mengembalikan list string untuk 1..n (Fizz untuk kelipatan 3, Buzz untuk 5, FizzBuzz untuk keduanya, selain itu angka sebagai string)",
     "assert fizzbuzz(5) == ['1','2','Fizz','4','Buzz']\nassert fizzbuzz(15)[-1] == 'FizzBuzz'\nassert fizzbuzz(0) == []"),
    ("flatten", "menerima list bersarang dengan kedalaman berapa pun dan mengembalikan list datar",
     "assert flatten([1,[2,[3,4]],5]) == [1,2,3,4,5]\nassert flatten([]) == []\nassert flatten([[[]]]) == []"),
    ("word_count", "menerima teks dan mengembalikan dict jumlah kata, huruf kecil, dipisah spasi",
     "assert word_count('a b A') == {'a':2,'b':1}\nassert word_count('') == {}"),
    ("merge_sorted", "menerima dua list terurut naik dan mengembalikan satu list terurut naik gabungan keduanya tanpa memakai sorted()",
     "assert merge_sorted([1,3,5],[2,4]) == [1,2,3,4,5]\nassert merge_sorted([],[1]) == [1]\nassert merge_sorted([1,1],[1]) == [1,1,1]"),
    ("fibonacci", "menerima n >= 0 dan mengembalikan bilangan Fibonacci ke-n dengan fibonacci(0)=0 dan fibonacci(1)=1",
     "assert fibonacci(0) == 0\nassert fibonacci(1) == 1\nassert fibonacci(10) == 55\nassert fibonacci(30) == 832040"),
    ("roman_to_int", "mengubah bilangan Romawi (string huruf besar) menjadi integer",
     "assert roman_to_int('III') == 3\nassert roman_to_int('IV') == 4\nassert roman_to_int('MCMXCIV') == 1994"),
    ("group_anagrams", "menerima list kata dan mengembalikan list grup anagram; tiap grup diurutkan, dan daftar grup diurutkan",
     "assert group_anagrams(['eat','tea','tan','ate','nat','bat']) == [['ate','eat','tea'],['bat'],['nat','tan']]\nassert group_anagrams([]) == []"),
    ("is_valid_parentheses", "menerima string berisi ()[]{} dan mengembalikan True jika kurung seimbang dan bersarang benar",
     "assert is_valid_parentheses('()[]{}') is True\nassert is_valid_parentheses('(]') is False\nassert is_valid_parentheses('([)]') is False\nassert is_valid_parentheses('') is True"),
    ("chunk", "menerima list dan size, mengembalikan list potongan berukuran size (potongan terakhir boleh lebih pendek)",
     "assert chunk([1,2,3,4,5],2) == [[1,2],[3,4],[5]]\nassert chunk([],3) == []"),
]

# --- Tugas perbaikan bug: (nama, kode bug, tes) -------------------------------
BUGFIX = [
    ("average", "def average(nums):\n    return sum(nums) / (len(nums) + 1)\n",
     "assert average([2,4,6]) == 4\nassert average([5]) == 5"),
    ("max_of", "def max_of(lst):\n    m = 0\n    for x in lst:\n        if x > m:\n            m = x\n    return m\n",
     "assert max_of([-5,-2,-9]) == -2\nassert max_of([1,7,3]) == 7"),
    ("count_vowels", "def count_vowels(s):\n    return sum(1 for c in s if c in 'aeiou')\n",
     "assert count_vowels('AEIou') == 5\nassert count_vowels('xyz') == 0"),
    ("factorial", "def factorial(n):\n    if n == 1:\n        return 0\n    return n * factorial(n - 1)\n",
     "assert factorial(1) == 1\nassert factorial(5) == 120"),
    ("binary_search", "def binary_search(a, t):\n    lo, hi = 0, len(a)\n    while lo < hi:\n        mid = (lo + hi) // 2\n        if a[mid] == t:\n            return mid\n        if a[mid] < t:\n            lo = mid\n        else:\n            hi = mid\n    return -1\n",
     "assert binary_search([1,3,5,7,9], 9) == 4\nassert binary_search([1,3,5,7,9], 1) == 0\nassert binary_search([1,3,5], 4) == -1"),
    ("remove_duplicates", "def remove_duplicates(lst):\n    return list(set(lst))\n",
     "assert remove_duplicates([3,1,3,2,1]) == [3,1,2]"),
    ("is_even", "def is_even(n):\n    return n % 2 == 1\n",
     "assert is_even(4) is True\nassert is_even(7) is False"),
    ("clamp", "def clamp(x, lo, hi):\n    return min(lo, max(hi, x))\n",
     "assert clamp(5, 0, 10) == 5\nassert clamp(-1, 0, 10) == 0\nassert clamp(99, 0, 10) == 10"),
    ("second_largest", "def second_largest(nums):\n    s = sorted(nums)\n    return s[-2]\n",
     "assert second_largest([1,5,5,3]) == 3\nassert second_largest([9,2]) == 2"),
    ("reverse_words", "def reverse_words(s):\n    return ' '.join(s.split(' ')[::-1])[::-1]\n",
     "assert reverse_words('hello big world') == 'world big hello'"),
]


def generate(model, prompt, num_predict, num_ctx=4096):
    body = {
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.2, "num_predict": num_predict, "num_ctx": num_ctx},
    }
    req = urllib.request.Request(f"{BASE_URL}/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    d["wall_s"] = time.time() - t0
    return d


def extract_code(text):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def run_tests(code, tests):
    if FORBIDDEN.search(code):
        return False, "blocked: impor/pemanggilan berbahaya"
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "t.py"
        f.write_text(code + "\n\n" + tests + "\nprint('PASS')\n", encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-I", str(f)], cwd=tmp, capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            return False, "timeout"
    ok = p.returncode == 0 and "PASS" in p.stdout
    return ok, "" if ok else (p.stderr.strip().splitlines() or ["gagal"])[-1]


def stats(results):
    gen = [r for r in results if "eval_count" in r]
    tps = [r["eval_count"] / (r["eval_duration"] / 1e9) for r in gen if r["eval_duration"]]
    return {"avg_tok_per_s": round(sum(tps) / len(tps), 2) if tps else None}


def section(name, items, fn):
    print(f"\n== {name} ({len(items)}) ==", flush=True)
    out = []
    for i, it in enumerate(items, 1):
        r = fn(it)
        out.append(r)
        print(f"  [{i}/{len(items)}] {'OK ' if r['passed'] else 'GAGAL'} {r.get('id','')} {r.get('note','')}", flush=True)
    passed = sum(r["passed"] for r in out)
    print(f"  -> {passed}/{len(out)} = {passed / len(out) * 100:.0f}%", flush=True)
    return {"passed": passed, "total": len(out), "rate": round(passed / len(out), 3), "runs": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--runs-json", type=int, default=20)
    ap.add_argument("--skip-json", action="store_true")
    ap.add_argument("--skip-code", action="store_true")
    ap.add_argument("--skip-bugfix", action="store_true")
    a = ap.parse_args()

    report = {"model": a.model, "started_at": datetime.now(timezone.utc).isoformat(), "options": {"temperature": 0.2, "num_ctx": 4096}}
    with urllib.request.urlopen(f"{BASE_URL}/api/tags", timeout=10) as r:
        report["ollama_models"] = [m["name"] for m in json.load(r)["models"]]
    generate(a.model, "ok", 1)  # warm-up / muat model
    meta = []

    def keep(d):
        meta.append(d)
        return d

    if not a.skip_json:
        def f(d):
            g = keep(generate(a.model, JSON_PROMPT.format(d=d), 300))
            return {"id": d[:30], "passed": valid_json_output(g["response"]), "output": g["response"]}
        report["json"] = section("Output terstruktur", (JSON_DESCRIPTIONS * 2)[: a.runs_json], f)

    if not a.skip_code:
        def f(t):
            name, desc, tests = t
            g = keep(generate(a.model, f"Tulis fungsi Python `{name}` yang {desc}. Balas hanya dengan satu blok kode python, tanpa penjelasan dan tanpa kode uji.", 400))
            code = extract_code(g["response"])
            ok, note = run_tests(code, tests)
            return {"id": name, "passed": ok, "note": note, "output": g["response"]}
        report["codegen"] = section("Pembuatan kode", CODEGEN, f)

    if not a.skip_bugfix:
        def f(t):
            name, buggy, tests = t
            g = keep(generate(a.model, f"Kode Python berikut memiliki bug. Perbaiki dan balas hanya dengan satu blok kode python berisi fungsi lengkap yang sudah benar, tanpa penjelasan.\n\n```python\n{buggy}```", 400))
            code = extract_code(g["response"])
            ok, note = run_tests(code, tests)
            return {"id": name, "passed": ok, "note": note, "output": g["response"]}
        report["bugfix"] = section("Perbaikan bug", BUGFIX, f)

    report["speed"] = stats(meta)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{a.model.replace(':', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKecepatan rata-rata: {report['speed']['avg_tok_per_s']} tok/s\nHasil disimpan: {path}")


if __name__ == "__main__":
    main()
