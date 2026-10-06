#!/usr/bin/env python3
"""Lokale bonprinter voor de Epson TM-T20II.

Start:  python bonprinter.py
Open:   http://127.0.0.1:8765
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import socket
import sys

HOST = "0.0.0.0"
PORT = int(__import__("os").environ.get("PORT", "8765"))
DEFAULT_PRINTER = "192.168.1.212"
PRINTER_PORT = 9100
WIDTH = 42
PAGE = (Path(__file__).parent / "index.html").read_bytes()


def clip(text, width):
    text = " ".join(str(text).split())
    if len(text) <= width:
        return text
    return text[: width - 1] + "..."


def build_receipt(title, subtitle, footer, items, logo=0):
    data = bytearray()

    def w(*parts):
        for part in parts:
            if isinstance(part, int):
                data.append(part)
            else:
                data.extend(str(part).encode("cp858", errors="replace"))

    w(0x1B, 0x40)
    w(0x1B, 0x74, 19)
    w(0x1B, 0x61, 1)
    if 1 <= logo <= 255:
        # FS p n m: print NV-logo nummer n, normale grootte
        w(0x1C, 0x70, logo, 0)
        w("\n")
    w(0x1B, 0x45, 1)
    w(0x1D, 0x21, 0x11)
    w(clip(title or "LIJST", 20) + "\n")
    w(0x1D, 0x21, 0x00)
    w(0x1B, 0x45, 0)
    if subtitle:
        w(clip(subtitle, WIDTH) + "\n")
    w("\n")
    w(0x1B, 0x61, 0)
    n = 0
    for item in items[:40]:
        task = clip(item.get("task", ""), WIDTH - 4)
        who = clip(item.get("who", ""), WIDTH - 6)
        if not task and not who:
            continue
        n += 1
        w("-" * WIDTH + "\n")
        w("%d. %s\n" % (n, task))
        if who:
            w(0x1B, 0x45, 1)
            w("   -> %s\n" % who)
            w(0x1B, 0x45, 0)
    w("-" * WIDTH + "\n\n")
    if footer:
        w(0x1B, 0x61, 1)
        w(clip(footer, WIDTH) + "\n")
    w("\n\n\n")
    w(0x1D, 0x56, 0x42, 0x00)
    return bytes(data)


def send(ip, payload):
    with socket.create_connection((ip, PRINTER_PORT), timeout=5) as sock:
        sock.sendall(payload)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body, content_type):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
            return
        self._send(404, "niet gevonden", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/print":
            self._send(404, json.dumps({"error": "niet gevonden"}), "application/json")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            job = json.loads(self.rfile.read(length) or b"{}")
            ip = str(job.get("ip") or DEFAULT_PRINTER).strip()
            parts = ip.split(".")
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                raise ValueError("Ongeldig IP-adres")
            logo = int(job.get("logo") or 0)
            if logo < 0 or logo > 255:
                raise ValueError("Logonummer moet tussen 0 en 255 liggen")
            items = job.get("items") or []
            if not isinstance(items, list) or not items:
                raise ValueError("Geen taken om te printen")
            payload = build_receipt(
                job.get("title") or "LIJST",
                job.get("subtitle") or "",
                job.get("footer") or "",
                items,
                logo,
            )
            send(ip, payload)
        except Exception as exc:
            self._send(400, json.dumps({"error": str(exc)}), "application/json")
            return
        self._send(200, json.dumps({"ok": True, "ip": ip}), "application/json")


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Bonprinter draait op http://%s:%s" % (HOST, PORT))
    print("Stoppen met Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGestopt")


if __name__ == "__main__":
    main()
