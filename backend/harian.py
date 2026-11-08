"""Tugas harian PythonAnywhere: kirim rekap mingguan tiap Senin.

Pasang di tab Tasks (Scheduled task), jadwal harian:
    python3 /home/<username>/dian-bookkeeping/backend/harian.py

Kenapa dibungkus: core.py `kirim` selalu kirim rekap. Dijadwalkan harian
tanpa bungkusan = ibu dapat rekap tiap hari. Ini ngecek hari dulu.
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parent


def main() -> int:
    if date.today().weekday() != 0:
        print("Bukan Senin, lewati.")
        return 0
    r = subprocess.run([sys.executable, str(BACKEND / "core.py"), "kirim"],
                       cwd=str(BACKEND.parent))
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
