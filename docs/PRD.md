# PRD — Diana Bookkeeping

Aplikasi pembukuan otomatis untuk usaha roti & kue DIAN SNACK (Kediri).

Status: v1 build. Pemilik: Ibu (operator non-teknis). Builder: HAI HELO.
Tanggal: 6 November 2026.

---

## 1. Masalah

Ibu jualan roti & kue. Uang masuk lewat beberapa jalur: tunai, QRIS, dan transfer
bank Wondr by BNI. Yang jadi masalah bukan kurang transaksi, tapi **catatannya
kacau**. Rekap cuma ada kalau ada waktu, dan waktu itu hampir gak pernah ada pas
jam sibuk jualan.

Akibatnya:

- Gak tahu omzet minggu ini berapa, sampai akhir bulan baru ngeh.
- Gak bisa hitung laba kotor, karena pengeluaran bahan baku (tepung, mentega,
  gula, telur) dicatat terpisah atau gak dicatat sama sekali.
- Kalau ada yang tanya "minggu lalu dapat berapa?", jawabannya kira-kira.
- Kalau mau ajukan pinjaman atau KUR, gak ada bukti pemasukan yang rapi.

## 2. Tujuan

Setiap transaksi masuk **otomatis kecatet tanpa Ibu ngetik apa pun**. Sekali
seminggu, rekapnya jadi file Excel dan dikirim ke Telegram HAI HELO.

Yang **tidak** jadi tujuan v1:

- Bukan pengganti pembukuan pajak.
- Bukan aplikasi yang butuh Ibu buka tiap hari.
- Bukan sistem multi-pegawai.

## 3. Batasan yang sudah disepakati

| Hal | Keputusan | Alasan |
|---|---|---|
| Sumber data utama | Input cepat 2 ketukan (tunai & QRIS) | Notifikasi Wondr punya batas minimum, lihat di bawah |
| Sumber data sekunder | Email notifikasi Wondr by BNI | Nangkep transfer besar otomatis, tanpa akses HP |
| Platform HP | Android | Wondr kirim email juga, jadi Android bukan hambatan |
| E-wallet | Wondr dulu, sisanya nyusul | Hindari over-build |
| Front end | HeroUI v3 + React 19 | Standar yang berlaku di mesin ini |
| Jalan di mana | Lokal dulu | Gratis, data gak keluar dari rumah |

### Temuan yang mengubah desain: notifikasi Wondr ada batas nominal

Balasan resmi BNI di ulasan Google Play menyatakan notifikasi transaksi hanya
dikirim untuk transaksi **minimal Rp 500.000**. Harga roti & kue ada di kisaran
Rp 2.000 sampai Rp 100.000.

Artinya: **notifikasi Wondr tidak bisa jadi jalur utama.** Kalau kita bangun
sistem yang cuma bergantung ke situ, 95% penjualan Ibu tidak akan kecatat dan
seluruh aplikasi ini jadi bohong.

Karena itu arsitekturnya dibalik:

- **Jalur utama** — pencatatan cepat 2 ketukan dari HP/laptop. Ini yang
  menangkap penjualan harian.
- **Jalur sekunder** — email Wondr, buat transfer besar yang memang bikin email.
- **Dua jalur dilebur** dengan pengecekan duplikat, jadi satu transaksi tetap
  satu baris walaupun ketangkep dua cara.

Ini justru kabar baik. Pencatatan manual yang dibuat gampang jauh lebih akurat
daripada otomatisasi yang bolong-bolong.

**Yang tidak mungkin, dan harus jujur sejak awal:** notifikasi push Android
**tidak bisa** dibaca aplikasi web/pihak ketiga. Gak ada API-nya. Kalau ada yang
bilang bisa tanpa root atau tanpa `NotificationListenerService`, itu bohong.
Karena Wondr mengirim salinan ke email, kita pakai jalur email. Ini jalur resmi
dan stabil.

## 4. Alur pengguna

```
Notif Wondr masuk HP Ibu
        │
        └─► Wondr juga kirim email ke alamat Ibu
                    │
                    └─► IMAP inbox dibaca tiap 15 menit
                                │
                                └─► Parser ambil: tanggal, nominal, arah (masuk/keluar), keterangan
                                            │
                                            └─► Masuk SQLite (dedupe by message-id)
                                                        │
                                                        ├─► Bot Telegram: /lapor → rekap hari ini
                                                        │
                                                        └─► Tiap Minggu 20:00 → Excel + kirim ke Telegram
```

## 5. Fitur

### Wajib (v1)

1. **Auto-import** — baca email Wondr via IMAP, parse transaksi, simpan.
   Idempotent: satu email = satu baris, walau dibaca berkali-kali.
2. **Rekap mingguan otomatis** — tiap Minggu 20:00, generate `.xlsx` berisi
   ringkasan + detail, kirim ke Telegram.
3. **Bot Telegram** — tanya lewat chat, gak perlu buka aplikasi.
4. **Input manual** — buat yang tunai & QRIS (gak lewat Wondr).
5. **Dashboard** — lihat, filter, koreksi.

### Tambahan yang layak (karena murah, tapi berguna)

6. **Kategori otomatis** — tebak dari kata kunci: `tepung` → Bahan Baku,
   `listrik` → Operasional. Aturan bisa diedit.
7. **Laba kotor** — pemasukan dikurangi pengeluaran bahan baku, per periode.
8. **Piutang** — pelanggan langganan yang belum bayar. Roti & kue banyak yang
   ngutang mingguan; tanpa ini omzet bohong.
9. **Grafik tren** — 12 minggu terakhir, di dashboard.

### Ditolak (dan alasannya)

- Login multi-user, role & permission → satu orang pakai, mubazir.
- Mode offline & sinkronisasi → datanya di satu laptop.
- Aplikasi Android native → email sudah cukup; nambah APK = nambah masalah
  update, izin, sideload, dan Play Store policy.
- Notifikasi stok real-time → gak ada data stok; bikin sekarang = fitur bohong.

## 6. Aturan parsing (kontrak yang harus benar)

Contoh email Wondr (format aktual dikonfirmasi saat setup):

```
Nominal   : IDR 250.000
Tanggal   : 06 Nov 2026 14:32
Jenis     : KREDIT
Berita    : Transfer dari HAI HELO
```

Aturan:

- Nominal wajib ketemu. Gak ketemu → baris masuk `perlu_review`, bukan dibuang.
- Arah: `KREDIT`/`CR`/`masuk`/`terima` → pemasukan. `DEBIT`/`DB`/`keluar`/
  `bayar`/`transfer ke` → pengeluaran.
- Format tanggal Indonesia (`06 Nov 2026`) dan `06/11/2026` dua-duanya harus
  kebaca.
- Dedupe pakai `Message-ID` email. Kalau kosong, pakai hash dari
  `tanggal + nominal + berita`.
- **Kalau parser ragu, tandai review. Jangan pernah nebak nominal.**
  Angka yang salah lebih bahaya dari angka yang kosong.

## 7. Kriteria sukses

v1 dianggap jalan kalau semua ini terbukti:

- [ ] Satu email Wondr asli masuk dan jadi baris di DB, nominal cocok.
- [ ] Email yang sama dibaca dua kali tetap satu baris.
- [ ] `/lapor` di Telegram balas rekap hari ini dengan angka yang cocok DB.
- [ ] Rekap mingguan generate `.xlsx` yang bisa dibuka Excel, angka cocok DB.
- [ ] File Excel kekirim ke Telegram.
- [ ] Dashboard bisa filter tanggal dan koreksi satu baris.
- [ ] `npx tsc -b` dan `npm run build` bersih.

## 8. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Format email Wondr berubah | Parser gagal senyap | Baris gagal masuk `perlu_review`, dashboard nampilin hitungannya |
| Email Wondr gak ada / cuma push notif | Seluruh alur mati | Diverifikasi di Hari 1 sebelum bangun sisanya. Fallback: input manual + forward screenshot |
| Ibu males input tunai | Data cuma separuh | Input manual dibuat 2 ketukan; tunai bisa dicatat harian sekali jalan |
| Kredensial email bocor | Serius | Password app disimpan di file `.env` lokal, gak pernah masuk git, gak pernah ditulis ke log |

## 9. Yang sengaja ditunda

Cloud/VPS 24 jam (butuh biaya + Ibu gak butuh real-time), kategori berbasis ML,
notifikasi stok, multi-cabang, integrasi QRIS langsung.
