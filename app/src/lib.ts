/** Tipe data & pemanggil API Diana. */

export type Arah = 'masuk' | 'keluar'

export interface Transaksi {
  id: number
  tanggal: string
  nominal: number
  arah: Arah
  kategori: string
  keterangan: string
  sumber: string
  metode: string
  perlu_review: number
}

export interface TitikHarian {
  tanggal: string
  masuk: number
  keluar: number
}

export interface Ringkasan {
  awal: string
  akhir: string
  jumlah_transaksi: number
  masuk: number
  keluar: number
  selisih: number
  bahan_baku: number
  laba_kotor: number
  per_kategori: Record<string, number>
  harian: TitikHarian[]
  perlu_review: number
  piutang: number
}

export interface Piutang {
  id: number
  nama: string
  nominal: number
  tanggal: string
  lunas: number
}

const qs = (o: Record<string, string | number | undefined>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(o)) {
    if (v !== undefined && v !== '') p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init)
  const teks = await r.text()
  let data: unknown
  try {
    data = JSON.parse(teks)
  } catch {
    throw new Error(teks.slice(0, 200) || `HTTP ${r.status}`)
  }
  if (!r.ok) {
    const p = data as { pesan?: string; error?: string }
    throw new Error(p.pesan || p.error || `HTTP ${r.status}`)
  }
  return data as T
}

const post = <T,>(path: string, body: unknown) =>
  req<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const api = {
  ringkasan: (awal: string, akhir: string) =>
    req<Ringkasan>(`/api/ringkasan${qs({ awal, akhir })}`),

  transaksi: (p: { awal?: string; akhir?: string; cari?: string; kategori?: string }) =>
    req<{ transaksi: Transaksi[]; jumlah: number }>(`/api/transaksi${qs(p)}`),

  kategori: () => req<{ kategori: { kategori: string; n: number }[] }>('/api/kategori'),

  piutang: () =>
    req<{ piutang: Piutang[]; total_belum_lunas: number }>('/api/piutang'),

  laporan: (awal: string, akhir: string) =>
    req<{ teks: string }>(`/api/laporan${qs({ awal, akhir })}`),

  catat: (b: {
    tanggal: string
    nominal: number
    arah: Arah
    keterangan: string
    metode: string
    kategori?: string
  }) => post<{ ok: boolean; pesan?: string; transaksi?: Transaksi }>('/api/catat', b),

  koreksi: (b: Partial<Transaksi> & { id: number }) =>
    post<{ ok: boolean; pesan?: string; transaksi?: Transaksi }>('/api/koreksi', b),

  hapus: (id: number) => post<{ ok: boolean; pesan?: string }>('/api/hapus', { id }),

  tambahPiutang: (nama: string, nominal: number) =>
    post<{ ok: boolean; pesan?: string }>('/api/piutang', { nama, nominal }),

  lunasPiutang: (id: number) =>
    post<{ ok: boolean; pesan?: string }>('/api/lunas', { id }),

  urlExcel: (awal: string, akhir: string) => `/api/export.xlsx${qs({ awal, akhir })}`,
}

/** Rp 25.000 — titik sebagai pemisah ribuan. */
export function rupiah(n: number): string {
  return `Rp ${Math.round(n).toLocaleString('id-ID')}`
}

/** 25.000 jadi 25000; kosong kalau bukan angka. */
export function parseDuit(s: string): number {
  const bersih = s.replace(/[^\d]/g, '')
  return bersih ? parseInt(bersih, 10) : 0
}

export const hariIni = () => new Date().toLocaleDateString('sv-SE') // YYYY-MM-DD

export function geser(hari: string, delta: number): string {
  const d = new Date(`${hari}T00:00:00`)
  d.setDate(d.getDate() + delta)
  return d.toLocaleDateString('sv-SE')
}

export function awalBulan(hari: string): string {
  return `${hari.slice(0, 7)}-01`
}

const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
  'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']

export function tanggalPendek(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return `${d} ${BULAN[m - 1]} ${y}`
}

export function labelPeriode(awal: string, akhir: string): string {
  if (awal === akhir) return tanggalPendek(awal)
  return `${tanggalPendek(awal)} – ${tanggalPendek(akhir)}`
}
