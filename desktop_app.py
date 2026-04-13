import socket
import threading
import time
import sys
import os
from pathlib import Path

from werkzeug.serving import make_server

from app import app


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

    # Small delay to ensure server is up before opening UI window.
    time.sleep(0.25)

    try:
        import webview

        webview.create_window(
            "Hammer File Maker",
            url,
            width=1320,
            height=860,
            min_size=(980, 700),
        )
        webview.start(
            func=lambda: apply_macos_icon(icon_path),
            icon=str(icon_path) if icon_path.exists() else None,
        )
    except Exception:
        import webbrowser

        webbrowser.open(url)
        print(f"Desktop window not available. Browser opened at {url}")
        input("Press Enter to close Hammer File Maker... ")
    finally:
        server_thread.shutdown()


if __name__ == "__main__":
    main()
