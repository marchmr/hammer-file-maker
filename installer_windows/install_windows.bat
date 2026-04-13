@echo off
setlocal

set "APP_NAME=Hammer File Maker.exe"
set "SRC_EXE=%~dp0%APP_NAME%"
set "TARGET_DIR=%LocalAppData%\Hammer File Maker"
set "TARGET_EXE=%TARGET_DIR%\%APP_NAME%"
set "WINGET=winget"

if not exist "%SRC_EXE%" (
  echo Fehler: "%APP_NAME%" fehlt im gleichen Ordner wie dieses Script.
  echo Lege die EXE neben "install_windows.bat" und starte erneut.
  pause
  exit /b 1
)

where winget >nul 2>nul
if errorlevel 1 (
  echo Warnung: winget nicht gefunden. Abhaengigkeiten koennen nicht automatisch installiert werden.
  echo Bitte installiere manuell: FFmpeg, LibreOffice, Inkscape.
) else (
  echo Installiere Abhaengigkeiten mit winget...
  %WINGET% install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
  %WINGET% install --id TheDocumentFoundation.LibreOffice -e --accept-package-agreements --accept-source-agreements
  %WINGET% install --id Inkscape.Inkscape -e --accept-package-agreements --accept-source-agreements
)

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
copy /Y "%SRC_EXE%" "%TARGET_EXE%" >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Hammer File Maker.lnk'); $lnk.TargetPath = '%TARGET_EXE%'; $lnk.WorkingDirectory = '%TARGET_DIR%'; $lnk.Save()"

echo Installation abgeschlossen: %TARGET_EXE%
echo Desktop-Verknuepfung erstellt: Hammer File Maker.lnk
echo Hinweis: Updates manuell ausfuehren mit:
echo winget upgrade --id Gyan.FFmpeg -e
echo winget upgrade --id TheDocumentFoundation.LibreOffice -e
echo winget upgrade --id Inkscape.Inkscape -e
pause
endlocal
