# Local Convert Studio (Offline)

Lokales Browser-Tool (ohne Internet), das sich am Workflow von Convertio und iLoveIMG orientiert.

## Funktionen

- Mehrere Dateien gleichzeitig hochladen (`batch`)
- Bildformate konvertieren: `jpg`, `png`, `webp`, `avif`, `gif`, `bmp`, `tiff`
- Bild-Skalierung:
  - Presets: `25%`, `50%`, `75%`
  - Eigene Größe per Breite/Höhe
- Bild-Komprimierung:
  - Lossy über Qualitätswert
  - Verlustfrei (wo möglich) für `png`, `webp(lossless)`, `avif(lossless)`
- Universal-Konvertierung über FFmpeg (z. B. `.ts -> .mp4`, auch viele Audio/Video-Formate)
- Kategorien im Universal-Converter: Bild, Video, Audio, Dokument, Vektor
- Verfügbarkeit wird lokal erkannt:
  - Audio/Video/Bild (universal): FFmpeg
  - Dokumente: LibreOffice (`soffice`)
  - Vektorformate: Inkscape
- Automatischer ZIP-Download bei mehreren Ergebnissen oder Teilfehlern

## Wichtiger Hinweis zu "voller Convertio/iLoveIMG-Funktionsumfang"

Die Plattformen haben sehr viele Spezialfunktionen (OCR, PDF-Workflows, Cloud-Integrationen, API-Limits, exotische Codecs, etc.).
Dieses Projekt bildet den lokalen Kernumfang für den Alltag ab und läuft komplett offline.

## Voraussetzungen

- Python 3.10+
- FFmpeg installiert und im PATH

### FFmpeg Installation (macOS)

```bash
brew install ffmpeg
```

## Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Im Browser öffnen: `http://127.0.0.1:5000`

## macOS Desktop-App (empfohlen)

Die App kann als echtes macOS-Bundle gebaut werden (ohne Python-Menüname):

```bash
chmod +x build_macos_app.sh
./build_macos_app.sh
```

Danach startest du per Doppelklick:
`~/Desktop/Hammer File Maker.app`

## Installer (macOS + Windows)

- `installer_macos/install_macos.command`
  - installiert die App nach `/Applications`
  - installiert automatisch: `ffmpeg`, `LibreOffice`, `Inkscape`
  - Auto-Updates bleiben aus (nur manueller Update-Hinweis)
- `installer_windows/install_windows.bat`
  - installiert die App nach `%LocalAppData%\Hammer File Maker`
  - erstellt Desktop-Verknüpfung
  - installiert automatisch via `winget`: `ffmpeg`, `LibreOffice`, `Inkscape`
  - Auto-Updates bleiben aus (nur manueller Update-Hinweis)

### Klassische Installer zusätzlich (neu)

- macOS `.dmg` erzeugen:
  - `chmod +x build_macos_dmg.sh`
  - `./build_macos_dmg.sh`
  - Ergebnis: `dist/installers/Hammer-File-Maker-macOS.dmg`
- Windows Setup `.exe` erzeugen (auf Windows ausführen):
  - `powershell -ExecutionPolicy Bypass -File .\build_windows_installer.ps1`
  - Ergebnis: `dist\installers\Hammer-File-Maker-Windows-Setup.exe`
  - Installer installiert App nach `%LocalAppData%\Hammer File Maker` (kein Admin fuer die App-Installation noetig)
  - Installer versucht zusaetzlich automatisch via `winget` zu installieren: `ffmpeg`, `LibreOffice`, `Inkscape`

Hinweis: Die bisherigen Script-Installer bleiben bestehen und funktionieren weiterhin.

## Nutzung

1. Eine oder mehrere Dateien wählen
2. Modus wählen:
   - `Bild-Tools`
   - `Universal-Konvertierung`
3. Optionen setzen
4. `Konvertieren`

## Technische Details

- `.ts -> .mp4` nutzt bevorzugt `-c:v copy` plus AAC für Audio.
- Bei FFmpeg-Fehlern werden fehlerhafte Dateien in `_errors.txt` innerhalb der ZIP protokolliert.
- Upload-Limit aktuell: `10 GiB` (`10.737.418.240 Bytes`).
