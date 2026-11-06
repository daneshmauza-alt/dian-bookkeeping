import { useCallback, useEffect, useState } from 'react'
import type { Ringkasan } from './lib'
import { api, hariIni, labelPeriode, rupiah } from './lib'
import Catat from './Catat'
import Dashboard from './Dashboard'
import Buku from './Buku'
import Piutang from './Piutang'

type Tab = 'catat' | 'dashboard' | 'buku' | 'piutang'

const TAB: { id: Tab; label: string; petunjuk: string }[] = [
  { id: 'catat', label: 'Catat', petunjuk: 'Simpan transaksi baru' },
  { id: 'dashboard', label: 'Ringkasan', petunjuk: 'Lihat angka & tren' },
  { id: 'buku', label: 'Buku Kas', petunjuk: 'Semua baris transaksi' },
  { id: 'piutang', label: 'Piutang', petunjuk: 'Yang belum bayar' },
]

interface Pesan {
  jenis: 'ok' | 'gagal'
  teks: string
  kunci: number
}

export default function App() {
  const [tab, setTab] = useState<Tab>('catat')
  const [awal, setAwal] = useState(() => `${hariIni().slice(0, 7)}-01`)
  const [akhir, setAkhir] = useState(hariIni)
  const [ringkasan, setRingkasan] = useState<Ringkasan | null>(null)
  const [memuat, setMemuat] = useState(true)
  const [pesan, setPesan] = useState<Pesan | null>(null)
  /** Naikkan angka ini buat maksa tab lain memuat ulang. */
  const [versi, setVersi] = useState(0)

  const muatRingkasan = useCallback(async () => {
    setMemuat(true)
    try {
      const r = await api.ringkasan(awal, akhir)
      setRingkasan(r)
    } catch (e) {
      setPesan({
        jenis: 'gagal',
        teks: e instanceof Error ? e.message : 'Gagal memuat ringkasan.',
        kunci: Date.now(),
      })
    } finally {
      setMemuat(false)
    }
  }, [awal, akhir])

  useEffect(() => {
    void muatRingkasan()
  }, [muatRingkasan, versi])

  // Pesan hilang sendiri setelah 4 detik.
  useEffect(() => {
    if (!pesan) return
    const t = setTimeout(() => setPesan(null), 4000)
    return () => clearTimeout(t)
  }, [pesan])

  const kasihPesan = useCallback((jenis: 'ok' | 'gagal', teks: string) => {
    setPesan({ jenis, teks, kunci: Date.now() })
  }, [])

  const sesudahUbah = useCallback(() => setVersi((v) => v + 1), [])

  const masuk = ringkasan?.masuk ?? 0
  const keluar = ringkasan?.keluar ?? 0

  return (
    <div className="kertas min-h-dvh">
      {/* ---- Kepala ---- */}
      <header className="sticky top-0 z-30 border-b border-[#e2d8c6] bg-[#faf6ef]/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            {/* Tanda DIAN: bentuk roti, bukan ikon generik */}
            <span
              aria-hidden
              className="flex size-9 items-center justify-center rounded-lg border-2 border-[#6b4a2f] bg-[#f0e8db]"
            >
              <svg viewBox="0 0 24 24" className="size-5" fill="none">
                <path
                  d="M4 15c0-4 3.6-7 8-7s8 3 8 7v1.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 16.5V15Z"
                  stroke="#6b4a2f"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
                <path
                  d="M9 9.4 10.6 6M15 9.4 13.4 6"
                  stroke="#9b2c2c"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </span>
            <div>
              <h1 className="text-base font-semibold leading-tight text-[#3d2b1f]">
                Diana
              </h1>
              <p className="text-xs leading-tight text-[#8a7a68]">
                Pembukuan DIAN SNACK
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-right">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide text-[#8a7a68]">
                Masuk
              </p>
              <p className="duit text-sm font-semibold text-[#2c4429]">
                {rupiah(masuk)}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wide text-[#8a7a68]">
                Keluar
              </p>
              <p className="duit text-sm font-semibold text-[#7a2222]">
                {rupiah(keluar)}
              </p>
            </div>
            <div className="hidden sm:block">
              <p className="text-[10px] font-medium uppercase tracking-wide text-[#8a7a68]">
                Sisa
              </p>
              <p
                className={`duit text-sm font-semibold ${
                  masuk - keluar >= 0 ? 'text-[#6b4a2f]' : 'text-[#7a2222]'
                }`}
              >
                {rupiah(masuk - keluar)}
              </p>
            </div>
          </div>
        </div>

        {/* ---- Tab ---- */}
        <nav className="mx-auto max-w-5xl px-4 sm:px-6" role="tablist">
          <ul className="flex gap-1 overflow-x-auto pb-px">
            {TAB.map((t) => {
              const aktif = tab === t.id
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={aktif}
                    title={t.petunjuk}
                    onClick={() => setTab(t.id)}
                    className={`relative whitespace-nowrap px-4 py-2.5 text-sm font-medium transition-colors ${
                      aktif ? 'text-[#3d2b1f]' : 'text-[#8a7a68] hover:text-[#6b4a2f]'
                    }`}
                  >
                    {t.label}
                    <span
                      aria-hidden
                      className={`absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-[#6b4a2f] transition-transform duration-300 ${
                        aktif ? 'scale-x-100' : 'scale-x-0'
                      }`}
                    />
                  </button>
                </li>
              )
            })}
          </ul>
        </nav>
      </header>

      {/* ---- Pesan ---- */}
      {pesan && (
        <div
          key={pesan.kunci}
          role="status"
          className="panel-in fixed inset-x-4 bottom-4 z-50 mx-auto max-w-md rounded-xl border-2 px-4 py-3 shadow-lg sm:inset-x-auto sm:right-6"
          style={{
            borderColor: pesan.jenis === 'ok' ? '#3f5e3f' : '#9b2c2c',
            backgroundColor: pesan.jenis === 'ok' ? '#e8f0e6' : '#f7e8e6',
            color: pesan.jenis === 'ok' ? '#2c4429' : '#7a2222',
          }}
        >
          <p className="text-sm font-medium">{pesan.teks}</p>
        </div>
      )}

      {/* ---- Isi ---- */}
      <main className="mx-auto max-w-5xl px-4 py-5 sm:px-6 sm:py-7">
        <div key={`${tab}-${awal}-${akhir}`} className="panel-in">
          {tab === 'catat' && (
            <Catat
              versi={versi}
              onSukses={(m) => {
                kasihPesan('ok', m)
                sesudahUbah()
              }}
              onGagal={(m) => kasihPesan('gagal', m)}
            />
          )}

          {tab === 'dashboard' && (
            <Dashboard
              data={ringkasan}
              memuat={memuat}
              awal={awal}
              akhir={akhir}
              onPeriode={(a, b) => {
                setAwal(a)
                setAkhir(b)
              }}
              onKeBuku={() => setTab('buku')}
            />
          )}

          {tab === 'buku' && (
            <Buku
              awal={awal}
              akhir={akhir}
              versi={versi}
              onPesan={kasihPesan}
            />
          )}

          {tab === 'piutang' && (
            <Piutang onPesan={kasihPesan} onBerubah={sesudahUbah} />
          )}
        </div>
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-8 sm:px-6">
        <div className="garis-kas text-[#6b4a2f]" />
        <p className="mt-3 text-xs text-[#a0937f]">
          Data disimpan di laptop ini saja. Periode aktif:{' '}
          {labelPeriode(awal, akhir)}.
        </p>
      </footer>
    </div>
  )
}
