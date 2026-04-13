import socket
import threading
import time
import sys
import os
from pathlib import Path

from werkzeug.serving import make_server

from app import app


def startup_log_path() -> Path:
    log_dir = Path.home() / ".hammer_file_maker"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "startup_error.log"


def append_startup_log(message: str):
    try:
        with startup_log_path().open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except Exception:
        pass


def resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent
    return base / relative


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.server = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def apply_macos_icon(icon_path: Path):
    if not icon_path.exists():
        return
    try:
        from AppKit import NSApplication, NSImage

        app_instance = NSApplication.sharedApplication()
        ns_image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
        if ns_image is not None:
            app_instance.setApplicationIconImage_(ns_image)
    except Exception:
        pass


def main():
    append_startup_log("=== App start ===")
    path_entries = [p for p in os.environ.get("PATH", "").split(":") if p]
    for p in (
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
        "/Applications/LibreOffice.app/Contents/MacOS",
        "/Applications/Inkscape.app/Contents/MacOS",
    ):
        if p not in path_entries:
            path_entries.append(p)
    os.environ["PATH"] = ":".join(path_entries)

    host = "127.0.0.1"
    port = free_port()
    url = f"http://{host}:{port}"
    icon_path = resource_path("assets/app_icon.png")

    server_thread = ServerThread(host, port)
    server_thread.start()
    append_startup_log(f"Server started on {url}")

    # Small delay to ensure server is up before opening UI window.
    time.sleep(0.25)

    try:
        import webview
        append_startup_log("pywebview imported")

        webview.create_window(
            "Hammer File Maker",
            url,
            width=1320,
            height=860,
            min_size=(980, 700),
        )
        append_startup_log("webview window created")
        webview.start(
            func=lambda: apply_macos_icon(icon_path),
            icon=str(icon_path) if icon_path.exists() else None,
        )
        append_startup_log("webview loop ended")
    except BaseException as exc:
        append_startup_log(f"webview failed: {exc!r}")
        import webbrowser

        log_path = startup_log_path()
        log_path.write_text(
            (
                "Hammer File Maker startup error\n"
                f"URL: {url}\n"
                f"Error: {exc}\n"
                "Hinweis: Auf Windows wird meist Microsoft Edge WebView2 Runtime benötigt.\n"
            ),
            encoding="utf-8",
        )

        try:
            webbrowser.open(url)
            append_startup_log("browser fallback via webbrowser.open")
        except Exception:
            pass
        if os.name == "nt":
            try:
                os.startfile(url)  # type: ignore[attr-defined]
                append_startup_log("browser fallback via os.startfile")
            except Exception:
                pass

        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Hammer File Maker",
                "Desktop-Fenster konnte nicht gestartet werden.\n\n"
                "Bitte Microsoft Edge WebView2 Runtime installieren und die App erneut starten.\n"
                f"Fehlerlog: {log_path}",
            )
            root.destroy()
            append_startup_log("tkinter error dialog shown")
        except Exception:
            pass

        # Keep server alive for a while so browser fallback can load.
        end_at = time.time() + 300
        while time.time() < end_at:
            time.sleep(0.25)
    finally:
        append_startup_log("server shutdown")
        server_thread.shutdown()


if __name__ == "__main__":
    main()
