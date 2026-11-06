"""Bot Telegram Diana Bookkeeping — polling, tanpa webhook, tanpa framework.

Perintah:
  /start            cara pakai
  /catat 25000 jual roti      -> pemasukan tunai
  /keluar 300000 beli tepung  -> pengeluaran
  /lapor                      -> rekap hari ini
  /minggu                     -> rekap minggu lalu
  /excel                      -> kirim file Excel minggu lalu
  /piutang Budi 50000         -> catat piutang
  /lunas Budi                 -> tandai lunas
  /review                     -> baris yang perlu dicek
  /koreksi <id> masuk|keluar <nominal>

Jalan: python backend/bot.py
"""

from __future__ import annotations

import calendar
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
import imap_sync

import requests

PANDUAN = """DIAN SNACK — cara pakai

Catat penjualan (paling sering):
  /catat 25000 jual roti coklat

Catat pengeluaran:
  /keluar 300000 beli tepung 25kg

Lihat rekap:
  /lapor          rekap hari ini
  /minggu         rekap minggu lalu
  /excel          file Excel minggu lalu

Piutang:
  /piutang Budi 50000
  /lunas Budi

Kalau ada yang salah:
  /review         baris yang perlu dicek
  /koreksi 12 masuk 45000

Total bisa ditulis 25000 atau 25.000, dua-duanya kebaca."""


# ---------------------------------------------------------------- util

def ambil_nominal(teks: str) -> tuple[int | None, str]:
    """Ambil angka pertama, balikin (nominal, sisa teks)."""
    m = re.search(r"\d[\d.,]*", teks)
    if not m:
        return None, teks.strip()
    nilai = core._bersih_nominal(m.group(0))
    sisa = (teks[:m.start()] + " " + teks[m.end():]).strip()
    return nilai, re.sub(r"\s{2,}", " ", sisa)


def parse_tanggal_awal(teks: str) -> tuple[str, str]:
    """Kalau teks mulai dengan tanggal, pakai itu. Balikin (iso, sisa)."""
    m = re.match(r"^(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\s+", teks)
    if m:
        iso = core.parse_tanggal(m.group(1))
        if iso:
            return iso, teks[m.end():]
    iso = core.parse_tanggal(teks)
    if iso:
        return iso, ""
    return date.today().isoformat(), teks


def potong(teks: str, n: int = 4000) -> str:
    return teks if len(teks) <= n else teks[:n - 20] + "\n...(dipotong)"


# ---------------------------------------------------------------- perintah

def cmd_catat(con, arah: str, arg: str) -> str:
    if not arg:
        return ("Format: /catat 25000 jual roti\n"
                "Nominal di depan, keterangan setelahnya.")
    tanggal, sisa = parse_tanggal_awal(arg)
    nominal, ket = ambil_nominal(sisa)
    if not nominal:
        return "Nominalnya gak kebaca. Contoh: /catat 25000 jual roti"
    metode = "tunai"
    if "qris" in ket.lower():
        metode = "qris"
    elif "transfer" in ket.lower():
        metode = "transfer"
    rid = core.tambah(con, tanggal, nominal, arah,
                      ket or ("Penjualan" if arah == "masuk" else "Pengeluaran"),
                      sumber="telegram", metode=metode)
    if not rid:
        return "Transaksi ini kayaknya sudah pernah dicatat."
    kelas = "MASUK" if arah == "masuk" else "KELUAR"
    kat = con.execute("SELECT kategori FROM tx WHERE id=?", (rid,)).fetchone()["kategori"]
    return (f"Tercatat #{rid}\n{kelas} {core.rupiah(nominal)}\n"
            f"{ket or '-'}\nKategori: {kat} ({tanggal})")


def cmd_koreksi(con, arg: str) -> str:
    bagian = arg.split()
    if len(bagian) < 2:
        return "Format: /koreksi 12 masuk 45000"
    try:
        rid = int(bagian[0])
    except ValueError:
        return "ID harus angka. Lihat /review buat daftar ID."
    row = con.execute("SELECT * FROM tx WHERE id=?", (rid,)).fetchone()
    if not row:
        return f"Transaksi #{rid} gak ada."

    ubah = {}
    for b in bagian[1:]:
        if b.lower() in ("masuk", "keluar"):
            ubah["arah"] = b.lower()
        elif re.fullmatch(r"\d[\d.,]*", b):
            n = core._bersih_nominal(b)
            if n:
                ubah["nominal"] = n
        else:
            ubah["keterangan"] = " ".join(bagian[1:])
            break
    if not ubah:
        return "Gak ada yang berubah. Contoh: /koreksi 12 masuk 45000"

    setel = ", ".join(f"{k}=?" for k in ubah)
    con.execute(f"UPDATE tx SET {setel}, perlu_review=0 WHERE id=?",
                (*ubah.values(), rid))
    con.commit()
    r = con.execute("SELECT * FROM tx WHERE id=?", (rid,)).fetchone()
    return (f"#{rid} diperbarui\n{r['arah'].upper()} "
            f"{core.rupiah(r['nominal'])} — {r['keterangan']}")


def cmd_review(con) -> str:
    rows = con.execute(
        "SELECT * FROM tx WHERE perlu_review=1 ORDER BY tanggal DESC LIMIT 20"
    ).fetchall()
    if not rows:
        return "Bersih. Gak ada baris yang perlu dicek."
    baris = [f"{len(rows)} baris perlu dicek:", ""]
    for r in rows:
        baris.append(f"#{r['id']} {r['tanggal']} {core.rupiah(r['nominal'])} "
                     f"{r['arah']}\n  {r['keterangan'][:60]}")
    baris += ["", "Betulkan dengan: /koreksi <id> masuk|keluar <nominal>"]
    return "\n".join(baris)


def cmd_piutang(con, arg: str) -> str:
    bagian = arg.split()
    if len(bagian) < 2:
        return "Format: /piutang Budi 50000"
    nama = bagian[0]
    nominal, _ = ambil_nominal(" ".join(bagian[1:]))
    if not nominal:
        return "Nominal gak kebaca. Contoh: /piutang Budi 50000"
    con.execute("INSERT INTO piutang (nama, nominal, tanggal) VALUES (?,?,?)",
                (nama, nominal, date.today().isoformat()))
    con.commit()
    total = con.execute(
        "SELECT COALESCE(SUM(nominal),0) t FROM piutang WHERE lunas=0"
    ).fetchone()["t"]
    return (f"Piutang {nama} {core.rupiah(nominal)} dicatat.\n"
            f"Total belum lunas semua: {core.rupiah(total)}")


def cmd_lunas(con, arg: str) -> str:
    nama = arg.strip()
    if not nama:
        return "Format: /lunas Budi"
    cur = con.execute(
        "UPDATE piutang SET lunas=1 WHERE lunas=0 AND nama LIKE ?",
        (f"%{nama}%",))
    con.commit()
    if not cur.rowcount:
        return f"Gak ada piutang belum lunas atas nama {nama}."
    sisa = con.execute(
        "SELECT COALESCE(SUM(nominal),0) t FROM piutang WHERE lunas=0"
    ).fetchone()["t"]
    return (f"{cur.rowcount} piutang {nama} ditandai lunas.\n"
            f"Sisa belum lunas: {core.rupiah(sisa)}")


def cmd_piutang_list(con) -> str:
    rows = con.execute(
        "SELECT nama, SUM(nominal) t FROM piutang WHERE lunas=0 "
        "GROUP BY nama ORDER BY t DESC").fetchall()
    if not rows:
        return "Gak ada piutang belum lunas."
    baris = ["Piutang belum lunas:"]
    total = 0
    for r in rows:
        baris.append(f"  {r['nama']}: {core.rupiah(r['t'])}")
        total += r["t"]
    baris += ["", f"Total: {core.rupiah(total)}"]
    return "\n".join(baris)


def cmd_grafik(con) -> str:
    """Tren 8 minggu terakhir, teks bar. Gak butuh gambar."""
    baris = ["Omzet 8 minggu terakhir:", ""]
    hari_ini = date.today()
    senin_ini = hari_ini - timedelta(days=hari_ini.weekday())
    data = []
    for i in range(8, 0, -1):
        awal = senin_ini - timedelta(days=7 * i)
        akhir = awal + timedelta(days=6)
        r = core.ringkas(con, awal.isoformat(), akhir.isoformat())
        data.append((awal, akhir, r["masuk"]))
    puncak = max((d[2] for d in data), default=0) or 1
    for awal, akhir, masuk in data:
        panjang = int(round(masuk / puncak * 20))
        bar = "#" * panjang or "."
        baris.append(f"{awal.day:2d}/{awal.month:02d} {bar} {core.rupiah(masuk)}")
    return "\n".join(baris)


def cmd_bulan(con) -> str:
    hari_ini = date.today()
    awal = hari_ini.replace(day=1).isoformat()
    akhir = hari_ini.replace(
        day=calendar.monthrange(hari_ini.year, hari_ini.month)[1]).isoformat()
    return core.laporan_teks(con, awal, akhir,
                             f"Rekap bulan {core.nama_bulan(hari_ini.month)} "
                             f"{hari_ini.year}")


# ---------------------------------------------------------------- dispatch

def tangani(con, teks: str) -> str:
    teks = teks.strip()
    if not teks.startswith("/"):
        return ("Aku cuma ngerti perintah. Ketik /start buat lihat daftarnya.\n"
                "Yang paling sering dipakai: /catat 25000 jual roti")

    perintah, _, arg = teks[1:].partition(" ")
    perintah = perintah.split("@")[0].lower()  # buang @namabot
    arg = arg.strip()

    if perintah in ("start", "help", "bantuan"):
        return PANDUAN
    if perintah == "catat":
        return cmd_catat(con, "masuk", arg)
    if perintah in ("keluar", "beli", "belanja"):
        return cmd_catat(con, "keluar", arg)
    if perintah == "jual":
        return cmd_catat(con, "masuk", arg)
    if perintah in ("lapor", "hari"):
        return core.laporan_teks(con, date.today().isoformat(),
                                 date.today().isoformat(),
                                 "Rekap hari ini")
    if perintah == "minggu":
        a, b, lbl = core.minggu_lalu()
        return core.laporan_teks(con, a, b, lbl)
    if perintah == "bulan":
        return cmd_bulan(con)
    if perintah == "grafik":
        return cmd_grafik(con)
    if perintah == "excel":
        a, b, _ = core.minggu_lalu()
        if not core.ringkas(con, a, b)["jumlah_transaksi"]:
            return "Minggu lalu belum ada transaksi, jadi belum ada yang direkap."
        xl = core.tulis_excel(con, a, b)
        return f"KIRIM_FILE:{xl}"
    if perintah == "review":
        return cmd_review(con)
    if perintah == "koreksi":
        return cmd_koreksi(con, arg)
    if perintah == "piutang":
        return cmd_piutang_list(con) if not arg else cmd_piutang(con, arg)
    if perintah == "lunas":
        return cmd_lunas(con, arg)
    return "Perintah gak dikenal. Ketik /start."


# ---------------------------------------------------------------- loop

def main() -> int:
    env = imap_sync._baca_env()
    token, chat = env.get("TG_TOKEN"), env.get("TG_CHAT")
    if not token:
        print("TG_TOKEN belum diisi di .env — bot tidak bisa jalan.", file=sys.stderr)
        print("Isi dulu di ~/dian-bookkeeping/.env", file=sys.stderr)
        return 1

    con = core.connect()
    print("Bot jalan. Tekan Ctrl+C buat berhenti.")
    offset = None
    gagal_beruntun = 0

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"timeout": 30, "offset": offset,
                        "allowed_updates": '["message"]'},
                timeout=45)
            data = r.json()
            if not data.get("ok"):
                print(f"Telegram error: {data}", file=sys.stderr)
                time.sleep(5)
                continue
            gagal_beruntun = 0

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                teks = (msg.get("text") or "").strip()
                masuk_chat = str((msg.get("chat") or {}).get("id", ""))
                if not teks:
                    continue
                if chat and masuk_chat != str(chat):
                    print(f"chat {masuk_chat} ditolak (bukan {chat})")
                    continue
                try:
                    balas = tangani(con, teks)
                except Exception as e:
                    balas = f"Ada error waktu memproses: {type(e).__name__}: {e}"
                    print(f"ERROR saat tangani {teks!r}: {e}", file=sys.stderr)

                if balas.startswith("KIRIM_FILE:"):
                    path = Path(balas.split(":", 1)[1])
                    core.tg_send_doc(token, masuk_chat, path,
                                     "Rekap minggu lalu")
                else:
                    core.tg_send(token, masuk_chat, potong(balas))

        except requests.exceptions.RequestException as e:
            gagal_beruntun += 1
            print(f"Jaringan bermasalah ({gagal_beruntun}x): {e}", file=sys.stderr)
            time.sleep(min(5 * gagal_beruntun, 60))
        except KeyboardInterrupt:
            print("\nBerhenti.")
            break
        except Exception as e:
            print(f"Error tak terduga: {type(e).__name__}: {e}", file=sys.stderr)
            time.sleep(5)
    return 0


if __name__ == "__main__":
    sys.exit(main())