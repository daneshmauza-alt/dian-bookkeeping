"""Server Diana: sajikan UI + API JSON di atas DB yang sama.

Jalan: python backend/serve.py   ->  http://127.0.0.1:8765

Sengaja stdlib (http.server). Gak ada FastAPI/Flask: satu pengguna, satu laptop,
satu DB. Server yang lebih besar cuma nambah yang bisa rusak.

Cuma dengar di 127.0.0.1 — tidak terbuka ke jaringan rumah.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core

PORT = 8765
DIST = core.ROOT / "app" / "dist"


def _json_default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(f"tidak bisa dijadikan JSON: {type(o)}")


def api_ringkasan(con, q) -> dict:
    hari_ini = date.today()
    awal = q.get("awal", [hari_ini.replace(day=1).isoformat()])[0]
    akhir = q.get("akhir", [hari_ini.isoformat()])[0]
    r = core.ringkas(con, awal, akhir)
    # Tambah data buat grafik harian di dashboard.
    harian = []
    d = date.fromisoformat(awal)
    akhir_d = date.fromisoformat(akhir)
    while d <= akhir_d:
        s = core.ringkas(con, d.isoformat(), d.isoformat())
        harian.append({"tanggal": d.isoformat(), "masuk": s["masuk"],
                       "keluar": s["keluar"]})
        d += timedelta(days=1)
    r["harian"] = harian
    review = con.execute(
        "SELECT COUNT(*) c FROM tx WHERE perlu_review=1 AND tanggal BETWEEN ? AND ?",
        (awal, akhir)).fetchone()["c"]
    r["perlu_review"] = review
    piutang = con.execute(
        "SELECT COALESCE(SUM(nominal),0) t FROM piutang WHERE lunas=0"
    ).fetchone()["t"]
    r["piutang"] = piutang
    return r


def api_transaksi(con, q) -> dict:
    awal = q.get("awal", [""])[0]
    akhir = q.get("akhir", [""])[0]
    cari = q.get("cari", [""])[0].strip()
    kategori = q.get("kategori", [""])[0]
    limit = min(int(q.get("limit", ["200"])[0]), 1000)

    where, par = [], []
    if awal:
        where.append("tanggal >= ?")
        par.append(awal)
    if akhir:
        where.append("tanggal <= ?")
        par.append(akhir)
    if cari:
        where.append("(keterangan LIKE ? OR kategori LIKE ?)")
        par += [f"%{cari}%", f"%{cari}%"]
    if kategori:
        where.append("kategori = ?")
        par.append(kategori)
    sql = "SELECT * FROM tx"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY tanggal DESC, id DESC LIMIT ?"
    par.append(limit)
    rows = [dict(r) for r in con.execute(sql, par)]
    return {"transaksi": rows, "jumlah": len(rows)}


def api_kategori(con) -> dict:
    rows = con.execute(
        "SELECT kategori, COUNT(*) n FROM tx GROUP BY kategori ORDER BY n DESC")
    return {"kategori": [dict(r) for r in rows]}


def api_piutang(con) -> dict:
    rows = con.execute("SELECT * FROM piutang ORDER BY lunas, tanggal DESC LIMIT 300")
    daftar = [dict(r) for r in rows]
    belum = sum(r["nominal"] for r in daftar if not r["lunas"])
    return {"piutang": daftar, "total_belum_lunas": belum}


def _baca_body(handler) -> dict:
    n = int(handler.headers.get("Content-Length") or 0)
    if not n:
        return {}
    try:
        return json.loads(handler.rfile.read(n).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def aksi_catat(con, b: dict) -> dict:
    nominal = int(b.get("nominal") or 0)
    if nominal <= 0:
        return {"ok": False, "pesan": "Nominal harus lebih dari 0."}
    arah = b.get("arah") if b.get("arah") in ("masuk", "keluar") else "masuk"
    tanggal = b.get("tanggal") or date.today().isoformat()
    rid = core.tambah(con, tanggal, nominal, arah,
                      (b.get("keterangan") or "").strip(),
                      sumber="web", metode=b.get("metode") or "tunai",
                      kategori=(b.get("kategori") or "").strip() or None)
    if not rid:
        return {"ok": False, "pesan": "Transaksi kembar sudah ada."}
    row = con.execute("SELECT * FROM tx WHERE id=?", (rid,)).fetchone()
    return {"ok": True, "transaksi": dict(row)}


def aksi_koreksi(con, b: dict) -> dict:
    try:
        rid = int(b.get("id"))
    except (TypeError, ValueError):
        return {"ok": False, "pesan": "ID tidak valid."}
    row = con.execute("SELECT * FROM tx WHERE id=?", (rid,)).fetchone()
    if not row:
        return {"ok": False, "pesan": f"Transaksi #{rid} tidak ada."}

    ubah = {}
    if b.get("arah") in ("masuk", "keluar"):
        ubah["arah"] = b["arah"]
    if b.get("nominal") is not None:
        n = int(b["nominal"])
        if n <= 0:
            return {"ok": False, "pesan": "Nominal harus lebih dari 0."}
        ubah["nominal"] = n
    if "keterangan" in b:
        ubah["keterangan"] = str(b["keterangan"])[:200]
    if b.get("kategori"):
        ubah["kategori"] = str(b["kategori"])[:60]
    if not ubah:
        return {"ok": False, "pesan": "Tidak ada yang diubah."}

    setel = ", ".join(f"{k}=?" for k in ubah)
    con.execute(f"UPDATE tx SET {setel}, perlu_review=0 WHERE id=?",
                (*ubah.values(), rid))
    con.commit()
    return {"ok": True, "transaksi": dict(
        con.execute("SELECT * FROM tx WHERE id=?", (rid,)).fetchone())}


def aksi_hapus(con, b: dict) -> dict:
    try:
        rid = int(b.get("id"))
    except (TypeError, ValueError):
        return {"ok": False, "pesan": "ID tidak valid."}
    cur = con.execute("DELETE FROM tx WHERE id=?", (rid,))
    con.commit()
    if not cur.rowcount:
        return {"ok": False, "pesan": f"Transaksi #{rid} tidak ada."}
    return {"ok": True, "pesan": f"Transaksi #{rid} dihapus."}


def aksi_piutang(con, b: dict) -> dict:
    nama = (b.get("nama") or "").strip()
    nominal = int(b.get("nominal") or 0)
    if not nama or nominal <= 0:
        return {"ok": False, "pesan": "Nama dan nominal harus diisi."}
    con.execute("INSERT INTO piutang (nama, nominal, tanggal) VALUES (?,?,?)",
                (nama[:60], nominal, b.get("tanggal") or date.today().isoformat()))
    con.commit()
    return {"ok": True, "pesan": f"Piutang {nama} dicatat."}


def aksi_lunas(con, b: dict) -> dict:
    try:
        pid = int(b.get("id"))
    except (TypeError, ValueError):
        return {"ok": False, "pesan": "ID tidak valid."}
    cur = con.execute("UPDATE piutang SET lunas=1 WHERE id=?", (pid,))
    con.commit()
    if not cur.rowcount:
        return {"ok": False, "pesan": f"Piutang #{pid} tidak ada."}
    return {"ok": True, "pesan": f"Piutang #{pid} ditandai lunas."}


class Handler(BaseHTTPRequestHandler):
    server_version = "Diana/1.0"

    def log_message(self, fmt, *args):
        pass  # jangan banjirin stdout

    # ---------------- util ----------------

    def _kirim(self, kode: int, tipe: str, isi: bytes, ekstra=None):
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (ekstra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(isi)

    def _json(self, data, kode: int = 200):
        self._kirim(kode, "application/json; charset=utf-8",
                    json.dumps(data, ensure_ascii=False,
                               default=_json_default).encode("utf-8"))

    def _q(self):
        return parse_qs(urlparse(self.path).query)

    # ---------------- GET ----------------

    def do_GET(self):
        path = urlparse(self.path).path
        q = self._q()

        if path.startswith("/api/"):
            con = core.connect()
            try:
                if path == "/api/ringkasan":
                    return self._json(api_ringkasan(con, q))
                if path == "/api/transaksi":
                    return self._json(api_transaksi(con, q))
                if path == "/api/kategori":
                    return self._json(api_kategori(con))
                if path == "/api/piutang":
                    return self._json(api_piutang(con))
                if path == "/api/laporan":
                    awal = q.get("awal", [date.today().isoformat()])[0]
                    akhir = q.get("akhir", [awal])[0]
                    return self._json({"teks": core.laporan_teks(con, awal, akhir)})
                if path == "/api/export.xlsx":
                    awal = q.get("awal", [core.minggu_lalu()[0]])[0]
                    akhir = q.get("akhir", [core.minggu_lalu()[1]])[0]
                    xl = core.tulis_excel(con, awal, akhir)
                    isi = xl.read_bytes()
                    return self._kirim(
                        200,
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet", isi,
                        {"Content-Disposition": f'attachment; filename="{xl.name}"'})
                return self._json({"error": "endpoint tidak ada"}, 404)
            finally:
                con.close()

        # Sajikan UI.
        if path in ("/", "/index.html"):
            idx = DIST / "index.html"
            if not idx.exists():
                pesan = ("UI belum dibuild.\n\nJalankan:\n"
                         "  cd app && npm run build\n\n"
                         "Lalu buka lagi http://127.0.0.1:8765")
                return self._kirim(503, "text/plain; charset=utf-8",
                                   pesan.encode("utf-8"))
            return self._kirim(200, "text/html; charset=utf-8", idx.read_bytes())
        return self._kirim(404, "text/plain; charset=utf-8", b"tidak ada")

    # ---------------- POST ----------------

    def do_POST(self):
        path = urlparse(self.path).path
        b = _baca_body(self)
        con = core.connect()
        try:
            rute = {
                "/api/catat": aksi_catat,
                "/api/koreksi": aksi_koreksi,
                "/api/hapus": aksi_hapus,
                "/api/piutang": aksi_piutang,
                "/api/lunas": aksi_lunas,
            }
            fn = rute.get(path)
            if not fn:
                return self._json({"ok": False, "pesan": "endpoint tidak ada"}, 404)
            return self._json(fn(con, b))
        except Exception as e:
            return self._json({"ok": False,
                               "pesan": f"{type(e).__name__}: {e}"}, 400)
        finally:
            con.close()


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Server Diana")
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--host", default="127.0.0.1")
    a = p.parse_args()

    con = core.connect()
    n = con.execute("SELECT COUNT(*) c FROM tx").fetchone()["c"]
    con.close()

    print(f"Diana jalan di http://{a.host}:{a.port}")
    print(f"Database: {core.DB_PATH}  ({n} transaksi)")
    print("Ctrl+C buat berhenti.")
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())