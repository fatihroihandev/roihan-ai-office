import os
import zipfile
import hashlib

repo_dir = r"D:\workspace\roihan-ai-office"
backup_zip = r"D:\workspace\roihan-ai-office-addendum-v2-backup.zip"

exclude_dirs = {".git", "node_modules", ".venv", ".next", "__pycache__", ".pytest_cache", ".benchmark-tmp", ".codegraph"}

print("Creating backup archive...")
with zipfile.ZipFile(backup_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            if f.endswith(".pyc"):
                continue
            full_path = os.path.join(root, f)
            arcname = os.path.relpath(full_path, repo_dir)
            zf.write(full_path, arcname)

print("Verifying zip integrity...")
with zipfile.ZipFile(backup_zip, "r") as zf:
    test_result = zf.testzip()
    file_count = len(zf.namelist())

h = hashlib.sha256()
with open(backup_zip, "rb") as f:
    while chunk := f.read(65536):
        h.update(chunk)
sha256 = h.hexdigest()
size = os.path.getsize(backup_zip)

print(f"Archive created: {backup_zip}")
print(f"Files archived: {file_count}")
print(f"Integrity test: {'100% OK' if test_result is None else f'CORRUPT: {test_result}'}")
print(f"Size: {size} bytes")
print(f"SHA256: {sha256}")
