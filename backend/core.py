"""Diana Bookkeeping — inti: DB, parser, rekap, Excel, Telegram.

Satu file. SQLite + stdlib. openpyxl cuma dipakai saat bikin Excel.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "diana.db"
OUT_DIR = ROOT / "out"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tx (
  id            INTEGER PRIMARY KEY,
  tanggal       TEXT NOT NULL,
  nominal       INTEGER NOT NULL,
  arah          TEXT NOT NULL CHECK (arah IN ('masuk','keluar')),
  kategori      TEXT NOT NULL DEFAULT 'Lain-lain',
  keterangan    TEXT NOT NULL DEFAULT '',
  sumber        TEXT NOT NULL DEFAULT 'manual',
  metode        TEXT NOT NULL DEFAULT 'tunai',
  fingerprint   TEXT NOT NULL UNIQUE,
  perlu_review  INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tx_tanggal ON tx(tanggal);

CREATE TABLE IF NOT EXISTS kategori_rule (
  kata     TEXT PRIMARY KEY,
  kategori TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS piutang (
  id       INTEGER PRIMARY KEY,
  nama     TEXT NOT NULL,
  nominal  INTEGER NOT NULL,
  tanggal  TEXT NOT NULL,
  lunas    INTEGER NOT NULL DEFAULT 0
);
"""

# Tebakan kategori dari kata kunci. Gampang ditimpa lewat tabel kategori_rule.
DEFAULT_RULES = [
    ("tepung", "Bahan Baku"),
    ("mentega", "Bahan Baku"),
    ("margarin", "Bahan Baku"),
    ("gula", "Bahan Baku"),
    ("telur", "Bahan Baku"),
    ("ragi", "Bahan Baku"),
    ("coklat", "Bahan Baku"),
    ("keju", "Bahan Baku"),
    ("susu", "Bahan Baku"),
    ("gas", "Operasional"),
    ("listrik", "Operasional"),
    ("token", "Operasional"),
    ("bensin", "Operasional"),
    ("kemasan", "Operasional"),
    ("plastik", "Operasional"),
    ("kertas", "Operasional"),
    ("sewa", "Operasional"),
    ("gaji", "Operasional"),
    ("iklan", "Operasional"),
]

BULAN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5, "jun": 6,
    "jul": 7, "agu": 8, "aug": 8, "ags": 8, "sep": 9, "okt": 10, "oct": 10,
    "nov": 11, "des": 12, "dec": 12,
}

MASUK_KW = ("kredit", "cr", "masuk", "terima", "diterima", "pemasukan",
            "transfer dari", "setoran", "top up", "refund", "pengembalian")
KELUAR_KW = ("debit", "db", "keluar", "bayar", "pembayaran", "transfer ke",
             "penarikan", "tarik", "belanja", "pembelian", "tagihan", "biaya")


# ---------------------------------------------------------------- koneksi

def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.executemany("INSERT OR IGNORE INTO kategori_rule VALUES (?,?)",
                    DEFAULT_RULES)
    con.commit()
    return con


def fingerprint(tanggal: str, nominal: int, arah: str, ket: str,
                sumber: str = "", message_id: str = "") -> str:
    """Kunci anti-duplikat. Message-ID email menang kalau ada."""
    raw = message_id or f"{tanggal}|{nominal}|{arah}|{ket.strip().lower()}"
    return hashlib.sha256(f"{sumber[:12]}|{raw}".encode()).hexdigest()[:32]


# ---------------------------------------------------------------- kategori

def tebak_kategori(con: sqlite3.Connection, ket: str, arah: str) -> str:
    if arah == "masuk":
        return "Penjualan"
    low = ket.lower()
    for row in con.execute("SELECT kata, kategori FROM kategori_rule"):
        if row["kata"] in low:
            return row["kategori"]
    return "Lain-lain"


# ---------------------------------------------------------------- tulis

def tambah(con, tanggal, nominal, arah, keterangan="", sumber="manual",
           metode="tunai", kategori=None, perlu_review=0,
           message_id="") -> int | None:
    """Tambah satu transaksi. Return id, atau None kalau duplikat."""
    if arah not in ("masuk", "keluar"):
        raise ValueError(f"arah tidak valid: {arah!r}")
    nominal = int(nominal)
    if nominal <= 0:
        raise ValueError(f"nominal harus positif: {nominal}")
    kategori = kategori or tebak_kategori(con, keterangan, arah)
    fp = fingerprint(tanggal, nominal, arah, keterangan, sumber, message_id)
    try:
        cur = con.execute(
            """INSERT INTO tx (tanggal, nominal, arah, kategori, keterangan,
                               sumber, metode, fingerprint, perlu_review)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (tanggal, nominal, arah, kategori, keterangan, sumber, metode,
             fp, int(perlu_review)))
        con.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None  # sudah ada


# ---------------------------------------------------------------- parser

NOMINAL_PAT = re.compile(
    r"(?:IDR|Rp\.?)\s*([\d.,]{3,})", re.IGNORECASE)
TGL_PAT_ANGKA = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
TGL_PAT_TEKS = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b")
JAM_PAT = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")


def _bersih_nominal(s: str) -> int | None:
    """'250.000' / '1,250,000' / '250000' -> int. None kalau ragu."""
    s = s.strip()
    if not s:
        return None
    # Buang pemisah ribuan; kalau ada koma 2 digit di ekor, itu desimal.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):       # gaya 1.250.000,50
            s = s.replace(".", "").replace(",", ".")
        else:                                  # gaya 1,250,000.50
            s = s.replace(",", "")
    elif s.count(",") == 1 and len(s.split(",")[-1]) == 2:
        s = s.replace(",", ".")
    else:
        s = s.replace(".", "").replace(",", "")
    try:
        val = float(s)
    except ValueError:
        return None
    if val <= 0 or val > 1_000_000_000:
        return None
    return int(round(val))


def parse_tanggal(teks: str, sekarang: date | None = None) -> str | None:
    """Cari tanggal di teks. Indonesia & angka. Return ISO atau None."""
    sekarang = sekarang or date.today()

    m = TGL_PAT_TEKS.search(teks)
    if m:
        d, bln, y = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
        if bln in BULAN and 1 <= d <= 31:
            try:
                return date(y, BULAN[bln], d).isoformat()
            except ValueError:
                pass

    m = TGL_PAT_ANGKA.search(teks)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        # Tukar kalau jelas kebalik (US style).
        if a > 12 and b <= 12:
            a, b = b, a
        if 1 <= b <= 12 and 1 <= a <= 31:
            try:
                return date(y, b, a).isoformat()
            except ValueError:
                pass
    return None


def parse_email_wondr(subject: str, body: str, message_id: str = "",
                      terima_tgl: str | None = None) -> dict:
    """Bongkar email Wondr. Selalu balikin dict; 'aman'=False kalau ragu.

    Aturan keras: kalau nominal gak ketemu, jangan nebak. Tandai review.
    """
    teks = f"{subject}\n{body}"
    hasil = {
        "aman": False, "tanggal": None, "nominal": 0, "arah": "masuk",
        "keterangan": "", "message_id": message_id, "alasan": "",
    }

    if "wondr" not in teks.lower() and "bni" not in teks.lower():
        hasil["alasan"] = "bukan email Wondr/BNI"
        return hasil

    m = NOMINAL_PAT.search(teks)
    if not m:
        hasil["alasan"] = "nominal tidak ketemu"
        return hasil
    nominal = _bersih_nominal(m.group(1))
    if not nominal:
        hasil["alasan"] = f"nominal tidak valid: {m.group(1)!r}"
        return hasil
    hasil["nominal"] = nominal

    hasil["tanggal"] = (parse_tanggal(teks) or terima_tgl
                        or date.today().isoformat())

    low = teks.lower()
    keluar_hit = sum(k in low for k in KELUAR_KW)
    masuk_hit = sum(k in low for k in MASUK_KW)
    hasil["arah"] = "keluar" if keluar_hit > masuk_hit else "masuk"
    if keluar_hit == masuk_hit:
        hasil["alasan"] = "arah transaksi ambigu"

    subj_bersih = re.sub(r"^(re|fwd?)\s*:\s*", "", subject.strip(), flags=re.I)
    hasil["keterangan"] = subj_bersih[:200] or "Transaksi Wondr"
    hasil["aman"] = not hasil["alasan"]
    return hasil


def impor_email(con, subject: str, body: str, message_id: str = "",
                terima_tgl: str | None = None) -> dict:
    """Parse + simpan. Return {'status': 'masuk'|'duplikat'|'review'|'tolak'}."""
    p = parse_email_wondr(subject, body, message_id, terima_tgl)
    if not p["nominal"]:
        return {"status": "tolak", "alasan": p["alasan"]}

    tanggal = p["tanggal"] or date.today().isoformat()
    if not p["aman"]:
        # Simpan tapi tandai. Nominal tetap benar, cuma arah perlu dipastikan.
        rid = tambah(con, tanggal, p["nominal"], p["arah"],
                     p["keterangan"], sumber="email", metode="transfer",
                     perlu_review=1, message_id=p["message_id"])
        return {"status": "review" if rid else "duplikat",
                "id": rid, "alasan": p["alasan"], **p}

    rid = tambah(con, tanggal, p["nominal"], p["arah"],
                 p["keterangan"], sumber="email", metode="transfer",
                 message_id=p["message_id"])
    return {"status": "masuk" if rid else "duplikat", "id": rid, **p}


# ---------------------------------------------------------------- rekap

def ringkas(con, awal: str, akhir: str) -> dict:
    """Ringkasan satu rentang tanggal (inklusif)."""
    q = "SELECT arah, nominal, kategori FROM tx WHERE tanggal BETWEEN ? AND ?"
    masuk = keluar = 0
    per_kat: dict[str, int] = {}
    n = 0
    for r in con.execute(q, (awal, akhir)):
        n += 1
        if r["arah"] == "masuk":
            masuk += r["nominal"]
        else:
            keluar += r["nominal"]
            per_kat[r["kategori"]] = per_kat.get(r["kategori"], 0) + r["nominal"]
    bahan = per_kat.get("Bahan Baku", 0)
    return {
        "awal": awal, "akhir": akhir, "jumlah_transaksi": n,
        "masuk": masuk, "keluar": keluar, "selisih": masuk - keluar,
        "bahan_baku": bahan,
        "laba_kotor": masuk - bahan,   # laba kotor = omzet - bahan baku
        "per_kategori": dict(sorted(per_kat.items(), key=lambda x: -x[1])),
    }


def minggu_lalu(hari_ini: date | None = None) -> tuple[str, str, str]:
    """Rentang Senin-Minggu yang barusan selesai.

    Return (awal, akhir, label) dengan label 'Seminggu 3-9 Nov 2026'.
    """
    hari_ini = hari_ini or date.today()
    # Senin minggu ini, lalu mundur 7 hari -> Senin minggu lalu
    senin_ini = hari_ini - timedelta(days=hari_ini.weekday())
    awal = senin_ini - timedelta(days=7)
    akhir = senin_ini - timedelta(days=1)
    label = f"Seminggu {awal.day}-{akhir.day} {nama_bulan(akhir.month)} {akhir.year}"
    return awal.isoformat(), akhir.isoformat(), label


def nama_bulan(b: int) -> str:
    return ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
            "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][b]


def rupiah(n: int) -> str:
    return f"Rp {n:,}".replace(",", ".")


def laporan_teks(con, awal: str, akhir: str, judul: str | None = None) -> str:
    """Laporan buat dibaca di Telegram. Plain text, tanpa emoji."""
    r = ringkas(con, awal, akhir)
    judul = judul or f"Rekap {awal} s/d {akhir}"
    if r["jumlah_transaksi"] == 0:
        return f"{judul}\n\nBelum ada transaksi tercatat di rentang ini."

    baris = [
        judul, "",
        f"Transaksi     : {r['jumlah_transaksi']}",
        f"Uang masuk    : {rupiah(r['masuk'])}",
        f"Uang keluar   : {rupiah(r['keluar'])}",
        f"Selisih       : {rupiah(r['selisih'])}",
        "",
        f"Bahan baku    : {rupiah(r['bahan_baku'])}",
        f"Laba kotor    : {rupiah(r['laba_kotor'])}",
    ]
    if r["per_kategori"]:
        baris += ["", "Pengeluaran per kategori:"]
        for k, v in r["per_kategori"].items():
            baris.append(f"  {k}: {rupiah(v)}")

    review = con.execute(
        "SELECT COUNT(*) c FROM tx WHERE perlu_review=1 AND tanggal BETWEEN ? AND ?",
        (awal, akhir)).fetchone()["c"]
    if review:
        baris += ["", f"PERLU DICEK: {review} baris arahnya belum pasti."]

    piutang = con.execute(
        "SELECT COALESCE(SUM(nominal),0) t FROM piutang WHERE lunas=0").fetchone()["t"]
    if piutang:
        baris += ["", f"Piutang belum lunas: {rupiah(piutang)}"]
    return "\n".join(baris)


# ---------------------------------------------------------------- excel

def tulis_excel(con, awal: str, akhir: str, path: Path | None = None) -> Path:
    """Bikin .xlsx 3 sheet: Ringkasan, Transaksi, Piutang."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = path or OUT_DIR / f"rekap-{awal}_sd_{akhir}.xlsx"

    wb = Workbook()
    tebal = Font(bold=True)
    kepala = PatternFill("solid", fgColor="E8E4DA")   # krem roti, bukan biru
    uang = '"Rp"#,##0'

    # -- Sheet 1: Ringkasan
    ws = wb.active
    ws.title = "Ringkasan"
    r = ringkas(con, awal, akhir)
    ws["A1"] = "DIAN SNACK — Rekap Keuangan"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"{awal} sampai {akhir}"
    ws.append([])
    for label, val in [
        ("Jumlah transaksi", r["jumlah_transaksi"]),
        ("Uang masuk", r["masuk"]),
        ("Uang keluar", r["keluar"]),
        ("Selisih", r["selisih"]),
        ("Bahan baku", r["bahan_baku"]),
        ("Laba kotor", r["laba_kotor"]),
    ]:
        ws.append([label, val])
        if isinstance(val, int) and label != "Jumlah transaksi":
            ws.cell(ws.max_row, 2).number_format = uang
    ws.append([])
    ws.append(["Pengeluaran per kategori", "Nominal"])
    ws.cell(ws.max_row, 1).font = tebal
    ws.cell(ws.max_row, 2).font = tebal
    for k, v in r["per_kategori"].items():
        ws.append([k, v])
        ws.cell(ws.max_row, 2).number_format = uang
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 18

    # -- Sheet 2: Transaksi
    ws2 = wb.create_sheet("Transaksi")
    kol = ["Tanggal", "Uraian", "Kategori", "Masuk", "Keluar", "Sumber",
           "Metode", "Perlu Dicek"]
    ws2.append(kol)
    for c in range(1, len(kol) + 1):
        cell = ws2.cell(1, c)
        cell.font = tebal
        cell.fill = kepala
        cell.alignment = Alignment(horizontal="center")

    for row in con.execute(
            "SELECT * FROM tx WHERE tanggal BETWEEN ? AND ? ORDER BY tanggal, id",
            (awal, akhir)):
        ws2.append([
            row["tanggal"], row["keterangan"], row["kategori"],
            row["nominal"] if row["arah"] == "masuk" else None,
            row["nominal"] if row["arah"] == "keluar" else None,
            row["sumber"], row["metode"],
            "YA" if row["perlu_review"] else "",
        ])
        ws2.cell(ws2.max_row, 4).number_format = uang
        ws2.cell(ws2.max_row, 5).number_format = uang

    if ws2.max_row > 1:
        # Baris total pakai rumus Excel asli, bukan angka mati.
        n = ws2.max_row
        ws2.append(["", "TOTAL", "", f"=SUM(D2:D{n+1})", f"=SUM(E2:E{n+1})",
                    "", "", ""])
        for c in (2, 4, 5):
            ws2.cell(ws2.max_row, c).font = tebal
            ws2.cell(ws2.max_row, c).number_format = uang
        ws2.auto_filter.ref = f"A1:H{n+1}"
    ws2.freeze_panes = "A2"
    for c, w in zip("ABCDEFGH", (12, 40, 16, 14, 14, 10, 12, 11)):
        ws2.column_dimensions[c].width = w

    # -- Sheet 3: Piutang
    ws3 = wb.create_sheet("Piutang")
    ws3.append(["Nama", "Nominal", "Tanggal", "Status"])
    for c in range(1, 5):
        ws3.cell(1, c).font = tebal
        ws3.cell(1, c).fill = kepala
    for row in con.execute("SELECT * FROM piutang ORDER BY lunas, tanggal"):
        ws3.append([row["nama"], row["nominal"], row["tanggal"],
                    "Lunas" if row["lunas"] else "Belum"])
        ws3.cell(ws3.max_row, 2).number_format = uang
    sisa = con.execute(
        "SELECT COALESCE(SUM(nominal),0) t FROM piutang WHERE lunas=0").fetchone()["t"]
    ws3.append(["Total belum lunas", sisa, "", ""])
    ws3.cell(ws3.max_row, 1).font = tebal
    ws3.cell(ws3.max_row, 2).font = tebal
    ws3.cell(ws3.max_row, 2).number_format = uang
    for c, w in zip("ABCD", (28, 16, 14, 12)):
        ws3.column_dimensions[c].width = w

    wb.save(path)
    return path


# ---------------------------------------------------------------- telegram

def tg_send(token: str, chat_id: str, teks: str) -> dict:
    import requests
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": teks[:4000],
              "disable_web_page_preview": True},
        timeout=30)
    return r.json()


def tg_send_doc(token: str, chat_id: str, path: Path, caption: str = "") -> dict:
    import requests
    with open(path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat_id, "caption": caption[:1000]},
            files={"document": (path.name, f)},
            timeout=120)
    return r.json()


def kirim_rekap_mingguan(con, token: str, chat_id: str) -> dict:
    awal, akhir, label = minggu_lalu()
    teks = laporan_teks(con, awal, akhir, label)
    hasil = {"label": label, "awal": awal, "akhir": akhir}
    hasil["pesan"] = tg_send(token, chat_id, teks)
    if ringkas(con, awal, akhir)["jumlah_transaksi"]:
        xl = tulis_excel(con, awal, akhir)
        hasil["excel"] = str(xl)
        hasil["file"] = tg_send_doc(token, chat_id, xl, label)
    return hasil


# ---------------------------------------------------------------- CLI

def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    con = connect()

    if cmd == "init":
        print(f"DB siap: {DB_PATH}")

    elif cmd == "tambah":
        # tambah <tgl> <nominal> <masuk|keluar> <keterangan...>
        tgl, nom, arah = argv[2], int(argv[3]), argv[4]
        ket = " ".join(argv[5:])
        rid = tambah(con, tgl, nom, arah, ket)
        print(json.dumps({"id": rid, "status": "masuk" if rid else "duplikat"}))

    elif cmd == "lapor":
        awal = argv[2] if len(argv) > 2 else date.today().isoformat()
        akhir = argv[3] if len(argv) > 3 else awal
        print(laporan_teks(con, awal, akhir))

    elif cmd == "minggu":
        awal, akhir, label = minggu_lalu()
        print(laporan_teks(con, awal, akhir, label))

    elif cmd == "excel":
        awal = argv[2] if len(argv) > 2 else minggu_lalu()[0]
        akhir = argv[3] if len(argv) > 3 else minggu_lalu()[1]
        print(tulis_excel(con, awal, akhir))

    elif cmd == "kirim":
        token, chat = os.environ.get("TG_TOKEN", ""), os.environ.get("TG_CHAT", "")
        if not token or not chat:
            print("TG_TOKEN dan TG_CHAT harus diisi di .env", file=sys.stderr)
            return 1
        print(json.dumps(kirim_rekap_mingguan(con, token, chat),
                         ensure_ascii=False, indent=2))

    else:
        print(f"perintah tidak dikenal: {cmd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
