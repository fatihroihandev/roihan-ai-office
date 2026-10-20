<#
  Menyiapkan distro WSL khusus untuk sandbox Roihan (Phase 5).

  Distro Ubuntu Anda TIDAK diubah: skrip menyalinnya menjadi distro baru (default: roihan-sandbox) lalu
  hanya distro baru itu yang dikunci (tanpa mount drive Windows, tanpa interop) dan diberi user 'sandbox'.

  Pemakaian (PowerShell biasa, tidak perlu admin):
    powershell -ExecutionPolicy Bypass -File scripts\setup_sandbox_wsl.ps1
    powershell -ExecutionPolicy Bypass -File scripts\setup_sandbox_wsl.ps1 -Source Ubuntu -Distro roihan-sandbox
#>
param(
  [string]$Source = "Ubuntu",
  [string]$Distro = "roihan-sandbox"
)
$ErrorActionPreference = "Stop"

function Get-Distros { (& wsl.exe -l -q 2>$null | Out-String) -replace "`0", "" -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ } }

$existing = Get-Distros
if ($existing -notcontains $Distro) {
  if ($existing -notcontains $Source) { throw "Distro sumber '$Source' tidak ditemukan. Pasang dulu: wsl --install -d Ubuntu" }
  $dir = Join-Path $env:LOCALAPPDATA "roihan-sandbox"
  $tar = Join-Path $env:TEMP "roihan-sandbox-base.tar"
  Write-Host "Menyalin '$Source' menjadi '$Distro' (butuh beberapa menit dan ruang disk ~2 GB)..."
  & wsl.exe --export $Source $tar
  if ($LASTEXITCODE -ne 0) { throw "wsl --export gagal" }
  & wsl.exe --import $Distro $dir $tar --version 2
  if ($LASTEXITCODE -ne 0) { throw "wsl --import gagal" }
  Remove-Item $tar -Force
} else {
  Write-Host "Distro '$Distro' sudah ada; hanya menjalankan ulang penyiapan."
}

Write-Host "Menjalankan penyiapan di dalam '$Distro'..."
& wsl.exe -d $Distro -u root --cd $PSScriptRoot --exec sh -c "tr -d '\r' < ./setup_sandbox_wsl.sh | sh -s"
if ($LASTEXITCODE -ne 0) { throw "Penyiapan di dalam distro gagal" }

& wsl.exe --terminate $Distro | Out-Null   # menerapkan /etc/wsl.conf pada start berikutnya

Write-Host ""
Write-Host "Selesai. Tambahkan ke .env di root repository, lalu restart backend:"
Write-Host "  SANDBOX_BACKEND=wsl"
Write-Host "  SANDBOX_WSL_DISTRO=$Distro"
Write-Host "Backend akan menjalankan uji isolasi otomatis; hasilnya terlihat di halaman Task."
