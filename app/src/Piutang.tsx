import { useEffect, useState } from 'react'
import type { Piutang as TPiutang } from './lib'
import { api, parseDuit, rupiah, tanggalPendek } from './lib'

interface Props {
  onPesan: (t: 'ok' | 'gagal', msg: string) => void
  onBerubah: () => void
}

export default function Piutang({ onPesan, onBerubah }: Props) {
  const [daftar, setDaftar] = useState<TPiutang[]>([])
  const [total, setTotal] = useState(0)
  const [memuat, setMemuat] = useState(true)
  const [nama, setNama] = useState('')
  const [nominal, setNominal] = useState('')
  const [tampilLunas, setTampilLunas] = useState(false)

  async function muat() {
    setMemuat(true)
    try {
      const r = await api.piutang()
      setDaftar(r.piutang)
      setTotal(r.total_belum_lunas)
    } catch (e) {
      onPesan('gagal', e instanceof Error ? e.message : 'Gagal memuat piutang.')
    } finally {
      setMemuat(false)
    }
  }

  useEffect(() => {
    void muat()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function tambah() {
    const n = parseDuit(nominal)
    if (!nama.trim() || n <= 0) {
      onPesan('gagal', 'Nama dan nominalnya harus diisi.')
      return
    }
    try {
      const r = await api.tambahPiutang(nama.trim(), n)
      if (!r.ok) {
        onPesan('gagal', r.pesan ?? 'Gagal menyimpan.')
        return
      }
      onPesan('ok', `Piutang ${nama.trim()} ${rupiah(n)} dicatat.`)
      setNama('')
      setNominal('')
      await muat()
      onBerubah()
    } catch (e) {
      onPesan('gagal', e instanceof Error ? e.message : 'Gagal menyimpan.')
    }
  }

  async function lunaskan(id: number, nm: string) {
    try {
      const r = await api.lunasPiutang(id)
      if (!r.ok) {
        onPesan('gagal', r.pesan ?? 'Gagal.')
        return
      }
      onPesan('ok', `Piutang ${nm} ditandai lunas.`)
      await muat()
      onBerubah()
    } catch (e) {
      onPesan('gagal', e instanceof Error ? e.message : 'Gagal.')
    }
  }

  const tampil = daftar.filter((p) => (tampilLunas ? true : !p.lunas))
  const adaLunas = daftar.some((p) => p.lunas)

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-[#e2d8c6] bg-white/70 p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-[#8a7a68]">
          Belum dibayar pelanggan
        </p>
        <p className="duit mt-1 text-2xl font-semibold text-[#7a2222]">
          {rupiah(total)}
        </p>
        <p className="mt-0.5 text-xs text-[#8a7a68]">
          Uang ini belum masuk kas, jadi jangan dihitung sebagai omzet.
        </p>
      </div>

      {/* ---- Catat baru ---- */}
      <div className="rounded-xl border border-[#e2d8c6] bg-[#f5efe4]/60 p-4">
        <p className="text-sm font-medium text-[#6b4a2f]">Catat piutang baru</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            placeholder="Nama pelanggan"
            value={nama}
            onChange={(e) => setNama(e.target.value)}
            className="min-w-32 flex-1 rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
          />
          <input
            inputMode="numeric"
            placeholder="50000"
            value={nominal}
            onChange={(e) => setNominal(e.target.value.replace(/[^\d]/g, ''))}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void tambah()
            }}
            className="duit w-32 rounded-lg border border-[#d9cdb9] bg-white px-3 py-2 text-sm text-[#3d2b1f] outline-none focus:border-[#8a5a2b] focus:ring-2 focus:ring-[#8a5a2b]/25"
          />
          <button
            type="button"
            onClick={() => void tambah()}
            className="rounded-lg border-2 border-[#6b4a2f] bg-[#6b4a2f] px-4 py-2 text-sm font-semibold text-[#faf6ef] hover:bg-[#57391f]"
          >
            Tambah
          </button>
        </div>
        {parseDuit(nominal) > 0 && (
          <p className="duit mt-2 text-xs text-[#8a7a68]">
            = {rupiah(parseDuit(nominal))}
          </p>
        )}
      </div>

      {/* ---- Daftar ---- */}
      {adaLunas && (
        <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-[#6b4a2f]">
          <input
            type="checkbox"
            checked={tampilLunas}
            onChange={(e) => setTampilLunas(e.target.checked)}
            className="size-4 accent-[#6b4a2f]"
          />
          Tampilkan yang sudah lunas
        </label>
      )}

      {memuat ? (
        <div className="h-20 animate-pulse rounded-xl border border-[#e2d8c6] bg-white/50" />
      ) : tampil.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#d9cdb9] bg-white/40 px-4 py-12 text-center">
          <p className="text-sm font-medium text-[#6b4a2f]">
            {daftar.length === 0
              ? 'Belum ada piutang tercatat'
              : 'Semua piutang sudah lunas'}
          </p>
          <p className="mt-1 text-xs text-[#8a7a68]">
            {daftar.length === 0
              ? 'Kalau ada pelanggan langganan yang belum bayar, catat di atas.'
              : 'Bagus. Gak ada yang nunggak.'}
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {tampil.map((p) => (
            <li
              key={p.id}
              className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 ${
                p.lunas
                  ? 'border-[#d9cdb9] bg-[#f5efe4]/40'
                  : 'border-[#e2d8c6] bg-white/70'
              }`}
            >
              <div className="min-w-0">
                <p
                  className={`font-medium ${
                    p.lunas ? 'text-[#8a7a68] line-through' : 'text-[#3d2b1f]'
                  }`}
                >
                  {p.nama}
                </p>
                <p className="text-xs text-[#8a7a68]">
                  sejak {tanggalPendek(p.tanggal)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`duit font-semibold ${
                    p.lunas ? 'text-[#8a7a68]' : 'text-[#7a2222]'
                  }`}
                >
                  {rupiah(p.nominal)}
                </span>
                {!p.lunas && (
                  <button
                    type="button"
                    onClick={() => void lunaskan(p.id, p.nama)}
                    className="rounded-lg border border-[#3f5e3f] bg-white/70 px-3 py-1.5 text-xs font-medium text-[#3f5e3f] transition-colors hover:bg-[#3f5e3f] hover:text-[#faf6ef]"
                  >
                    Sudah bayar
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
