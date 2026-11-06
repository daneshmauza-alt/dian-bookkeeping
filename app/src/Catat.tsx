import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Transaksi } from './lib'
import { api, rupiah } from './lib'

interface Props {
  /** Naikkan buat maksa daftar hari ini memuat ulang. */
  versi: number
  /** Dipanggil setelah transaksi berhasil disimpan. */
  onSukses: (msg: string) => void
  /** Pas gagal. */
  onGagal: (msg: string) => void
}

/** Preset cepat: yang paling sering Ibu jual. Sekali ketuk, langsung tercatat. */
const CEPAT: { label: string; nominal: number; ket: string }[] = [
  { label: 'Roti isi', nominal: 5000, ket: 'Roti isi' },
  { label: 'Roti tawar', nominal: 15000, ket: 'Roti tawar' },
  { label: 'Bolu', nominal: 25000, ket: 'Bolu' },
  { label: 'Kue basah', nominal: 3000, ket: 'Kue basah' },
  { label: 'Pesanan', nominal: 150000, ket: 'Pesanan' },
]

/** Kata kunci buat nebak kategori. Bikin Ibu gak perlu mikir. */
const SARAN: Record<string, string> = {
  tepung: 'Bahan Baku', mentega: 'Bahan Baku', margarin: 'Bahan Baku',
  gula: 'Bahan Baku', telur: 'Bahan Baku', ragi: 'Bahan Baku',
  coklat: 'Bahan Baku', keju: 'Bahan Baku', susu: 'Bahan Baku',
  gas: 'Operasional', listrik: 'Operasional', token: 'Operasional',
  bensin: 'Operasional', kemasan: 'Operasional', plastik: 'Operasional',
  sewa: 'Operasional', gaji: 'Operasional', iklan: 'Operasional',
}

export default function Catat({ versi, onSukses, onGagal }: Props) {
  const [arah, setArah] = useState<'masuk' | 'keluar'>('masuk')
  const [nominal, setNominal] = useState('')
  const [keterangan, setKeterangan] = useState('')
  const [metode, setMetode] = useState('tunai')
  const [tanggal, setTanggal] = useState(
    () => new Date().toLocaleDateString('sv-SE'),
  )
  const [simpan, setSimpan] = useState(false)
  const [hariIni, setHariIni] = useState<Transaksi[]>([])
  const inputNominal = useRef<HTMLInputElement>(null)
  const inputKet = useRef<HTMLInputElement>(null)

  // Ambil transaksi tanggal terpilih, buat panel "sudah kecatat".
  const muatHari = useCallback(async (tgl: string) => {
    try {
      const r = await api.transaksi({ awal: tgl, akhir: tgl })
      setHariIni(r.transaksi)
    } catch {
      /* panel ini cuma informasi; gagal ambil bukan alasan ganggu Ibu */
    }
  }, [])

  useEffect(() => {
    void muatHari(tanggal)
  }, [tanggal, versi, muatHari])

  // Fokus langsung ke nominal — itu satu-satunya yang wajib diisi.
  useEffect(() => {
    inputNominal.current?.focus()
  }, [])

  const kategoriTebak = useMemo(() => {
    if (arah === 'masuk') return 'Penjualan'
    const low = keterangan.toLowerCase()
    for (const [kata, kat] of Object.entries(SARAN)) {
      if (low.includes(kata)) return kat
    }
    return 'Lain-lain'
  }, [keterangan, arah])

  const nilaiNominal = Number(nominal.replace(/\D/g, '')) || 0

  async function kirim() {
    if (nilaiNominal <= 0) {
      onGagal('Nominalnya belum diisi.')
      inputNominal.current?.focus()
      return
    }
    setSimpan(true)
    try {
      const r = await api.catat({
        tanggal,
        nominal: nilaiNominal,
        arah,
        keterangan: keterangan.trim() || (arah === 'masuk' ? 'Penjualan' : 'Pengeluaran'),
        metode,
        kategori: kategoriTebak,
      })
      if (!r.ok) {
        onGagal(r.pesan ?? 'Gagal menyimpan.')
        return
      }
      onSukses(`${arah === 'masuk' ? 'Masuk' : 'Keluar'} ${rupiah(nilaiNominal)} tercatat.`)
      setNominal('')
      setKeterangan('')
      inputNominal.current?.focus()
    } catch (e) {
      onGagal(e instanceof Error ? e.message : 'Gagal menyimpan.')
    } finally {
      setSimpan(false)
    }
  }

  function ketukCepat(c: (typeof CEPAT)[number]) {
    setArah('masuk')
    setNominal(String(c.nominal))
    setKeterangan(c.ket)
    inputKet.current?.focus()
  }

  // Enter di keterangan = simpan. Biar gak perlu pindah ke mouse.
  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      void kirim()
    }
  }

  const masukHariIni = hariIni.filter((t) => t.arah === 'masuk')
  const totalHari = masukHariIni.reduce((s, t) => s + t.nominal, 0)

  return (
    <div className="flex flex-col gap-5">
      {/* ---- Pilih arah: dua tombol besar, bukan radio kecil ---- */}
      <div className="grid grid-cols-2 gap-3">
        {(['masuk', 'keluar'] as const).map((a) => {
          const aktif = arah === a
          const warnaAktif =
            a === 'masuk'
              ? 'border-[#3f5e3f] bg-[#e8f0e6] text-[#2c4429]'
              : 'border-[#9b2c2c] bg-[#f7e8e6] text-[#7a2222]'
          return (
            <button
              key={a}
              type="button"
              onClick={() => setArah(a)}
              aria-pressed={aktif}
              className={`tombol-cepat rounded-xl border-2 px-4 py-3 text-left transition-colors ${
                aktif
                  ? warnaAktif
                  : 'border-[#d9cdb9] bg-white/60 text-[#6b4a2f] hover:bg-white'
              }`}
            >
              <span className="block text-xs font-medium uppercase tracking-wide opacity-70">
                {a === 'masuk' ? 'Uang masuk' : 'Uang keluar'}
              </span>
              <span className="block text-base font-semibold">
                {a === 'masuk' ? 'Jualan / terima' : 'Belanja / bayar'}
              </span>
            </button>
          )
        })}
      </div>

      {/* ---- Form ---- */}
      <div className="rounded-xl border border-[#e2d8c6] bg-white/70 p-4">
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-[#6b4a2f]">Nominal</span>
            <div className="flex items-stretch gap-2">
              <span className="flex items-center rounded-lg border border-[#d9cdb9] bg-[#f5efe4] px-3 text-sm font-medium text-[#8a5a2b]">
                Rp
              </span>
              <input
                ref={inputNominal}
                inputMode="numeric"
                autoComplete="off"
                placeholder="25000"
                value={nominal}
                onChange={(e) => setNominal(e.target.value.replace(/[^\d]/g, ''))}
                onKeyDown={onKey}
                className="duit min-w-0 flex-1 rounded-lg border border-[#d9cdb9] bg-white px-3 py-2.5 text-lg font-semibold text-[#3d2b1f] outline-none transition-shadow placeholder:font-normal placeholder:text-[#bdb0a0] focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
              />
            </div>
            {nilaiNominal > 0 && (
              <span className="duit text-xs text-[#8a7a68]">
                = {rupiah(nilaiNominal)}
              </span>
            )}
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-[#6b4a2f]">
              Buat apa / dari apa
            </span>
            <input
              ref={inputKet}
              autoComplete="off"
              placeholder={
                arah === 'masuk' ? 'jual roti coklat' : 'beli tepung 25 kg'
              }
              value={keterangan}
              onChange={(e) => setKeterangan(e.target.value)}
              onKeyDown={onKey}
              className="rounded-lg border border-[#d9cdb9] bg-white px-3 py-2.5 text-sm text-[#3d2b1f] outline-none transition-shadow focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
            />
          </label>

          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-[#6b4a2f]">Cara bayar</span>
              <select
                value={metode}
                onChange={(e) => setMetode(e.target.value)}
                className="rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
              >
                <option value="tunai">Tunai</option>
                <option value="qris">QRIS</option>
                <option value="transfer">Transfer / Wondr</option>
              </select>
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-[#6b4a2f]">Tanggal</span>
              <input
                type="date"
                value={tanggal}
                onChange={(e) => setTanggal(e.target.value)}
                className="rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
              />
            </label>

            <div className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-[#6b4a2f]">Kategori</span>
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#cbbfa8] bg-[#f5efe4] px-3 py-2 text-sm font-medium text-[#6b4a2f]">
                {kategoriTebak}
                <span className="text-[10px] font-normal uppercase tracking-wide opacity-60">
                  otomatis
                </span>
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => void kirim()}
            disabled={simpan}
            className="tombol-cepat w-full rounded-xl border-2 border-[#6b4a2f] bg-[#6b4a2f] px-5 text-base font-semibold text-[#faf6ef] transition-colors hover:bg-[#57391f] disabled:opacity-50"
          >
            {simpan ? 'Menyimpan…' : 'Simpan'}
          </button>
          <p className="-mt-2 text-center text-xs text-[#8a7a68]">
            Tekan Enter buat simpan juga.
          </p>
        </div>
      </div>

      {/* ---- Preset cepat ---- */}
      <div>
        <p className="mb-2 text-sm font-medium text-[#6b4a2f]">
          Serba sekali ketuk
        </p>
        <div className="flex flex-wrap gap-2">
          {CEPAT.map((c) => (
            <button
              key={c.label}
              type="button"
              onClick={() => ketukCepat(c)}
              className="rounded-lg border border-[#d9cdb9] bg-white/70 px-3 py-2 text-left text-sm transition-colors hover:border-[#8a5a2b] hover:bg-white"
            >
              <span className="block font-medium text-[#3d2b1f]">{c.label}</span>
              <span className="duit block text-xs text-[#8a7a68]">
                {rupiah(c.nominal)}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* ---- Sudah kecatat hari ini ---- */}
      <div className="rounded-xl border border-[#e2d8c6] bg-[#f5efe4]/60 p-4">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-sm font-medium text-[#6b4a2f]">
            Sudah masuk hari ini
          </p>
          <p className="duit text-lg font-semibold text-[#3f5e3f]">
            {rupiah(totalHari)}
          </p>
        </div>
        <p className="text-xs text-[#8a7a68]">
          {masukHariIni.length} transaksi tercatat pada tanggal terpilih
        </p>
        {masukHariIni.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1.5 border-t border-[#e2d8c6] pt-3">
            {masukHariIni
              .slice(-6)
              .reverse()
              .map((t) => (
                <li
                  key={t.id}
                  className="flex items-baseline justify-between gap-3 text-sm"
                >
                  <span className="min-w-0 flex-1 truncate text-[#5a4a3c]">
                    {t.keterangan || 'Penjualan'}
                  </span>
                  <span className="duit shrink-0 text-[#3d2b1f]">
                    {rupiah(t.nominal)}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </div>

      <p className="text-center text-xs text-[#a0937f]">
        Notifikasi Wondr cuma ditulis buat transaksi Rp 500.000 ke atas, jadi
        jualan harian tetap dicatat dari sini.
      </p>
    </div>
  )
}
