param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "== Build Windows EXE ==" -ForegroundColor Cyan

if (!(Test-Path ".venv")) {
  & $Python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r .\requirements.txt
& ".\.venv\Scripts\python.exe" -m pip install pyinstaller

if (Test-Path .\build) { Remove-Item .\build -Recurse -Force }
if (Test-Path .\dist) { Remove-Item .\dist -Recurse -Force }

& ".\.venv\Scripts\pyinstaller.exe" `
  --noconfirm `
  --windowed `
  --name "Hammer File Maker" `
  --add-data "templates;templates" `
  --add-data "static;static" `
  --add-data "assets;assets" `
  .\desktop_app.py

Write-Host "== Build Setup EXE (Inno Setup) ==" -ForegroundColor Cyan
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (!(Test-Path $iscc)) {
  $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (!(Test-Path $iscc)) {
  throw "ISCC.exe nicht gefunden. Bitte Inno Setup 6 installieren."
}

& $iscc .\installer_windows_exe.iss

Write-Host "Fertig. Setup liegt in dist\installers\Hammer-File-Maker-Windows-Setup.exe" -ForegroundColor Green
Write-Host "Hinweis: FFmpeg, LibreOffice und Inkscape werden beim Setup auf dem Zielrechner via winget installiert (falls vorhanden)." -ForegroundColor Yellow
