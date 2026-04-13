import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import json
import threading
import uuid
import sys
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image, UnidentifiedImageError


def runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = runtime_base_dir()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
APP_CONFIG_DIR = Path.home() / ".hammer_file_maker"
APP_CONFIG_PATH = APP_CONFIG_DIR / "config.json"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "Hammer File Maker Output"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
UPDATE_HINT_CACHE: dict[str, object] = {"checked_at": 0.0, "result": None}
UPDATE_HINT_LOCK = threading.Lock()
UPDATE_HINT_TTL_SECONDS = 6 * 60 * 60

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif", ".avif"}
IMAGE_FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tiff": "TIFF",
    "gif": "GIF",
    "avif": "AVIF",
}

FFMPEG_VIDEO_TARGETS = [
    "mp4",
    "mkv",
    "mov",
    "webm",
    "avi",
    "flv",
    "mpeg",
    "mpg",
    "ts",
    "m4v",
    "3gp",
]
FFMPEG_AUDIO_TARGETS = [
    "mp3",
    "aac",
    "m4a",
    "wav",
    "flac",
    "ogg",
    "opus",
    "aiff",
    "ac3",
    "wma",
]
FFMPEG_IMAGE_TARGETS = [
    "jpg",
    "jpeg",
    "png",
    "webp",
    "bmp",
    "tiff",
    "gif",
    "avif",
]
LIBREOFFICE_DOCUMENT_TARGETS = ["pdf", "docx", "odt", "rtf", "txt", "html", "epub"]
INKSCAPE_VECTOR_TARGETS = ["svg", "pdf", "eps", "ps", "png"]
def default_tool_paths() -> list[str]:
    paths = [
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
        "/Applications/LibreOffice.app/Contents/MacOS",
        "/Applications/Inkscape.app/Contents/MacOS",
    ]
    if os.name == "nt":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_app_data = os.environ.get("LocalAppData", "")
        paths.extend(
            [
                rf"{program_files}\ffmpeg\bin",
                rf"{program_files}\LibreOffice\program",
                rf"{program_files}\Inkscape\bin",
                rf"{program_files_x86}\Inkscape\bin",
                rf"{program_files_x86}\LibreOffice\program",
                rf"{local_app_data}\Microsoft\WinGet\Links" if local_app_data else "",
            ]
        )
    return [p for p in paths if p]


def normalize_name(filename: str) -> str:
    return Path(filename).name or "datei"


def allowed_image_suffix(suffix: str) -> bool:
    return suffix.lower() in IMAGE_EXTENSIONS


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value)


def parse_timestamp_to_seconds(value: str) -> float:
    match = re.match(r"^(\d+):(\d+):(\d+(?:\.\d+)?)$", value.strip())
    if not match:
        return 0.0
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return (hours * 3600) + (minutes * 60) + seconds


def format_bytes(value: int) -> str:
    value = max(0, int(value))
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if size < 1024 or candidate == units[-1]:
            break
        size /= 1024.0
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.2f} {unit}"


def ensure_runtime_path():
    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    for entry in default_tool_paths():
        if entry not in parts:
            parts.append(entry)
    os.environ["PATH"] = os.pathsep.join(parts)


def resolve_command(name: str) -> str | None:
    ensure_runtime_path()
    found = shutil.which(name)
    if found:
        return found
    candidates = [name]
    if os.name == "nt" and not name.lower().endswith(".exe"):
        candidates.append(f"{name}.exe")
    for base in default_tool_paths():
        for cmd in candidates:
            candidate = Path(base) / cmd
            if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def command_exists(name: str) -> bool:
    return resolve_command(name) is not None


def load_config() -> dict:
    if not APP_CONFIG_PATH.exists():
        return {"output_dir": str(DEFAULT_OUTPUT_DIR)}
    try:
        return json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"output_dir": str(DEFAULT_OUTPUT_DIR)}


def save_config(config: dict):
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_output_dir() -> Path:
    config = load_config()
    raw = config.get("output_dir", str(DEFAULT_OUTPUT_DIR))
    return Path(raw).expanduser().resolve()


def set_output_dir(path_text: str):
    output_dir = Path(path_text).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["output_dir"] = str(output_dir)
    save_config(config)


def select_output_dir_desktop(initial_dir: Path) -> str:
    try:
        import webview
    except Exception as exc:
        raise RuntimeError("Desktop-Dialog ist nicht verfügbar.") from exc

    windows = getattr(webview, "windows", [])
    if not windows:
        raise RuntimeError("Desktop-Fenster ist noch nicht bereit.")

    start_dir = initial_dir if initial_dir.exists() else initial_dir.parent
    selected = windows[0].create_file_dialog(
        webview.FOLDER_DIALOG,
        directory=str(start_dir),
    )
    if not selected:
        return ""
    if isinstance(selected, (list, tuple)):
        return str(selected[0])
    return str(selected)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for idx in range(1, 10000):
        candidate = parent / f"{stem} ({idx}){suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Zu viele gleichnamige Dateien im Zielordner.")


def write_results_to_output(results: list[tuple[str, bytes]], errors: list[str]) -> tuple[int, Path, Path | None]:
    out_dir = get_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for filename, payload in results:
        target = unique_path(out_dir / filename)
        target.write_bytes(payload)
        saved += 1

    error_file: Path | None = None
    if errors:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        error_file = out_dir / f"_errors-{stamp}.txt"
        error_file.write_text("\n".join(errors), encoding="utf-8")
    return saved, out_dir, error_file


def create_job(total_files: int) -> str:
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "queued",
            "total": total_files,
            "processed": 0.0,
            "current_file": "",
            "message": "",
            "error": "",
            "output_dir": str(get_output_dir()),
            "saved_count": 0,
        }
    return job_id


def update_job(job_id: str, **fields):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(fields)


def get_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def ffmpeg_available_muxers() -> set[str]:
    ffmpeg_cmd = resolve_command("ffmpeg")
    if not ffmpeg_cmd:
        return set()
    try:
        process = subprocess.run(
            [ffmpeg_cmd, "-hide_banner", "-muxers"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return set()

    muxers: set[str] = set()
    for line in process.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("--"):
            continue
        # Example line: " E mp4             MP4 (MPEG-4 Part 14)"
        parts = line.split()
        if len(parts) >= 2 and "E" in parts[0]:
            muxers.add(parts[1].lower())
    return muxers


def detected_capabilities() -> dict:
    has_ffmpeg = command_exists("ffmpeg")
    has_soffice = command_exists("soffice")
    has_inkscape = command_exists("inkscape")
    muxers = ffmpeg_available_muxers() if has_ffmpeg else set()

    def available_ffmpeg_targets(candidates: list[str]) -> list[str]:
        if not has_ffmpeg:
            return []
        if not muxers:
            return candidates
        return [fmt for fmt in candidates if fmt in muxers]

    categories = {
        "image": sorted(set(IMAGE_FORMAT_MAP.keys())),
        "video": available_ffmpeg_targets(FFMPEG_VIDEO_TARGETS),
        "audio": available_ffmpeg_targets(FFMPEG_AUDIO_TARGETS),
        "document": LIBREOFFICE_DOCUMENT_TARGETS if has_soffice else [],
        "vector": INKSCAPE_VECTOR_TARGETS if has_inkscape else [],
    }

    return {
        "engines": {
            "ffmpeg": has_ffmpeg,
            "soffice": has_soffice,
            "inkscape": has_inkscape,
        },
        "categories": categories,
    }


def dependency_update_hint(capabilities: dict) -> dict:
    default = {"checked": False, "needs_update": False, "items": [], "command": ""}
    if sys.platform != "darwin":
        return default
    if not resolve_command("brew"):
        return default

    now = time.time()
    with UPDATE_HINT_LOCK:
        checked_at = float(UPDATE_HINT_CACHE.get("checked_at", 0.0))
        cached = UPDATE_HINT_CACHE.get("result")
        if cached and (now - checked_at) < UPDATE_HINT_TTL_SECONDS:
            return dict(cached)

    checks: list[tuple[str, str, list[str], bool]] = [
        ("ffmpeg", "FFmpeg", ["brew", "outdated", "--formula", "ffmpeg"], bool(capabilities["engines"]["ffmpeg"])),
        ("libreoffice", "LibreOffice", ["brew", "outdated", "--cask", "libreoffice"], bool(capabilities["engines"]["soffice"])),
        ("inkscape", "Inkscape", ["brew", "outdated", "--cask", "inkscape"], bool(capabilities["engines"]["inkscape"])),
    ]
    outdated_labels: list[str] = []
    outdated_tokens: list[str] = []
    checked_any = False

    for token, label, cmd, installed in checks:
        if not installed:
            continue
        checked_any = True
        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = (process.stdout or "").strip().lower()
        if token in output:
            outdated_labels.append(label)
            outdated_tokens.append(token)

    command_parts: list[str] = []
    if "ffmpeg" in outdated_tokens:
        command_parts.append("brew upgrade ffmpeg")
    cask_outdated = [tok for tok in outdated_tokens if tok in ("libreoffice", "inkscape")]
    if cask_outdated:
        command_parts.append(f"brew upgrade --cask {' '.join(cask_outdated)}")

    result = {
        "checked": checked_any,
        "needs_update": bool(outdated_labels),
        "items": outdated_labels,
        "command": " && ".join(command_parts),
    }
    with UPDATE_HINT_LOCK:
        UPDATE_HINT_CACHE["checked_at"] = now
        UPDATE_HINT_CACHE["result"] = dict(result)
    return result


def image_save_kwargs(target_format: str, quality: int, compress_enabled: bool, lossless: bool) -> dict:
    fmt = target_format.lower()
    kwargs = {}

    if fmt in ("jpg", "jpeg"):
        if compress_enabled:
            # JPEG hat kein echtes Lossless in dieser Pipeline.
            kwargs["quality"] = 100 if lossless else quality
            kwargs["optimize"] = True
            kwargs["progressive"] = True
            kwargs["subsampling"] = 0
        else:
            kwargs["quality"] = 95
            kwargs["subsampling"] = 0

    elif fmt == "png":
        if compress_enabled:
            kwargs["optimize"] = True
            kwargs["compress_level"] = 9

    elif fmt == "webp":
        if compress_enabled:
            kwargs["lossless"] = bool(lossless)
            if not lossless:
                kwargs["quality"] = quality
            kwargs["method"] = 6
        else:
            kwargs["quality"] = 95

    elif fmt == "avif":
        if compress_enabled:
            # Pillow/AVIF unterstützt i.d.R. lossless=True abhängig vom Build.
            if lossless:
                kwargs["lossless"] = True
            else:
                kwargs["quality"] = quality
        else:
            kwargs["quality"] = 95

    elif fmt in ("tiff", "bmp", "gif"):
        # Keine lossy Parameter nötig.
        pass

    return kwargs


def resize_dimensions(
    original_w: int,
    original_h: int,
    scale_mode: str,
    scale_percent: int | None,
    width: int | None,
    height: int | None,
) -> tuple[int, int] | None:
    if scale_mode == "preset" and scale_percent:
        factor = scale_percent / 100
        return max(1, int(original_w * factor)), max(1, int(original_h * factor))

    if scale_mode == "custom" and (width or height):
        if width and not height:
            ratio = width / original_w
            height = max(1, int(original_h * ratio))
        elif height and not width:
            ratio = height / original_h
            width = max(1, int(original_w * ratio))
        return width or original_w, height or original_h

    return None


def process_image_pipeline(
    file_bytes: bytes,
    source_name: str,
    enable_scale: bool,
    scale_mode: str,
    scale_percent: int | None,
    width: int | None,
    height: int | None,
    enable_compress: bool,
    compress_mode: str,
    quality: int,
    enable_convert: bool,
    target_format: str,
):
    warning = None
    source_ext = Path(source_name).suffix.lower().lstrip(".")
    if source_ext not in IMAGE_FORMAT_MAP:
        raise ValueError("Ungültiges Quell-Bildformat.")

    if not (enable_scale or enable_compress or enable_convert):
        return file_bytes, source_name, "application/octet-stream", None

    output_ext = target_format.lower() if enable_convert else source_ext

    with Image.open(io.BytesIO(file_bytes)) as image:
        if output_ext not in IMAGE_FORMAT_MAP:
            raise ValueError("Ungültiges Ziel-Bildformat.")

        if image.mode in ("RGBA", "P") and output_ext in ("jpg", "jpeg"):
            image = image.convert("RGB")

        if enable_scale:
            new_size = resize_dimensions(
                original_w=image.size[0],
                original_h=image.size[1],
                scale_mode=scale_mode,
                scale_percent=scale_percent,
                width=width,
                height=height,
            )
            if new_size:
                image = image.resize(new_size, Image.Resampling.LANCZOS)

        lossless = enable_compress and compress_mode == "lossless"
        if lossless and output_ext in ("jpg", "jpeg"):
            warning = "JPEG unterstützt kein echtes Lossless. Es wurde maximale Optimierung angewendet."

        output = io.BytesIO()
        kwargs = image_save_kwargs(
            target_format=output_ext,
            quality=quality,
            compress_enabled=enable_compress,
            lossless=lossless,
        )
        image.save(output, format=IMAGE_FORMAT_MAP[output_ext], **kwargs)
        output.seek(0)

        out_name = f"{Path(source_name).stem}.{output_ext}"
        mimetype = f"image/{'jpeg' if output_ext in ('jpg', 'jpeg') else output_ext}"

        return output.read(), out_name, mimetype, warning


def ffmpeg_convert(file_bytes: bytes, source_name: str, target_ext: str, progress_cb=None):
    ffmpeg_cmd = resolve_command("ffmpeg")
    if not ffmpeg_cmd:
        raise RuntimeError("FFmpeg ist nicht installiert oder nicht auffindbar.")

    target_ext = target_ext.lower().lstrip(".")

    with tempfile.TemporaryDirectory() as temp_dir:
        in_path = Path(temp_dir) / normalize_name(source_name)
        out_path = Path(temp_dir) / f"{Path(source_name).stem}.{target_ext}"
        if out_path == in_path:
            out_path = Path(temp_dir) / f"{Path(source_name).stem}_converted.{target_ext}"

        with open(in_path, "wb") as f:
            f.write(file_bytes)

        if in_path.suffix.lower() == ".ts" and target_ext == "mp4":
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-hide_banner",
                "-nostats",
                "-i",
                str(in_path),
                "-map",
                "0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-progress",
                "pipe:2",
                str(out_path),
            ]
        else:
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-hide_banner",
                "-nostats",
                "-i",
                str(in_path),
                "-progress",
                "pipe:2",
                str(out_path),
            ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        duration_seconds = 0.0
        error_lines: list[str] = []
        if process.stderr is not None:
            for raw_line in process.stderr:
                line = raw_line.strip()
                if not line:
                    continue
                error_lines.append(line)
                if len(error_lines) > 120:
                    error_lines = error_lines[-120:]

                if duration_seconds <= 0.0 and line.startswith("Duration:"):
                    match = re.search(r"Duration:\s*(\d+:\d+:\d+(?:\.\d+)?)", line)
                    if match:
                        duration_seconds = parse_timestamp_to_seconds(match.group(1))

                if progress_cb and duration_seconds > 0:
                    if line.startswith("out_time_ms="):
                        try:
                            out_time_ms = int(line.split("=", 1)[1].strip())
                            progress = min(0.99, max(0.0, (out_time_ms / 1_000_000.0) / duration_seconds))
                            progress_cb(progress)
                        except ValueError:
                            pass
                    elif line.startswith("out_time="):
                        out_time = line.split("=", 1)[1].strip()
                        out_seconds = parse_timestamp_to_seconds(out_time)
                        if out_seconds > 0:
                            progress = min(0.99, max(0.0, out_seconds / duration_seconds))
                            progress_cb(progress)

        return_code = process.wait()
        if return_code != 0:
            error_text = "\n".join(error_lines[-40:]).strip() or "FFmpeg conversion failed."
            raise RuntimeError(error_text)

        if progress_cb:
            progress_cb(1.0)

        return out_path.read_bytes(), out_path.name


def libreoffice_convert(file_bytes: bytes, source_name: str, target_ext: str):
    soffice_cmd = resolve_command("soffice")
    if not soffice_cmd:
        raise RuntimeError("LibreOffice (soffice) ist nicht installiert.")

    target_ext = target_ext.lower().lstrip(".")
    with tempfile.TemporaryDirectory() as temp_dir:
        in_path = Path(temp_dir) / normalize_name(source_name)
        with open(in_path, "wb") as f:
            f.write(file_bytes)

        cmd = [
            soffice_cmd,
            "--headless",
            "--convert-to",
            target_ext,
            "--outdir",
            temp_dir,
            str(in_path),
        ]
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            error_text = process.stderr.strip() or process.stdout.strip() or "LibreOffice conversion failed."
            raise RuntimeError(error_text)

        expected = Path(temp_dir) / f"{in_path.stem}.{target_ext}"
        if expected.exists():
            return expected.read_bytes(), expected.name

        outputs = [p for p in Path(temp_dir).iterdir() if p.is_file() and p.name != in_path.name]
        if outputs:
            out = outputs[0]
            return out.read_bytes(), out.name

        raise RuntimeError("LibreOffice hat keine Ausgabedatei erzeugt.")


def inkscape_convert(file_bytes: bytes, source_name: str, target_ext: str):
    inkscape_cmd = resolve_command("inkscape")
    if not inkscape_cmd:
        raise RuntimeError("Inkscape ist nicht installiert.")

    target_ext = target_ext.lower().lstrip(".")
    with tempfile.TemporaryDirectory() as temp_dir:
        in_path = Path(temp_dir) / normalize_name(source_name)
        out_path = Path(temp_dir) / f"{Path(source_name).stem}.{target_ext}"

        with open(in_path, "wb") as f:
            f.write(file_bytes)

        cmd = [
            inkscape_cmd,
            str(in_path),
            f"--export-type={target_ext}",
            f"--export-filename={out_path}",
        ]
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            error_text = process.stderr.strip() or process.stdout.strip() or "Inkscape conversion failed."
            raise RuntimeError(error_text)
        if not out_path.exists():
            raise RuntimeError("Inkscape hat keine Ausgabedatei erzeugt.")

        return out_path.read_bytes(), out_path.name


def pack_zip(results: list[tuple[str, bytes]], errors: list[str]) -> io.BytesIO:
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, payload in results:
            zf.writestr(filename, payload)

        if errors:
            zf.writestr("_errors.txt", "\n".join(errors))

    zip_stream.seek(0)
    return zip_stream


def execute_conversion(
    files_data: list[tuple[str, bytes]],
    mode: str,
    form_data: dict,
    progress_cb=None,
) -> tuple[list[tuple[str, bytes]], list[str], list[str]]:
    results: list[tuple[str, bytes]] = []
    errors: list[str] = []
    warnings: list[str] = []
    total = len(files_data)

    if mode == "image":
        enable_scale = form_data.get("enable_scale") == "1"
        enable_compress = form_data.get("enable_compress") == "1"
        enable_convert = form_data.get("enable_convert") == "1"

        scale_mode = form_data.get("scale_mode", "none")
        scale_percent = parse_int(form_data.get("scale_percent"))
        if scale_percent is not None:
            scale_percent = min(100, max(10, scale_percent))
        width = parse_int(form_data.get("width"))
        height = parse_int(form_data.get("height"))
        quality = min(100, max(1, int(form_data.get("quality", "82"))))
        compress_mode = form_data.get("compress_mode", "lossless")
        target_format = form_data.get("image_target_format", "webp").lower()

        for index, (source_name, source_bytes) in enumerate(files_data, start=1):
            if progress_cb:
                progress_cb(index=index, total=total, current_file=source_name)
            source_suffix = Path(source_name).suffix.lower()

            if not allowed_image_suffix(source_suffix):
                errors.append(f"{source_name}: keine unterstützte Bilddatei.")
                continue

            try:
                payload, out_name, _mimetype, warning = process_image_pipeline(
                    file_bytes=source_bytes,
                    source_name=source_name,
                    enable_scale=enable_scale,
                    scale_mode=scale_mode,
                    scale_percent=scale_percent,
                    width=width,
                    height=height,
                    enable_compress=enable_compress,
                    compress_mode=compress_mode,
                    quality=quality,
                    enable_convert=enable_convert,
                    target_format=target_format,
                )
                results.append((out_name, payload))
                if warning:
                    warnings.append(f"{source_name}: {warning}")
            except (UnidentifiedImageError, ValueError) as exc:
                errors.append(f"{source_name}: {exc}")

        return results, errors, warnings

    if mode == "general":
        capabilities = detected_capabilities()
        category = (form_data.get("general_category") or "video").strip().lower()
        target_ext = (form_data.get("general_target_format") or "mp4").lower().strip().lstrip(".")
        if not target_ext:
            raise ValueError("Bitte ein Ziel-Format angeben.")

        allowed = capabilities["categories"].get(category, [])
        if not allowed:
            raise ValueError(f"Die Kategorie '{category}' ist lokal nicht verfügbar.")
        if target_ext not in allowed:
            raise ValueError(f"Ziel-Format '{target_ext}' ist für Kategorie '{category}' lokal nicht verfügbar.")

        for index, (source_name, source_bytes) in enumerate(files_data, start=1):
            if progress_cb:
                progress_cb(index=index, total=total, current_file=source_name)
            try:
                if category in ("video", "audio", "image"):
                    ffmpeg_progress_cb = None
                    if progress_cb:
                        ffmpeg_progress_cb = lambda p, idx=index, src=source_name: progress_cb(
                            index=idx,
                            total=total,
                            current_file=src,
                            file_progress=p,
                        )
                    out_bytes, out_name = ffmpeg_convert(
                        source_bytes,
                        source_name,
                        target_ext,
                        progress_cb=ffmpeg_progress_cb,
                    )
                elif category == "document":
                    out_bytes, out_name = libreoffice_convert(source_bytes, source_name, target_ext)
                elif category == "vector":
                    out_bytes, out_name = inkscape_convert(source_bytes, source_name, target_ext)
                else:
                    raise RuntimeError("Unbekannte Kategorie.")
                results.append((out_name, out_bytes))
            except RuntimeError as exc:
                errors.append(f"{source_name}: {exc}")

        return results, errors, warnings

    raise ValueError("Ungültiger Modus.")


def run_conversion_job(job_id: str, files_data: list[tuple[str, bytes]], mode: str, form_data: dict):
    update_job(job_id, status="running", processed=0, current_file="")

    def on_progress(index: int, total: int, current_file: str, file_progress: float = 0.0):
        file_progress = max(0.0, min(1.0, float(file_progress)))
        processed = max(0.0, min(float(total), float(index - 1) + file_progress))
        update_job(
            job_id,
            current_file=current_file,
            processed=processed,
            total=total,
        )

    try:
        results, errors, warnings = execute_conversion(
            files_data=files_data,
            mode=mode,
            form_data=form_data,
            progress_cb=on_progress,
        )
        if warnings:
            errors.extend(warnings)

        if not results:
            msg = "Keine Datei konnte verarbeitet werden."
            if errors:
                msg += " " + " | ".join(errors[:4])
            update_job(job_id, status="error", error=msg, processed=len(files_data))
            return

        saved_count, out_dir, error_file = write_results_to_output(results=results, errors=errors)
        message = f"{saved_count} Datei(en) gespeichert in: {out_dir}"
        if error_file:
            message += f" | Fehlerprotokoll: {error_file.name}"

        update_job(
            job_id,
            status="done",
            processed=len(files_data),
            current_file="",
            message=message,
            output_dir=str(out_dir),
            saved_count=saved_count,
        )
    except Exception as exc:
        update_job(job_id, status="error", error=str(exc), processed=len(files_data))


def render_index(error: str | None = None, success: str | None = None):
    capabilities = detected_capabilities()
    return render_template(
        "index.html",
        error=error,
        success=success,
        capabilities=capabilities,
        update_hint=dependency_update_hint(capabilities),
        output_dir=str(get_output_dir()),
        max_upload_bytes=MAX_UPLOAD_BYTES,
    )


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_exc: RequestEntityTooLarge):
    max_size = format_bytes(MAX_UPLOAD_BYTES)
    content_length = request.content_length or 0
    actual_size = format_bytes(content_length) if content_length > 0 else "unbekannt"
    message = (
        f"Upload zu groß. Erlaubt sind maximal {max_size} "
        f"({MAX_UPLOAD_BYTES} Bytes) pro Upload-Anfrage "
        f"(empfangen: {actual_size}"
        f"{f' / {content_length} Bytes' if content_length > 0 else ''})."
    )
    if request.path.startswith("/start-job") or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": message, "max_upload_bytes": MAX_UPLOAD_BYTES}), 413
    return render_index(error=message), 413


@app.route("/", methods=["GET"])
def index():
    return render_index()


@app.route("/set-output-dir", methods=["POST"])
def set_output_dir_route():
    path_text = (request.form.get("output_dir") or "").strip()
    if not path_text:
        return jsonify({"ok": False, "error": "Bitte ein gültiges Verzeichnis angeben."}), 400
    try:
        set_output_dir(path_text)
        return jsonify({"ok": True, "output_dir": str(get_output_dir())})
    except OSError as exc:
        return jsonify({"ok": False, "error": f"Ordner konnte nicht gesetzt werden: {exc}"}), 400


@app.route("/select-output-dir", methods=["POST"])
def select_output_dir_route():
    try:
        selected = select_output_dir_desktop(get_output_dir())
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Ordnerdialog nicht verfügbar: {exc}"}), 500

    if not selected:
        return jsonify({"ok": False, "error": "Kein Ordner ausgewählt."}), 400

    try:
        set_output_dir(selected)
    except OSError as exc:
        return jsonify({"ok": False, "error": f"Ordner konnte nicht gesetzt werden: {exc}"}), 400

    return jsonify({"ok": True, "output_dir": str(get_output_dir())})


@app.route("/start-job", methods=["POST"])
def start_job_route():
    files = request.files.getlist("files")
    files = [f for f in files if f and f.filename]
    if not files:
        return jsonify({"ok": False, "error": "Bitte mindestens eine Datei auswählen."}), 400

    files_data: list[tuple[str, bytes]] = []
    for item in files:
        source_name = normalize_name(item.filename)
        files_data.append((source_name, item.read()))

    mode = request.form.get("mode", "image")
    form_data = {k: v for k, v in request.form.items()}

    job_id = create_job(total_files=len(files_data))
    thread = threading.Thread(
        target=run_conversion_job,
        args=(job_id, files_data, mode, form_data),
        daemon=True,
    )
    thread.start()
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/job-status/<job_id>", methods=["GET"])
def job_status_route(job_id: str):
    job = get_job(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job nicht gefunden."}), 404
    total = max(1, int(job.get("total", 1)))
    processed = float(job.get("processed", 0.0))
    percent = min(100, int((processed / total) * 100))
    completed = max(0, min(total, int(processed)))
    return jsonify(
        {
            "ok": True,
            "status": job.get("status", "queued"),
            "processed": processed,
            "completed": completed,
            "total": total,
            "percent": percent,
            "current_file": job.get("current_file", ""),
            "message": job.get("message", ""),
            "error": job.get("error", ""),
            "output_dir": job.get("output_dir", str(get_output_dir())),
            "saved_count": int(job.get("saved_count", 0)),
        }
    )


@app.route("/convert", methods=["POST"])
def convert():
    files = request.files.getlist("files")
    files = [f for f in files if f and f.filename]

    if not files:
        return render_index("Bitte mindestens eine Datei auswählen.")

    mode = request.form.get("mode", "image")
    files_data: list[tuple[str, bytes]] = []
    for item in files:
        files_data.append((normalize_name(item.filename), item.read()))
    form_data = {k: v for k, v in request.form.items()}

    try:
        results, errors, warnings = execute_conversion(
            files_data=files_data,
            mode=mode,
            form_data=form_data,
            progress_cb=None,
        )

        if not results:
            combined = errors + warnings
            msg = "Keine Datei konnte verarbeitet werden."
            if combined:
                msg += " " + " | ".join(combined[:4])
            return render_index(msg)

        if warnings:
            errors.extend(warnings)

        saved_count, out_dir, error_file = write_results_to_output(results=results, errors=errors)
        message = f"{saved_count} Datei(en) gespeichert in: {out_dir}"
        if error_file:
            message += f" | Fehlerprotokoll: {error_file.name}"
        return render_index(success=message)

    except ValueError:
        return render_index("Ungültige Zahlenwerte in den Optionen.")
    except FileNotFoundError:
        return render_index("Ein benötigtes Tool ist nicht installiert oder nicht im PATH verfügbar.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug_mode = os.environ.get("HAMMER_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    app.run(host="127.0.0.1", port=port, debug=debug_mode)
