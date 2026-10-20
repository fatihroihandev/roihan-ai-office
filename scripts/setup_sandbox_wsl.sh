#!/bin/sh
# Dijalankan di DALAM distro sandbox sebagai root (lihat setup_sandbox_wsl.ps1).
# Menyiapkan alat, user tanpa hak khusus, dan mengunci distro dari drive Windows serta interop.
set -eu

echo "[1/4] Memasang paket: python3, pytest, util-linux"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends python3 python3-pytest util-linux tar coreutils ca-certificates

echo "[2/4] Membuat user 'sandbox' tanpa hak khusus"
if ! id -u sandbox >/dev/null 2>&1; then
  useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin sandbox
fi
gpasswd -d sandbox sudo >/dev/null 2>&1 || true

echo "[3/4] Mengunci distro: drive Windows tidak ter-mount dan interop dimatikan"
cat > /etc/wsl.conf <<'CONF'
[automount]
enabled=false
mountFsTab=false

[interop]
enabled=false
appendWindowsPath=false
CONF

echo "[4/4] Memeriksa alat isolasi"
for t in unshare prlimit setpriv timeout tar base64 python3; do
  command -v "$t" >/dev/null 2>&1 || { echo "ALAT HILANG: $t" >&2; exit 1; }
done
python3 -c "import pytest; print('pytest', pytest.__version__)"
echo "Selesai. Distro harus di-restart agar wsl.conf berlaku."
