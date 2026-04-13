WINDOWS-INSTALLER (2 Dateien)

1) Lege "Hammer File Maker.exe" in diesen Ordner.
2) Starte "install_windows.bat".

Die App wird nach %LocalAppData%\Hammer File Maker installiert
und eine Desktop-Verknuepfung wird erstellt.
Zusätzlich installiert der Installer automatisch (via winget):
- FFmpeg
- LibreOffice
- Inkscape
Auto-Updates sind AUS.
Manuelle Updates:
- winget upgrade --id Gyan.FFmpeg -e
- winget upgrade --id TheDocumentFoundation.LibreOffice -e
- winget upgrade --id Inkscape.Inkscape -e

Alternative (empfohlen fuer Verteilung):
- Build auf Windows mit:
  powershell -ExecutionPolicy Bypass -File .\build_windows_installer.ps1
- Ergebnis:
  dist\installers\Hammer-File-Maker-Windows-Setup.exe
- Diese Setup-EXE installiert App + (falls verfuegbar) Abhaengigkeiten via winget.
