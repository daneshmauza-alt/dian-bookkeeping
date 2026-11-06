"""Self-check: parser, dedupe, rekap, Excel. Jalankan: python backend/test_core.py"""
import sys, tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core

ok = gagal = 0

def cek(nama, dapat, harus):
    global ok, gagal
    if dapat == harus:
        ok += 1
        print(f"  ok   {nama}")
    else:
        gagal += 1
        print(f"  FAIL {nama}: dapat {dapat!r}, harus {harus!r}")

def cek_true(nama, nilai):
    cek(nama, bool(nilai), True)

print("nominal")
cek("250.000", core._bersih_nominal("250.000"), 250000)
cek("1.250.000", core._bersih_nominal("1.250.000"), 1250000)
cek("1,250,000", core._bersih_nominal("1,250,000"), 1250000)
cek("25000", core._bersih_nominal("25000"), 25000)
cek("nol ditolak", core._bersih_nominal("0"), None)
cek("sampah ditolak", core._bersih_nominal("abc"), None)

print("tanggal")
cek("06 Nov 2026", core.parse_tanggal("Tanggal : 06 Nov 2026 14:32"), "2026-11-06")
cek("06/11/2026", core.parse_tanggal("tgl 06/11/2026"), "2026-11-06")
cek("2026-11-06 kebalik", core.parse_tanggal("tgl 11/06/2026"), "2026-06-11")
cek("1 Des 2026", core.parse_tanggal("1 Des 2026"), "2026-12-01")
cek("gak ada tanggal", core.parse_tanggal("halo"), None)

print("parser wondr")
email_masuk = """Nominal   : IDR 250.000
Tanggal   : 06 Nov 2026 14:32
Jenis     : KREDIT
Berita    : Transfer dari HAI HELO"""
p = core.parse_email_wondr("Notifikasi wondr by BNI", email_masuk, "msg-1")
cek("nominal", p["nominal"], 250000)
cek("arah", p["arah"], "masuk")
cek("tanggal", p["tanggal"], "2026-11-06")
cek_true("aman", p["aman"])

email_keluar = """Nominal   : IDR 1.500.000
Tanggal   : 05 Nov 2026
Jenis     : DEBIT
Berita    : Transfer ke TOKO TEPUNG JAYA"""
p = core.parse_email_wondr("Notifikasi wondr by BNI", email_keluar, "msg-2")
cek("keluar nominal", p["nominal"], 1500000)
cek("keluar arah", p["arah"], "keluar")

p = core.parse_email_wondr("Notifikasi wondr by BNI", "Transaksi berhasil", "msg-3")
cek("tanpa nominal -> aman False", p["aman"], False)
cek("tanpa nominal -> nominal 0", p["nominal"], 0)

p = core.parse_email_wondr("Promo spesial", "Diskon 50% di toko", "msg-4")
cek("bukan BNI -> tolak", p["nominal"], 0)

print("db: tambah + dedupe")
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    core.DB_PATH = Path(td) / "t.db"
    con = core.connect()

    r1 = core.impor_email(con, "Notifikasi wondr by BNI", email_masuk, "msg-1")
    cek("import pertama masuk", r1["status"], "masuk")
    r2 = core.impor_email(con, "Notifikasi wondr by BNI", email_masuk, "msg-1")
    cek("import kedua duplikat", r2["status"], "duplikat")
    n = con.execute("SELECT COUNT(*) c FROM tx").fetchone()["c"]
    cek("tetap 1 baris", n, 1)

    # nominal sama, message-id beda -> transaksi berbeda (2 roti Rp250rb?)
    r3 = core.impor_email(con, "Notifikasi wondr by BNI", email_masuk, "msg-9")
    cek("msg-id beda = baris baru", r3["status"], "masuk")

    core.tambah(con, "2026-11-06", 45000, "masuk", "Jual roti", metode="tunai")
    core.tambah(con, "2026-11-06", 300000, "keluar", "Beli tepung 25kg")
    core.tambah(con, "2026-11-06", 85000, "keluar", "Token listrik")

    print("kategori otomatis")
    k = con.execute(
        "SELECT kategori FROM tx WHERE keterangan LIKE '%tepung%'").fetchone()["kategori"]
    cek("tepung -> Bahan Baku", k, "Bahan Baku")
    k = con.execute(
        "SELECT kategori FROM tx WHERE keterangan LIKE '%listrik%'").fetchone()["kategori"]
    cek("listrik -> Operasional", k, "Operasional")

    print("rekap")
    r = core.ringkas(con, "2026-11-01", "2026-11-30")
    cek("jumlah transaksi", r["jumlah_transaksi"], 5)
    cek("masuk", r["masuk"], 250000 * 2 + 45000)
    cek("keluar", r["keluar"], 300000 + 85000)
    cek("bahan baku", r["bahan_baku"], 300000)
    cek("laba kotor", r["laba_kotor"], 545000 - 300000)
    cek("selisih", r["selisih"], 545000 - 385000)

    print("minggu")
    a, b, lbl = core.minggu_lalu(date(2026, 11, 6))  # Jumat
    cek("awal minggu lalu", a, "2026-10-26")
    cek("akhir minggu lalu", b, "2026-11-01")
    cek_true("label ada isi", lbl.startswith("Seminggu"))

    print("excel")
    xl = core.tulis_excel(con, "2026-11-01", "2026-11-30",
                          Path(td) / "t.xlsx")
    cek_true("file ada", xl.exists())
    cek_true("file > 4KB", xl.stat().st_size > 4000)

    from openpyxl import load_workbook
    wb = load_workbook(xl)
    cek("nama sheet", wb.sheetnames, ["Ringkasan", "Transaksi", "Piutang"])
    ws = wb["Transaksi"]
    cek("header transaksi", [ws.cell(1, c).value for c in range(1, 9)],
        ["Tanggal", "Uraian", "Kategori", "Masuk", "Keluar", "Sumber",
         "Metode", "Perlu Dicek"])
    # 5 transaksi + header + total = 7 baris
    cek("baris excel", ws.max_row, 7)
    cek_true("ada rumus SUM", str(ws.cell(7, 4).value).startswith("=SUM"))
    wb.close()
    con.close()

print(f"\n{ok} lulus, {gagal} gagal")
sys.exit(1 if gagal else 0)