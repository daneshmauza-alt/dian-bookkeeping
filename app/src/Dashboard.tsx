import { useMemo, useState } from 'react'
import type { Ringkasan } from './lib'
import { labelPeriode, rupiah } from './lib'

interface Props {
  data: Ringkasan | null
  memuat: boolean
  awal: string
  akhir: string
  onPeriode: (awal: string, akhir: string) => void
  onKeBuku: () => void
}

/** Warna kategori: coklat-krem hangat, bukan palet neon. */
const WARNA_KAT: Record<string, string> = {
  'Bahan Baku': '#8a5a2b',
  Operasional: '#6b4a2f',
  Gaji: '#3f5e3f',
  Penjualan: '#4a6b48',
}

function warnKat(k: string, i: number): string {
  return WARNA_KAT[k] ?? ['#9b2c2c', '#a8906b', '#5a4a3c'][i % 3]
}

/** Kartu angka besar. */
function Stat({
  label,
  nilai,
  kecil,
  nada = 'netral',
}: {
  label: string
  nilai: string
  kecil?: string
  nada?: 'netral' | 'hijau' | 'merah' | 'coklat'
}) {
  const warna =
    nada === 'hijau'
      ? 'text-[#2c4429]'
      : nada === 'merah'
        ? 'text-[#7a2222]'
        : nada === 'coklat'
          ? 'text-[#6b4a2f]'
          : 'text-[#3d2b1f]'
  return (
    <div className="rounded-xl border border-[#e2d8c6] bg-white/70 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-[#8a7a68]">
        {label}
      </p>
      <p className={`duit mt-1 text-xl font-semibold sm:text-2xl ${warna}`}>
        {nilai}
      </p>
      {kecil && <p className="mt-0.5 text-xs text-[#8a7a68]">{kecil}</p>}
    </div>
  )
}

/** Grafik batang harian. SVG tangan, tanpa library. */
function Grafik({ harian }: { harian: Ringkasan['harian'] }) {
  const [sorot, setSorot] = useState<number | null>(null)
  const puncak = Math.max(...harian.map((h) => Math.max(h.masuk, h.keluar)), 1)
  const adaIsi = harian.some((h) => h.masuk > 0 || h.keluar > 0)

  if (!adaIsi) {
    return (
      <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-[#d9cdb9] bg-white/40">
        <p className="text-sm text-[#8a7a68]">
          Belum ada transaksi di periode ini.
        </p>
      </div>
    )
  }

  const T = 150 // tinggi area gambar
  const n = harian.length
  const lebarBatang = Math.max(4, Math.min(22, (700 / n) * 0.34))

  return (
    <div className="rounded-xl border border-[#e2d8c6] bg-white/70 p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-[#6b4a2f]">Naik-turun harian</p>
        <div className="flex items-center gap-3 text-xs text-[#8a7a68]">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-sm bg-[#3f5e3f]" />
            masuk
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-sm bg-[#9b2c2c]" />
            keluar
          </span>
          <span className="duit">puncak {rupiah(puncak)}</span>
        </div>
      </div>

      <div className="relative overflow-x-auto">
        <svg
          viewBox={`-8 -12 ${Math.max(n * 30 + 16, 320)} ${T + 44}`}
          className="h-48 w-full min-w-[320px]"
          role="img"
          aria-label={`Grafik ${n} hari`}
        >
          {/* garis bantu */}
          {[0, 0.5, 1].map((f) => (
            <line
              key={f}
              x1="0"
              x2={n * 30}
              y1={T - T * f}
              y2={T - T * f}
              stroke="#d9cdb9"
              strokeDasharray="3 4"
              strokeWidth="1"
            />
          ))}

          {harian.map((h, i) => {
            const x = i * 30 + 6
            const hm = (h.masuk / puncak) * T
            const hk = (h.keluar / puncak) * T
            const aktif = sorot === i
            return (
              <g
                key={h.tanggal}
                onMouseEnter={() => setSorot(i)}
                onMouseLeave={() => setSorot(null)}
                style={{ cursor: 'default' }}
              >
                <rect
                  x={x - 3}
                  y={0}
                  width={lebarBatang * 2 + 8}
                  height={T}
                  fill={aktif ? '#6b4a2f' : 'transparent'}
                  opacity={aktif ? 0.07 : 0}
                />
                {h.masuk > 0 && (
                  <rect
                    x={x}
                    y={T - hm}
                    width={lebarBatang}
                    height={Math.max(hm, 2)}
                    rx="1.5"
                    fill="#3f5e3f"
                  />
                )}
                {h.keluar > 0 && (
                  <rect
                    x={x + lebarBatang + 2}
                    y={T - hk}
                    width={lebarBatang}
                    height={Math.max(hk, 2)}
                    rx="1.5"
                    fill="#9b2c2c"
                  />
                )}
                <text
                  x={x + lebarBatang}
                  y={T + 16}
                  textAnchor="middle"
                  fontSize="10"
                  fill="#8a7a68"
                >
                  {h.tanggal.slice(8)}
                </text>
              </g>
            )
          })}
        </svg>

        {sorot !== null && (
          <div className="pointer-events-none absolute right-2 top-0 rounded-lg border border-[#d9cdb9] bg-[#faf6ef] px-3 py-2 text-xs shadow-sm">
            <p className="font-medium text-[#3d2b1f]">
              {harian[sorot].tanggal}
            </p>
            <p className="duit text-[#3f5e3f]">
              masuk {rupiah(harian[sorot].masuk)}
            </p>
            <p className="duit text-[#9b2c2c]">
              keluar {rupiah(harian[sorot].keluar)}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

/** Rincian pengeluaran per kategori, batang proporsi. */
function Kategori({ data }: { data: Record<string, number> }) {
  const entri = Object.entries(data)
  const total = entri.reduce((s, [, v]) => s + v, 0)
  if (!entri.length) {
    return (
      <div className="rounded-xl border border-[#e2d8c6] bg-white/70 p-4">
        <p className="text-sm font-medium text-[#6b4a2f]">Ke mana uangnya</p>
        <p className="mt-2 text-sm text-[#8a7a68]">
          Belum ada pengeluaran di periode ini.
        </p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-[#e2d8c6] bg-white/70 p-4">
      <p className="text-sm font-medium text-[#6b4a2f]">Ke mana uangnya</p>
      <ul className="mt-3 flex flex-col gap-3">
        {entri.map(([k, v], i) => {
          const persen = (v / total) * 100
          return (
            <li key={k} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="font-medium text-[#5a4a3c]">{k}</span>
                <span className="duit text-[#3d2b1f]">
                  {rupiah(v)}
                  <span className="ml-1.5 text-xs text-[#8a7a68]">
                    {persen.toFixed(0)}%
                  </span>
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[#f0e8db]">
                <div
                  className="h-full rounded-full transition-[width] duration-500"
                  style={{
                    width: `${persen}%`,
                    backgroundColor: warnKat(k, i),
                  }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default function Dashboard({
  data,
  memuat,
  awal,
  akhir,
  onPeriode,
  onKeBuku,
}: Props) {
  const hariIni = new Date().toLocaleDateString('sv-SE')
  const preset = useMemo(() => {
    const d = new Date(`${hariIni}T00:00:00`)
    const senin = new Date(d)
    senin.setDate(d.getDate() - ((d.getDay() + 6) % 7))
    const iso = (x: Date) => x.toLocaleDateString('sv-SE')
    return [
      { label: 'Hari ini', a: hariIni, b: hariIni },
      { label: 'Minggu ini', a: iso(senin), b: hariIni },
      { label: 'Bulan ini', a: `${hariIni.slice(0, 7)}-01`, b: hariIni },
    ]
  }, [hariIni])

  if (memuat && !data) {
    return (
      <div className="flex flex-col gap-4">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-xl border border-[#e2d8c6] bg-white/50"
          />
        ))}
      </div>
    )
  }
  if (!data) return null

  const lr = data.masuk - data.keluar

  return (
    <div className="flex flex-col gap-5">
      {/* ---- Pilih periode ---- */}
      <div className="flex flex-wrap items-center gap-2">
        {preset.map((p) => {
          const aktif = p.a === awal && p.b === akhir
          return (
            <button
              key={p.label}
              type="button"
              onClick={() => onPeriode(p.a, p.b)}
              className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                aktif
                  ? 'border-[#6b4a2f] bg-[#6b4a2f] text-[#faf6ef]'
                  : 'border-[#d9cdb9] bg-white/70 text-[#6b4a2f] hover:border-[#8a5a2b] hover:bg-white'
              }`}
            >
              {p.label}
            </button>
          )
        })}
        <div className="flex items-center gap-2 rounded-lg border border-[#d9cdb9] bg-white/70 px-2 py-1.5">
          <input
            type="date"
            value={awal}
            onChange={(e) => onPeriode(e.target.value, akhir)}
            aria-label="Tanggal mulai"
            className="bg-transparent text-sm text-[#3d2b1f] outline-none"
          />
          <span className="text-[#a0937f]">–</span>
          <input
            type="date"
            value={akhir}
            onChange={(e) => onPeriode(awal, e.target.value)}
            aria-label="Tanggal akhir"
            className="bg-transparent text-sm text-[#3d2b1f] outline-none"
          />
        </div>
      </div>

      <p className="text-sm text-[#8a7a68]">
        Periode: <span className="font-medium text-[#6b4a2f]">
          {labelPeriode(data.awal, data.akhir)}
        </span>{' '}
        · {data.jumlah_transaksi} transaksi
      </p>

      {/* ---- Peringatan yang perlu ditindak ---- */}
      {(data.perlu_review > 0 || data.piutang > 0) && (
        <div className="flex flex-col gap-2">
          {data.perlu_review > 0 && (
            <button
              type="button"
              onClick={onKeBuku}
              className="flex items-center gap-3 rounded-xl border border-[#e0c9a0] bg-[#fbf3e4] px-4 py-3 text-left transition-colors hover:bg-[#f7ecd9]"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[#8a5a2b] text-sm font-semibold text-[#faf6ef]">
                {data.perlu_review}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-[#6b4a2f]">
                  Ada yang perlu dicek
                </span>
                <span className="block text-xs text-[#8a7a68]">
                  Dari email Wondr, arah transaksinya belum pasti. Ketuk buat
                  betulin.
                </span>
              </span>
            </button>
          )}
          {data.piutang > 0 && (
            <div className="flex items-center gap-3 rounded-xl border border-[#d9c2b5] bg-[#f9eee9] px-4 py-3">
              <span className="min-w-0">
                <span className="block text-sm font-medium text-[#7a2222]">
                  Piutang belum lunas
                </span>
                <span className="duit block text-xs text-[#8a7a68]">
                  {rupiah(data.piutang)} — cek tab Piutang
                </span>
              </span>
            </div>
          )}
        </div>
      )}

      {/* ---- Angka utama ---- */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Uang masuk"
          nilai={rupiah(data.masuk)}
          kecil="penjualan"
          nada="hijau"
        />
        <Stat
          label="Uang keluar"
          nilai={rupiah(data.keluar)}
          kecil="belanja + operasional"
          nada="merah"
        />
        <Stat
          label={lr >= 0 ? 'Sisa uang' : 'Minus'}
          nilai={rupiah(Math.abs(lr))}
          kecil={lr >= 0 ? 'lebih pemasukan' : 'lebih pengeluaran'}
          nada={lr >= 0 ? 'coklat' : 'merah'}
        />
        <Stat
          label="Laba kotor"
          nilai={rupiah(data.laba_kotor)}
          kecil={`omzet dikurangi bahan baku ${rupiah(data.bahan_baku)}`}
          nada={data.laba_kotor >= 0 ? 'hijau' : 'merah'}
        />
      </div>

      <Grafik harian={data.harian} />
      <Kategori data={data.per_kategori} />

      <div className="flex flex-wrap gap-2">
        <a
          href={`/api/export.xlsx?awal=${data.awal}&akhir=${data.akhir}`}
          className="rounded-lg border border-[#6b4a2f] bg-white/70 px-4 py-2.5 text-sm font-medium text-[#6b4a2f] transition-colors hover:bg-[#6b4a2f] hover:text-[#faf6ef]"
        >
          Unduh Excel periode ini
        </a>
        <button
          type="button"
          onClick={onKeBuku}
          className="rounded-lg border border-[#d9cdb9] bg-white/70 px-4 py-2.5 text-sm font-medium text-[#6b4a2f] transition-colors hover:border-[#8a5a2b] hover:bg-white"
        >
          Buka buku kas
        </button>
      </div>
    </div>
  )
}
