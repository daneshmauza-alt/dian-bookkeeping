import { useEffect, useMemo, useState } from 'react'
import type { Transaksi } from './lib'
import { api, parseDuit, rupiah, tanggalPendek } from './lib'

interface Props {
  awal: string
  akhir: string
  onPesan: (t: 'ok' | 'gagal', msg: string) => void
  /** Penanda dari luar biar tabel ikut refresh setelah catat baru. */
  versi: number
}

const KATEGORI = [
  'Penjualan', 'Bahan Baku', 'Operasional', 'Gaji', 'Lain-lain',
]

export default function Buku({ awal, akhir, onPesan, versi }: Props) {
  const [daftar, setDaftar] = useState<Transaksi[]>([])
  const [memuat, setMemuat] = useState(true)
  const [cari, setCari] = useState('')
  const [filterKat, setFilterKat] = useState('')
  const [filterArah, setFilterArah] = useState<'' | 'masuk' | 'keluar'>('')
  const [sunting, setSunting] = useState<Transaksi | null>(null)
  const [hapusId, setHapusId] = useState<number | null>(null)

  async function muat() {
    setMemuat(true)
    try {
      const r = await api.transaksi({ awal, akhir })
      setDaftar(r.transaksi)
    } catch (e) {
      onPesan('gagal', e instanceof Error ? e.message : 'Gagal memuat buku.')
    } finally {
      setMemuat(false)
    }
  }

  useEffect(() => {
    void muat()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [awal, akhir, versi])

  const saring = useMemo(() => {
    const q = cari.trim().toLowerCase()
    return daftar.filter((t) => {
      if (filterKat && t.kategori !== filterKat) return false
      if (filterArah && t.arah !== filterArah) return false
      if (q && !(`${t.keterangan} ${t.kategori} ${t.metode}`.toLowerCase().includes(q)))
        return false
      return true
    })
  }, [daftar, cari, filterKat, filterArah])

  const total = useMemo(() => {
    let masuk = 0
    let keluar = 0
    for (const t of saring) {
      if (t.arah === 'masuk') masuk += t.nominal
      else keluar += t.nominal
    }
    return { masuk, keluar }
  }, [saring])

  async function simpanSunting() {
    if (!sunting) return
    try {
      const r = await api.koreksi({
        id: sunting.id,
        tanggal: sunting.tanggal,
        nominal: sunting.nominal,
        arah: sunting.arah,
        keterangan: sunting.keterangan,
        kategori: sunting.kategori,
      })
      if (!r.ok) {
        onPesan('gagal', r.pesan ?? 'Gagal menyimpan.')
        return
      }
      onPesan('ok', `Transaksi #${sunting.id} diperbarui.`)
      setSunting(null)
      await muat()
    } catch (e) {
      onPesan('gagal', e instanceof Error ? e.message : 'Gagal menyimpan.')
    }
  }

  async function konfirmasiHapus() {
    if (hapusId === null) return
    try {
      const r = await api.hapus(hapusId)
      if (!r.ok) {
        onPesan('gagal', r.pesan ?? 'Gagal menghapus.')
        return
      }
      onPesan('ok', r.pesan ?? 'Terhapus.')
      setHapusId(null)
      await muat()
    } catch (e) {
      onPesan('gagal', e instanceof Error ? e.message : 'Gagal menghapus.')
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ---- Saringan ---- */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          placeholder="Cari keterangan…"
          value={cari}
          onChange={(e) => setCari(e.target.value)}
          className="min-w-40 flex-1 rounded-lg border border-[#d9cdb9] bg-white/70 px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
        />
        <select
          value={filterArah}
          onChange={(e) => setFilterArah(e.target.value as '' | 'masuk' | 'keluar')}
          aria-label="Saring arah"
          className="rounded-lg border border-[#d9cdb9] bg-white/70 px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b]"
        >
          <option value="">Masuk & keluar</option>
          <option value="masuk">Masuk saja</option>
          <option value="keluar">Keluar saja</option>
        </select>
        <select
          value={filterKat}
          onChange={(e) => setFilterKat(e.target.value)}
          aria-label="Saring kategori"
          className="rounded-lg border border-[#d9cdb9] bg-white/70 px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b]"
        >
          <option value="">Semua kategori</option>
          {KATEGORI.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 text-sm">
        <span className="text-[#8a7a68]">
          {saring.length} dari {daftar.length} baris
        </span>
        <span className="duit text-[#2c4429]">masuk {rupiah(total.masuk)}</span>
        <span className="duit text-[#7a2222]">keluar {rupiah(total.keluar)}</span>
        <span className="duit font-medium text-[#3d2b1f]">
          sisa {rupiah(total.masuk - total.keluar)}
        </span>
      </div>

      {/* ---- Tabel ---- */}
      {memuat ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded-lg border border-[#e2d8c6] bg-white/50"
            />
          ))}
        </div>
      ) : saring.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#d9cdb9] bg-white/40 px-4 py-12 text-center">
          <p className="text-sm font-medium text-[#6b4a2f]">
            {daftar.length === 0
              ? 'Belum ada transaksi di periode ini'
              : 'Gak ada baris yang cocok dengan saringan'}
          </p>
          <p className="mt-1 text-xs text-[#8a7a68]">
            {daftar.length === 0
              ? 'Catat yang pertama dari tab Catat.'
              : 'Coba kosongkan kata pencarian atau saringan.'}
          </p>
        </div>
      ) : (
        <>
          {/* Desktop: tabel penuh */}
          <div className="hidden overflow-hidden rounded-xl border border-[#e2d8c6] bg-white/70 md:block">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-[#f0e8db] text-left text-xs uppercase tracking-wide text-[#6b4a2f]">
                  <th className="px-3 py-2.5 font-medium">Tanggal</th>
                  <th className="px-3 py-2.5 font-medium">Keterangan</th>
                  <th className="px-3 py-2.5 font-medium">Kategori</th>
                  <th className="px-3 py-2.5 text-right font-medium">Masuk</th>
                  <th className="px-3 py-2.5 text-right font-medium">Keluar</th>
                  <th className="px-3 py-2.5 font-medium">Cara</th>
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {saring.map((t) => (
                  <tr
                    key={t.id}
                    className={`border-t border-[#eee5d6] transition-colors hover:bg-[#faf6ef] ${
                      t.perlu_review ? 'bg-[#fbf3e4]' : ''
                    }`}
                  >
                    <td className="whitespace-nowrap px-3 py-2.5 text-[#5a4a3c]">
                      {tanggalPendek(t.tanggal)}
                    </td>
                    <td className="max-w-64 px-3 py-2.5">
                      <span className="block truncate text-[#3d2b1f]">
                        {t.keterangan || '—'}
                      </span>
                      {t.perlu_review === 1 && (
                        <span className="mt-0.5 inline-block rounded bg-[#8a5a2b] px-1.5 py-0.5 text-[10px] font-medium text-[#faf6ef]">
                          perlu dicek
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-[#6b4a2f]">{t.kategori}</td>
                    <td className="duit px-3 py-2.5 text-right text-[#2c4429]">
                      {t.arah === 'masuk' ? rupiah(t.nominal) : ''}
                    </td>
                    <td className="duit px-3 py-2.5 text-right text-[#7a2222]">
                      {t.arah === 'keluar' ? rupiah(t.nominal) : ''}
                    </td>
                    <td className="px-3 py-2.5 text-xs capitalize text-[#8a7a68]">
                      {t.metode}
                      {t.sumber === 'email' && (
                        <span className="ml-1 rounded bg-[#e8eef5] px-1 py-0.5 text-[10px] text-[#3f5e3f]">
                          email
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={() => setSunting({ ...t })}
                        className="rounded px-2 py-1 text-xs font-medium text-[#6b4a2f] underline-offset-2 hover:underline"
                      >
                        Betulin
                      </button>
                      <button
                        type="button"
                        onClick={() => setHapusId(t.id)}
                        className="rounded px-2 py-1 text-xs font-medium text-[#7a2222] underline-offset-2 hover:underline"
                      >
                        Hapus
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* HP: kartu bertumpuk */}
          <ul className="flex flex-col gap-2 md:hidden">
            {saring.map((t) => (
              <li
                key={t.id}
                className={`rounded-xl border border-[#e2d8c6] bg-white/70 p-3 ${
                  t.perlu_review ? 'border-[#e0c9a0] bg-[#fbf3e4]' : ''
                }`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 flex-1 truncate font-medium text-[#3d2b1f]">
                    {t.keterangan || '—'}
                  </span>
                  <span
                    className={`duit shrink-0 font-semibold ${
                      t.arah === 'masuk' ? 'text-[#2c4429]' : 'text-[#7a2222]'
                    }`}
                  >
                    {t.arah === 'masuk' ? '+' : '−'} {rupiah(t.nominal)}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[#8a7a68]">
                  <span>{tanggalPendek(t.tanggal)}</span>
                  <span>·</span>
                  <span>{t.kategori}</span>
                  <span>·</span>
                  <span className="capitalize">{t.metode}</span>
                  {t.sumber === 'email' && <span>· dari email</span>}
                </div>
                <div className="mt-2 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setSunting({ ...t })}
                    className="text-xs font-medium text-[#6b4a2f] underline underline-offset-2"
                  >
                    Betulin
                  </button>
                  <button
                    type="button"
                    onClick={() => setHapusId(t.id)}
                    className="text-xs font-medium text-[#7a2222] underline underline-offset-2"
                  >
                    Hapus
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {/* ---- Panel betulin ---- */}
      {sunting && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-[#3d2b1f]/40 p-0 sm:items-center sm:p-4"
          onClick={() => setSunting(null)}
        >
          <div
            className="panel-in max-h-[90dvh] w-full overflow-y-auto rounded-t-2xl border border-[#e2d8c6] bg-[#faf6ef] p-5 sm:max-w-lg sm:rounded-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[#3d2b1f]">
              Betulin transaksi #{sunting.id}
            </h3>
            <div className="mt-4 flex flex-col gap-3.5">
              <div className="grid grid-cols-2 gap-3">
                {(['masuk', 'keluar'] as const).map((a) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => setSunting({ ...sunting, arah: a })}
                    className={`rounded-lg border-2 px-3 py-2 text-sm font-medium capitalize transition-colors ${
                      sunting.arah === a
                        ? a === 'masuk'
                          ? 'border-[#3f5e3f] bg-[#e8f0e6] text-[#2c4429]'
                          : 'border-[#9b2c2c] bg-[#f7e8e6] text-[#7a2222]'
                        : 'border-[#d9cdb9] bg-white/70 text-[#6b4a2f]'
                    }`}
                  >
                    {a}
                  </button>
                ))}
              </div>

              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[#6b4a2f]">Tanggal</span>
                <input
                  type="date"
                  value={sunting.tanggal}
                  onChange={(e) =>
                    setSunting({ ...sunting, tanggal: e.target.value })
                  }
                  className="rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b]"
                />
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[#6b4a2f]">Nominal</span>
                <input
                  inputMode="numeric"
                  value={String(sunting.nominal)}
                  onChange={(e) =>
                    setSunting({
                      ...sunting,
                      nominal: parseDuit(e.target.value),
                    })
                  }
                  className="duit rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm font-semibold text-[#3d2b1f] outline-none focus:border-[#8a5a2b]"
                />
                <span className="duit text-xs text-[#8a7a68]">
                  = {rupiah(sunting.nominal)}
                </span>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[#6b4a2f]">
                  Keterangan
                </span>
                <input
                  value={sunting.keterangan}
                  onChange={(e) =>
                    setSunting({ ...sunting, keterangan: e.target.value })
                  }
                  className="rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b]"
                />
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-[#6b4a2f]">Kategori</span>
                <select
                  value={sunting.kategori}
                  onChange={(e) =>
                    setSunting({ ...sunting, kategori: e.target.value })
                  }
                  className="rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b]"
                >
                  {KATEGORI.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </label>

              <div className="mt-1 flex gap-2">
                <button
                  type="button"
                  onClick={() => void simpanSunting()}
                  className="tombol-cepat flex-1 rounded-xl border-2 border-[#6b4a2f] bg-[#6b4a2f] px-4 text-sm font-semibold text-[#faf6ef] hover:bg-[#57391f]"
                >
                  Simpan
                </button>
                <button
                  type="button"
                  onClick={() => setSunting(null)}
                  className="rounded-xl border border-[#d9cdb9] bg-white/70 px-4 py-3 text-sm font-medium text-[#6b4a2f] hover:bg-white"
                >
                  Batal
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---- Konfirmasi hapus ---- */}
      {hapusId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#3d2b1f]/40 p-4"
          onClick={() => setHapusId(null)}
        >
          <div
            className="panel-in w-full max-w-sm rounded-2xl border border-[#e2d8c6] bg-[#faf6ef] p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-semibold text-[#3d2b1f]">
              Hapus transaksi #{hapusId}?
            </h3>
            <p className="mt-1.5 text-sm text-[#8a7a68]">
              Gak bisa dibatalin. Kalau cuma salah arah, pakai Betulin aja.
            </p>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => void konfirmasiHapus()}
                className="flex-1 rounded-lg border-2 border-[#9b2c2c] bg-[#9b2c2c] px-4 py-2.5 text-sm font-semibold text-[#faf6ef] hover:bg-[#832424]"
              >
                Hapus
              </button>
              <button
                type="button"
                onClick={() => setHapusId(null)}
                className="flex-1 rounded-lg border border-[#d9cdb9] bg-white/70 px-4 py-2.5 text-sm font-medium text-[#6b4a2f] hover:bg-white"
              >
                Batal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
