"""Entry point WSGI buat PythonAnywhere (dan host mana pun yang support WSGI).

PythonAnywhere gak jalanin `python serve.py` — dia manggil WSGI callable.
File ini cuma membungkus fungsi API yang udah ada di serve.py. Gak ada
logika baru, gak ada framework baru: stdlib murni, persis kayak server lokal.

Config WSGI di dashboard PythonAnywhere:
    /home/<username>/dian-bookkeeping/backend/wsgi.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import core  # noqa: E402
from serve import (  # noqa: E402
    _json_default,
    aksi_catat,
    aksi_hapus,
    aksi_koreksi,
    aksi_lunas,
    aksi_piutang,
    api_kategori,
    api_piutang,
    api_ringkasan,
    api_transaksi,
)

DIST = core.ROOT / "app" / "dist"

RUTE_GET = {
    "/api/ringkasan": api_ringkasan,
    "/api/transaksi": api_transaksi,
    "/api/kategori": lambda con, q: api_kategori(con),
    "/api/piutang": lambda con, q: api_piutang(con),
}

RUTE_POST = {
    "/api/catat": aksi_catat,
    "/api/koreksi": aksi_koreksi,
    "/api/hapus": aksi_hapus,
    "/api/piutang": aksi_piutang,
    "/api/lunas": aksi_lunas,
}


def _baca_body(environ) -> dict:
    try:
        n = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return {}
    if not n:
        return {}
    try:
        return json.loads(environ["wsgi.input"].read(n).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def _start(start_response, kode: int, tipe: str, isi: bytes, ekstra=None):
    hdr = [("Content-Type", tipe),
           ("Content-Length", str(len(isi))),
           ("Cache-Control", "no-store")]
    hdr += list((ekstra or {}).items())
    start_response(f"{kode} " + {200: "OK", 404: "Not Found",
                                 503: "Service Unavailable"}.get(kode, "Error"), hdr)
    return [isi]


def application(environ, start_response):
    path = urlparse(environ.get("PATH_INFO", "/")).path
    q = parse_qs(environ.get("QUERY_STRING", ""))
    metode = environ.get("REQUEST_METHOD", "GET")

    # --- API GET ---
    if metode == "GET" and path in RUTE_GET:
        con = core.connect()
        try:
            data = RUTE_GET[path](con, q)
            isi = json.dumps(data, ensure_ascii=False, default=_json_default).encode("utf-8")
            return _start(start_response, 200, "application/json; charset=utf-8", isi)
        finally:
            con.close()

    if metode == "GET" and path == "/api/laporan":
        con = core.connect()
        try:
            awal = q.get("awal", [date.today().isoformat()])[0]
            akhir = q.get("akhir", [awal])[0]
            isi = json.dumps({"teks": core.laporan_teks(con, awal, akhir)},
                             ensure_ascii=False).encode("utf-8")
            return _start(start_response, 200, "application/json; charset=utf-8", isi)
        finally:
            con.close()

    if metode == "GET" and path == "/api/export.xlsx":
        con = core.connect()
        try:
            awal = q.get("awal", [core.minggu_lalu()[0]])[0]
            akhir = q.get("akhir", [core.minggu_lalu()[1]])[0]
            xl = core.tulis_excel(con, awal, akhir)
            return _start(
                start_response, 200,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                xl.read_bytes(),
                {"Content-Disposition": f'attachment; filename="{xl.name}"'})
        finally:
            con.close()

    # --- API POST ---
    if metode == "POST" and path in RUTE_POST:
        con = core.connect()
        try:
            data = RUTE_POST[path](con, _baca_body(environ))
            isi = json.dumps(data, ensure_ascii=False, default=_json_default).encode("utf-8")
            return _start(start_response, 200, "application/json; charset=utf-8", isi)
        except Exception as e:
            isi = json.dumps({"ok": False, "pesan": f"{type(e).__name__}: {e}"}).encode("utf-8")
            return _start(start_response, 200, "application/json; charset=utf-8", isi)
        finally:
            con.close()

    # --- UI ---
    if metode == "GET" and path in ("/", "/index.html"):
        idx = DIST / "index.html"
        if not idx.exists():
            return _start(start_response, 503, "text/plain; charset=utf-8",
                          b"UI belum dibuild: jalankan `cd app && npm run build` "
                          b"lalu commit dist/index.html.")
        return _start(start_response, 200, "text/html; charset=utf-8", idx.read_bytes())

    return _start(start_response, 404, "text/plain; charset=utf-8", b"tidak ada")
