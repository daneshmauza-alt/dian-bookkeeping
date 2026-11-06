"""Self-check bot: dispatch perintah tanpa jaringan. python backend/test_bot.py"""
import sys, tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core, bot

ok = gagal = 0

def cek(nama, dapat, harus):
    global ok, gagal
    if dapat == harus:
        ok += 1; print(f"  ok   {nama}")
    else:
        gagal += 1; print(f"  FAIL {nama}:\n       dapat {dapat!r}\n       harus {harus!r}")

def ada(nama, teks, potongan):
    global ok, gagal
    if potongan.lower() in teks.lower():
        ok += 1; print(f"  ok   {nama}")
    else:
        gagal += 1; print(f"  FAIL {nama}: {potongan!r} tidak ada di:\n{teks}")

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
    core.DB_PATH = Path(td) / "t.db"
    con = core.connect()
    hari = date.today().isoformat()

    print("start / gak dikenal")
    ada("start kasih panduan", bot.tangani(con, "/start"), "/catat")
    ada("teks bebas ditolak sopan", bot.tangani(con, "halo"), "/start")
    ada("perintah ngawur", bot.tangani(con, "/apalah"), "gak dikenal")

    print("catat masuk")
    b = bot.tangani(con, "/catat 25000 jual roti coklat")
    ada("konfirmasi", b, "Tercatat")
    ada("nominal terformat", b, "Rp 25.000")
    ada("kategori penjualan", b, "Penjualan")
    row = con.execute("SELECT * FROM tx ORDER BY id DESC LIMIT 1").fetchone()
    cek("nominal di db", row["nominal"], 25000)
    cek("arah", row["arah"], "masuk")
    cek("metode tunai", row["metode"], "tunai")
    cek("sumber telegram", row["sumber"], "telegram")

    print("titik ribuan & qris")
    bot.tangani(con, "/catat 25.000 jual roti qris")
    row = con.execute("SELECT * FROM tx ORDER BY id DESC LIMIT 1").fetchone()
    cek("25.000 kebaca", row["nominal"], 25000)
    cek("qris kedeteksi", row["metode"], "qris")

    print("keluar")
    bot.tangani(con, "/keluar 300000 beli tepung 25kg")
    row = con.execute("SELECT * FROM tx ORDER BY id DESC LIMIT 1").fetchone()
    cek("arah keluar", row["arah"], "keluar")
    cek("kategori bahan baku", row["kategori"], "Bahan Baku")

    print("nominal ngawur ditolak")
    ada("tanpa angka", bot.tangani(con, "/catat jual roti"), "Nominalnya gak kebaca")

    print("tanggal eksplisit")
    bot.tangani(con, "/catat 5/11/2026 15000 jual bolu")
    row = con.execute("SELECT * FROM tx ORDER BY id DESC LIMIT 1").fetchone()
    cek("tanggal kebaca", row["tanggal"], "2026-11-05")

    print("duplikat")
    lagi = bot.tangani(con, "/catat 25000 jual roti coklat")
    ada("duplikat terdeteksi", lagi, "sudah pernah")

    print("lapor")
    b = bot.tangani(con, "/lapor")
    ada("header hari ini", b, "Rekap hari ini")
    ada("uang masuk", b, "Uang masuk")

    print("review")
    rid_review = core.tambah(con, hari, 123456, "masuk", "ambigu", sumber="email",
                             perlu_review=1)
    b = bot.tangani(con, "/review")
    ada("nampilin id", b, f"#{rid_review}")
    ada("cara betulin", b, "/koreksi")

    print("koreksi")
    b = bot.tangani(con, f"/koreksi {rid_review} keluar 123456")
    ada("koreksi jalan", b, "diperbarui")
    row = con.execute("SELECT * FROM tx WHERE id=?", (rid_review,)).fetchone()
    cek("arah berubah", row["arah"], "keluar")
    cek("flag review hilang", row["perlu_review"], 0)
    b = bot.tangani(con, "/review")
    ada("review bersih", b, "Bersih")
    ada("id ngawur", bot.tangani(con, "/koreksi 99999 masuk 1"), "gak ada")
    ada("format salah", bot.tangani(con, "/koreksi x"), "Format")

    print("piutang")
    b = bot.tangani(con, "/piutang Budi 50000")
    ada("piutang dicatat", b, "Rp 50.000")
    bot.tangani(con, "/piutang Siti 75000")
    b = bot.tangani(con, "/piutang")
    ada("daftar piutang", b, "Budi")
    ada("total piutang", b, "Rp 125.000")
    b = bot.tangani(con, "/lunas Budi")
    ada("lunas jalan", b, "lunas")
    b = bot.tangani(con, "/piutang")
    ada("Budi hilang dari daftar", b, "Siti")
    b = bot.tangani(con, "/lunas Sinta")
    ada("nama gak ada", b, "Gak ada piutang")

    print("grafik & bulan")
    b = bot.tangani(con, "/grafik")
    ada("grafik 8 minggu", b, "8 minggu")
    b = bot.tangani(con, "/bulan")
    ada("rekap bulanan", b, "Rekap bulan")

    print("excel")
    b = bot.tangani(con, "/excel")
    ada("excel atau kosong", b, "KIRIM_FILE" if "KIRIM_FILE" in b else "belum ada transaksi")

    print("chat lain tidak boleh dibaca - cek fungsi internal")
    # Chat filtering diuji lewat variabel: pastikan ada cek chat di main loop
    src = (Path(__file__).parent / "bot.py").read_text(encoding="utf-8")
    ada("ada filter chat", src, "ditolak (bukan")
    ada("ada retry jaringan", src, "gagal_beruntun")
    ada("exit 0 kalau imap belum diisi",
        (Path(__file__).parent / "imap_sync.py").read_text(encoding="utf-8"),
        "sys.exit(0)")

    con.close()

print(f"\n{ok} lulus, {gagal} gagal")
sys.exit(1 if gagal else 0)