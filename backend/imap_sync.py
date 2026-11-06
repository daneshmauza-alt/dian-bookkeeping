"""Sync email Wondr dari IMAP ke DB. Jalan tiap 15 menit lewat Task Scheduler.

Kalau kredensial belum diisi, keluar dengan tenang (exit 0) tanpa error —
biar Task Scheduler gak spam notifikasi gagal.
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
import sys
from datetime import date
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core

PENGIRIM_WONDR = ("wondr", "bni", "notifikasi bni", "bank bni")


def _baca_env() -> dict:
    """Baca .env sederhana. Gak pakai pustaka tambahan."""
    env = {}
    f = core.ROOT / ".env"
    if f.exists():
        for baris in f.read_text(encoding="utf-8").splitlines():
            baris = baris.strip()
            if not baris or baris.startswith("#") or "=" not in baris:
                continue
            k, v = baris.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASS", "IMAP_FOLDER",
              "TG_TOKEN", "TG_CHAT"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def _teks_pesan(msg: email.message.Message) -> str:
    """Ambil body sebagai teks biasa. HTML dibersihkan kalau gak ada teks."""
    bagian_teks, bagian_html = [], []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        tipe = part.get_content_type()
        if tipe not in ("text/plain", "text/html"):
            continue
        try:
            isi = part.get_payload(decode=True) or b""
            cs = part.get_content_charset() or "utf-8"
            teks = isi.decode(cs, errors="replace")
        except Exception:
            continue
        (bagian_teks if tipe == "text/plain" else bagian_html).append(teks)

    if bagian_teks:
        return "\n".join(bagian_teks)
    html = "\n".join(bagian_html)
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]{2,}", " ", html).strip()


def _header(msg, nama: str) -> str:
    raw = msg.get(nama, "")
    if not raw:
        return ""
    out = []
    for teks, enc in decode_header(raw):
        if isinstance(teks, bytes):
            out.append(teks.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(teks)
    return "".join(out)


def sync(verbose: bool = True) -> dict:
    env = _baca_env()
    kurang = [k for k in ("IMAP_HOST", "IMAP_USER", "IMAP_PASS") if not env.get(k)]
    if kurang:
        if verbose:
            print(f"IMAP belum diisi ({', '.join(kurang)}). Lewati sync.")
        return {"status": "belum_dikonfigurasi", "kurang": kurang}

    folder = env.get("IMAP_FOLDER", "INBOX")
    host = env["IMAP_HOST"]
    port = int(env.get("IMAP_PORT", "993"))

    stat = {"diperiksa": 0, "masuk": 0, "duplikat": 0, "review": 0, "tolak": 0}

    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(env["IMAP_USER"], env["IMAP_PASS"])
    except Exception as e:
        print(f"IMAP gagal konek: {type(e).__name__}: {e}", file=sys.stderr)
        return {"status": "gagal_konek", "error": str(e)}

    try:
        imap.select(folder, readonly=True)
        # Cari email 30 hari terakhir dari pengirim bank. Server yang filter.
        kriteria = ['(SINCE "{}")'.format(
            (date.today().replace(day=1)).strftime("%d-%b-%Y"))]
        ok, data = imap.search(None, *kriteria)
        if ok != "OK":
            return {"status": "gagal_search", "error": str(data)}

        ids = (data[0] or b"").split()
        con = core.connect()
        for num in ids:
            ok, parts = imap.fetch(num, "(RFC822)")
            if ok != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            msg = email.message_from_bytes(parts[0][1])
            dari = _header(msg, "From").lower()
            stat["diperiksa"] += 1

            if not any(p in dari for p in PENGIRIM_WONDR):
                stat["tolak"] += 1
                continue

            subject = _header(msg, "Subject")
            body = _teks_pesan(msg)
            mid = _header(msg, "Message-ID") or _header(msg, "Message-Id")

            terima = None
            try:
                terima = parsedate_to_datetime(
                    _header(msg, "Date")).date().isoformat()
            except Exception:
                pass

            hasil = core.impor_email(con, subject, body, mid, terima)
            stat[hasil["status"]] = stat.get(hasil["status"], 0) + 1
            if verbose:
                print(f"  [{hasil['status']}] {subject[:60]} "
                      f"-> {core.rupiah(hasil.get('nominal') or 0)}")
        con.close()
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    stat["status"] = "ok"
    if verbose:
        print(json.dumps(stat, ensure_ascii=False, indent=2))
    return stat


if __name__ == "__main__":
    hasil = sync()
    # Exit 0 selalu: kalau IMAP belum diisi itu kondisi normal, bukan error.
    sys.exit(0)