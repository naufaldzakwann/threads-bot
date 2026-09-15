<#
.SYNOPSIS
  Build 1 perintah: backend PyInstaller onedir + Electron NSIS (§20). Target total <=500MB browser resources.
#>
$ErrorActionPreference = 'Stop'
pyinstaller --noconfirm --onedir --name thbuzzer-core apps/core/thbuzzer/main.py
npm --prefix apps/ui ci
npm --prefix apps/ui run build
$hash = Get-FileHash dist/THBuzzer.exe -Algorithm SHA256
$hash.Hash | Out-File dist/SHA256SUM.txt
Write-Host "Build OK" $hash.Hash
