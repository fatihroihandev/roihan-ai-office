"""Pemindaian statis deterministik untuk review keamanan dan kualitas (tanpa model, tanpa menjalankan kode)."""
import ast
import re

SECRET_ASSIGN = re.compile(r"""(?i)\b(api[_-]?key|secret|token|passwd|password|private[_-]?key)\b\s*[:=]\s*['"][^'"\s]{8,}['"]""")
SECRET_FORMATS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "Kunci API bergaya OpenAI"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "Access key AWS"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "Private key"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "Token GitHub"),
]
DANGEROUS_CALLS = {
    "eval": ("high", "security", "Pemakaian eval() mengeksekusi string sebagai kode", "Hindari eval; gunakan ast.literal_eval atau parser khusus"),
    "exec": ("high", "security", "Pemakaian exec() mengeksekusi string sebagai kode", "Hindari exec"),
    "compile": ("medium", "security", "compile() membangun kode dari string", "Pastikan input tepercaya"),
    "__import__": ("medium", "security", "Impor dinamis lewat __import__", "Gunakan import biasa"),
}
DANGEROUS_ATTRS = {
    ("os", "system"): ("high", "security", "os.system menjalankan perintah shell", "Gunakan subprocess tanpa shell"),
    ("os", "popen"): ("high", "security", "os.popen menjalankan perintah shell", "Gunakan subprocess tanpa shell"),
    ("pickle", "loads"): ("high", "security", "pickle.loads dapat mengeksekusi kode dari data tak tepercaya", "Gunakan json"),
    ("pickle", "load"): ("high", "security", "pickle.load dapat mengeksekusi kode dari data tak tepercaya", "Gunakan json"),
    ("marshal", "loads"): ("high", "security", "marshal.loads tidak aman untuk data tak tepercaya", "Gunakan json"),
}
NETWORK_MODULES = {"socket", "requests", "urllib", "http", "ftplib", "smtplib", "telnetlib"}


def _f(sev, cat, file, line, desc, sug=""):
    return {"severity": sev, "category": cat, "file": file, "line": line, "description": desc, "suggestion": sug, "source": "static"}


def scan_python(path: str, text: str) -> list[dict]:
    out: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        if SECRET_ASSIGN.search(line):
            out.append(_f("high", "security", path, i, "Kredensial tampaknya ditulis langsung di kode", "Baca dari environment atau secret store"))
        for rx, label in SECRET_FORMATS:
            if rx.search(line):
                out.append(_f("critical", "security", path, i, f"{label} ditemukan di kode", "Hapus dan putar (rotate) kredensial tersebut"))
        if re.search(r"#\s*(TODO|FIXME|XXX)\b", line):
            out.append(_f("low", "maintainability", path, i, "Penanda TODO/FIXME masih tersisa"))
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return out + [_f("high", "correctness", path, e.lineno, f"Sintaks tidak valid: {e.msg}")]

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            out.append(_f("low", "maintainability", path, node.lineno, "except tanpa tipe menelan semua galat", "Tangkap tipe galat yang spesifik"))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                if n.split(".")[0] in NETWORK_MODULES:
                    out.append(_f("medium", "security", path, node.lineno, f"Kode mengimpor modul jaringan '{n}'", "Pastikan akses jaringan memang dibutuhkan dan aman"))
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in DANGEROUS_CALLS:
                sev, cat, desc, sug = DANGEROUS_CALLS[fn.id]
                out.append(_f(sev, cat, path, node.lineno, desc, sug))
            elif isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                key = (fn.value.id, fn.attr)
                if key in DANGEROUS_ATTRS:
                    sev, cat, desc, sug = DANGEROUS_ATTRS[key]
                    out.append(_f(sev, cat, path, node.lineno, desc, sug))
                if fn.value.id == "subprocess":
                    shell = any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords)
                    out.append(_f("high" if shell else "medium", "security", path, node.lineno,
                                  "subprocess dengan shell=True rentan injeksi perintah" if shell else "Kode menjalankan proses eksternal (subprocess)",
                                  "Hindari shell=True; beri argumen sebagai daftar"))
                if key == ("yaml", "load") and not any(k.arg == "Loader" for k in node.keywords):
                    out.append(_f("high", "security", path, node.lineno, "yaml.load tanpa Loader aman", "Gunakan yaml.safe_load"))
    return out


def scan_files(files: dict[str, str]) -> list[dict]:
    findings: list[dict] = []
    for path, text in sorted(files.items()):
        if path.endswith(".py"):
            findings += scan_python(path, text)
        else:
            for i, line in enumerate(text.splitlines(), 1):
                for rx, label in SECRET_FORMATS:
                    if rx.search(line):
                        findings.append(_f("critical", "security", path, i, f"{label} ditemukan di file", "Hapus dan putar (rotate) kredensial tersebut"))
                if SECRET_ASSIGN.search(line):
                    findings.append(_f("high", "security", path, i, "Kredensial tampaknya ditulis langsung di file", "Pindahkan ke environment"))
    return findings
