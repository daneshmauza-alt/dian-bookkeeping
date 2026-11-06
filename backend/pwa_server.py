"""Wrapper PWA untuk Diana Bookkeeping. 
Bisa diakses dari HP Ibu lewat Wi-Fi lokal kalau laptop & HP di jaringan yang sama."""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys, os
from pathlib import Path

# Path ke file hasil build
os.chdir(str(Path(__file__).resolve().parent.parent / "app" / "dist"))

class PWAHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Service Worker & PWA cache headers
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

print("Diana (Web App) jalan di http://<IP-Laptop-Lu>:8765")
print("Ibu bisa akses dari HP lewat browser (pastikan satu Wi-Fi).")
print("Tekan Ctrl+C buat berhenti.")

HTTPServer(('', 8765), PWAHandler).serve_forever()
