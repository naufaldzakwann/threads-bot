# THBuzzer Design System — MASTER (sumber kebenaran visual)
> Dihasilkan via `ui-ux-pro-max --design-system` ("automation bot dashboard dark futuristic neon").
> Pola: Real-Time / Operations console. Telemetri dilabeli live hanya bila dari sumber aktual + waktu update.

## Token
| Token | Nilai | Pakai |
|---|---|---|
| `--bg` | `#020617` | background OLED |
| `--bg-2` | `#0F172A` | primary surface / sider |
| `--card` | `#0E1223` | kartu |
| `--muted` | `#1A1E2F` | surface tersier |
| `--border` | `#334155` | border/divider |
| `--fg` | `#F8FAFC` | teks utama (kontras ≥4.5:1) |
| `--fg-dim` | `#94A3B8` | teks sekunder |
| `--run` | `#16A34A` | running/sukses/CTA |
| `--live` | `#22D3EE` | aksen neon sekunder, link, live-dot |
| `--queue` | `#F59E0B` | queued/warning |
| `--fail` | `#DC2626` | failed/restricted |
| `--violet` | `#8B5CF6` | aksen gradient (logo, hero) |

## Tipografi
- UI: `Fira Sans`, sistem fallback. Data/log/angka: `Fira Code` monospace.
- Google Fonts (progressive enhancement, fallback bila offline).

## Efek
- Glow minimal: `text-shadow 0 0 10px` hanya untuk indikator live/dot, bukan body text.
- Kartu: glass `rgba(14,18,35,.72)` + blur + border `#334155` + radius 12–16.
- Transisi hover 150–300ms; hormati `prefers-reduced-motion`.
- Grid/dot background halus di hero; tanpa chart dekoratif (setiap grafik dari data nyata).

## Semantik status (konsisten di semua halaman)
`active/running/published/success → run hijau` · `queued/scheduled/pending → amber` ·
`failed/restricted/checkpoint → merah` · `paused/held → slate` · `live → cyan glow`.

## Anti-pola
- Tanpa emoji sebagai ikon (pakai `@ant-design/icons`).
- Tanpa angka/hijau palsu: kosong → empty-state jujur ("belum ada data").
- Tanpa tabel mentah raksasa tanpa pagination/filter.
