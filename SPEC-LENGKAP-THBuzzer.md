# SPEC LENGKAP — THBuzzer: Aplikasi Threads Bot Desktop Multi-Akun

> **Dokumen gabungan paralel IGBuzzer.**
> Diadaptasi 1:1 dari `instagram-bot/SPEC-LENGKAP-IGBuzzer.md` + `docs/spec/01-24`.
> Baca berurutan Bagian 01 → 24. Kerangka 80% sama (arsitektur, task engine, proxy, AI, campaign, keamanan, NFR, UI), 20% diganti mengikuti realitas Threads API 2026.

**Versi dokumen:** 1.0 — 2026-09-14
**Status:** Siap untuk implementasi (Fase 0)
**Nama kode aplikasi:** `THBuzzer` (placeholder — boleh diganti, asal konsisten)
**Folder:** `threads-bot/` | **DB:** `%APPDATA%\THBuzzer\` | **Handshake:** `THBUZZER_READY`

**Sumber acuan resmi (Juli–Agustus 2026):**
- Host resmi: `https://graph.threads.net/v1.0/` (track sendiri, BUKAN graph.facebook.com — kode publish IG yang di-port mentah tidak akan jalan).
- OAuth 2.0 + App Review Meta wajib untuk semua scope `threads_*` di akun non-tester.
- Token long-lived 60 hari, wajib auto-refresh H-50 (pola sama seperti Graph IG).
- Publish = 2 langkah: `POST /{user-id}/threads` (buat container) → tunggu ±30 dtk, poll `GET /{container-id}?fields=status,error_message` (maks 1x/mnt, maks 5 mnt) → `POST /{user-id}/threads_publish` dengan `creation_id`. Status: `IN_PROGRESS, FINISHED, PUBLISHED, ERROR, EXPIRED`. Container kedaluwarsa 24 jam.
- **PERHATIAN KRITIS MEDIA CONTAINER:** Meta Graph API TIDAK menerima upload multipart file biner lokal langsung. Container gambar/video WAJIB menyertakan `image_url` / `video_url` yang dapat diakses publik oleh server Meta. Solusi terpadu THBuzzer:
  1. *Jalur Storage Cloud (Rekomendasi):* Opsi integrasi Cloudflare R2 (gratis 10 GB, zero egress) / AWS S3 presigned URL ber-TTL pendek (1–2 jam) dengan auto-cleanup setelah publish sukses.
  2. *Jalur Browser DOM (Fallback Lokal Murni):* Jika cloud storage tidak dikonfigurasi operator, posting gambar/video lokal otomatis diarahkan via engine `browser` (Playwright) yang mengunggah file biner langsung ke input DOM `threads.com`.
- Kuota resmi per profil per rolling 24 jam (endpoint cek: `GET /{user-id}/threads_publishing_limit` → `quota_usage, reply_quota_usage, delete_quota_usage, location_search_quota_usage`, semua `quota_duration: 86400`):
  - Posts: **250** (carousel dihitung 1) — scope `threads_content_publish`
  - Replies: **1.000** — scope `threads_manage_replies`
  - Deletions: **100** — scope `threads_delete`
  - Location search: **500**
  - Keyword search: **500 per rolling 7 hari** (~70/hari) — scope `threads_keyword_search`
- Budget call umum per app+user: **4800 × impressions 24 jam terakhir** (floor impressions=10 → floor 48.000 call/hari). Jangan hard-code angka — baca objek `config` runtime karena Meta bisa ubah tanpa notice.
- Batas konten: teks **500 char** (emoji dihitung byte UTF-8), maks **5 link** (inline + link_attachment, error `THREADS_API__LINK_LIMIT_EXCEEDED` sejak Des 2025), **1 topic_tag** per post (1–50 char, tanpa `.`/`&`), `reply_control` = `everyone | accounts_you_follow | mentioned_only | parent_post_author_only | followers_only`, gambar JPG/PNG ≤8 MB lebar 320–1440 px aspek ≤10:1 sRGB, video MOV/MP4 H264/HEVC AAC 23–60fps ≤1920px ≤1 GB ≤300 dtk (5 mnt), carousel 2–20 item, alt-text ≤1020 char, tanpa edit setelah publish (edit 5 mnt hanya di app manual), tanpa DM via API.
- Error non-retryable permanen contoh: subcode `4279013 "Threads account restricted"` — WAJIB masuk peta error sebagai `E-LIMIT-BLOCK` tanpa retry.
- Insight resmi per post: views, likes, replies, reposts, quotes (+shares); level akun: followers + demografi. Lookback pendek → warehouse sendiri.
- Webhook reply+mention (sejak Okt 2024) ada di API resmi, tapi tool desktop lokal tanpa URL publik TETAP pakai polling (lihat §10). Webhook hanya dicatat sebagai ekstensi masa depan via relay opsional.

---

# 01 — Ringkasan Eksekutif & Keputusan Terkunci

## 1.1 Apa yang Dibangun

**THBuzzer** adalah aplikasi desktop (bukan web/CLI) yang berjalan penuh di PC Windows operator, untuk mengelola dan mengotomasi **belasan hingga ribuan akun Threads** dari satu panel — paralel penuh IGBuzzer, dengan penyesuaian platform.

## 1.2 Masalah yang Diselesaikan

Sama seperti IGBuzzer (salah akun, lupa jadwal, pola robotic → restricted), ditambah kekhasan Threads: limit teks 500 char memaksa utas panjang, 1 topic_tag/post, flow container 2-langkah yang rawan dobel-post, URL publik untuk media official API, dan search resmi yang dijatah mingguan sehingga riset target harus hemat.

## 1.3 Pengguna

| Aktor | Deskripsi | Hak |
|---|---|---|
| **Operator** | Satu-satunya peran; pemilik PC | Semua akses |

Tanpa login aplikasi. WAJIB opsi PIN/lock lokal (default mati), sama seperti §1.3 IGBuzzer.

## 1.4 Tujuan Ukur (Success Criteria)

1. ≥ 1.000 akun dalam satu instalasi tetap responsif (navigasi < 200 ms) di PC menengah-atas (lihat §20).
2. Scheduler ≥ 5.000 job/hari persisten (tahan restart).
3. Aksi berjalan dengan app minimize ke tray.
4. Kampanye buzzer ke ≥ 500 akun peserta dalam 1 klik + progres real-time + target-side pacing aman.
5. Success rate kondisi normal ≥ 95%; kegagalan tercatat + retry/backoff otomatis.

## 1.5 Ruang Lingkup

**IN-SCOPE:**
- Manajemen akun massal Threads (akun terhubung Instagram — lihat §5): tambah manual & bulk, login, 2FA, sesi/token persisten, health score, warm-up, grup.
- **Pemisahan peran & tier akun:** `Scout` (khusus scraping & riset) vs `Actor` (eksekusi interaksi); `brand_official` (OAuth Graph API) vs `buzzer_satellite` (Browser/Session).
- Proxy manager (copy IGBuzzer §06, 95% sama).
- Tiga engine: **Official Threads API** (utama untuk publish/reply/insight brand), **Unofficial Private API** (fragile, untuk follow/like/search massal), **Browser Automation threads.com** (pilar first-class Playwright dengan optimasi `storageState.json` untuk growth, reply massal, fallback media lokal, dan checkpoint manual).
- Growth: like, follow, unfollow, reply, repost, quote (+view timeline sebagai warm-up).
- Posting & scheduling: thread teks, image/carousel, video, reply terjadwal, quote terjadwal, repost terjadwal, topic-tag manager (+auto-sanitizer), AI caption utas, dan linear threadstorm recovery.
- **Reply & Mention automation (PENGGANTI DM — Threads tidak punya DM mandiri via API):** unified replies-inbox, auto-reply keyword/regex/AI, sapa follower baru, mass-reply/broadcast ke utas target dengan throttling, serta **audit visibilitas balasan (deteksi Hidden Replies / shadowban)**.
- **Mode Kampanye Buzzer:** like massal, reply bervariasi (distribusi stance opini), repost, quote ke URL Threads target, distribusi human-like, dan **target-side velocity pacing**.
- Analytics: dashboard, kurva follower, log/audit, alert desktop + Telegram/Discord.
- AI LLM OpenAI-compatible untuk reply/komentar/caption utas + variasi sudut pandang opini buzzer.
- Solusi media hosting: Cloudflare R2 / S3 presigned URL sementara + Playwright direct DOM upload.
- Installer Windows tunggal + tray.

**OUT-OF-SCOPE v1:**
- macOS/Linux, mobile, server multi-user/lisensi/billing/cloud.
- Platform lain (IG/TikTok/X dipisah — interface Engine generik agar bisa diperluas, tapi tidak diimplementasikan).
- Pembuatan akun otomatis (HANYA kelola akun yang sudah ada).
- Pembelian proxy/OTP/captcha di dalam app (konsumsi API pihak ketiga milik operator saja).
- **DM Instagram** (akun Threads terhubung IG, tapi DM tetap dikelola via IGBuzzer — THBuzzer TIDAK menduplikasi modul DM; lihat §10).
- Edit post setelah publish via API (tidak didukung Meta).

## 1.6 Keputusan Desain [TERKUNCI]

| # | Keputusan | Nilai |
|---|---|---|
| D1 | OS target | **Windows 10/11 64-bit saja** (sama) |
| D2 | Stack | **Python 3.12 backend (FastAPI) + Electron (React + TypeScript + Ant Design) UI** (sama) |
| D3 | Engine Threads | **Tiga engine**: Official Threads API (utama publish/reply brand), Unofficial Private (growth/search legacy), Browser Automation threads.com (pilar first-class growth/media-lokal/checkpoint dengan `storageState.json`) — lihat §07 |
| D4 | Skala | **Ribuan akun**; limit hanya spek PC |
| D5 | Model | **Tool internal single-operator**, tanpa lisensi/server |
| D6 | AI | **LLM OpenAI-compatible** untuk reply, quote-text, caption utas, variasi stance opini; fallback template |
| D7 | Database | **SQLite (WAL)** via SQLAlchemy + Alembic; PostgreSQL-ready |
| D8 | Penyimpanan | **100% lokal**; trafik keluar hanya: graph.threads.net, threads.com/net, proxy operator, LLM operator, storage R2/S3 (opsional untuk media container), captcha/SMS opsional |
| D9 | Bahasa | **Indonesia** default (i18n en) |
| D10 | Rate limiting | WAJIB ada, default konservatif (tabel §19 baru, 3–5x lebih ketat dari IG) + target-side pacing; tidak bisa dimatikan |
| D11 | Lisensi kode | Open-source saja; semua key milik operator via Settings |
| D12 | Tiering Akun | **Dua tier terpisah**: `brand_official` (OAuth Graph API, aman, terikat Meta App) vs `buzzer_satellite` (Browser/Session, tanpa terikat 1 Meta App ID operator untuk mencegah ban massal) |

## 1.7 Glosarium (delta vs IGBuzzer)

| Istilah | Arti |
|---|---|
| **Engine** | `official_api`, `private_unofficial`, `browser` |
| **Official API** | `graph.threads.net/v1.0` resmi Meta (OAuth, container→publish) |
| **Private Unofficial** | Library reverse-engineer (login via kredensial IG, rapuh — pin versi, isolasi error) |
| **Container** | Objek media sementara hasil `POST /threads`, dipublish via `threads_publish`; kedaluwarsa 24 jam |
| **Thread/Utas** | Post + rangkaian reply beruntun (threadstorm) |
| **Reply/Balasan** | Komentar di bawah post (pengganti "comment" IG) |
| **Repost** | Teruskan tanpa teks tambahan |
| **Quote** | Teruskan + teks sendiri (perlu rewrite AI agar unik) |
| **Topic tag** | 1 tag per post (`topic_tag`, bukan hashtag multi) |
| **Reply control** | Siapa boleh membalas (everyone/followers_only/dsb.) |
| **Replies inbox** | Pengganti "DM inbox": daftar replies/mentions/quotes masuk (polling) |
| Istilah lain (Job, Health score, Spintax, Jitter, Proxy sticky, Session, Kill switch, Operator) | Sama seperti IGBuzzer §1.7 |

---

# 02 — Risiko, Kepatuhan, dan Penggunaan Bertanggung Jawab

> Longevity > kecepatan. Berlaku penuh dari IGBuzzer §02 + penyesuaian Threads.

## 2.1 Fakta Risiko

1. **Unofficial Private + Browser automation melanggar ToS Threads/Meta.** Risiko: restricted permanen (`4279013`), checkpoint Meta Account Center, suspend.
2. Official API tidak melanggar ToS TAPI: butuh App Review, scope per aksi, kuota keras (250 post / 1000 reply / 500 search-mingguan). Melebihi kuota = 429, bukan ban — tapi pola spam via API resmi tetap bisa di-restricted manual.
3. Risiko tertinggi: akun baru tanpa warm-up, aksi reply/quote berulang identik, banyak akun 1 IP, link >5/post, topic_tag spam.
4. **Tidak ada jaminan 100% anti-restricted.**
5. Tanggung jawab hukum operator (UU ITE dsb.) — sama.

## 2.2 Konsekuensi Desain (WAJIB)

1. Default konservatif (tabel §19 baru — JANGAN copy angka IG).
2. Rate limiter tidak bisa dimatikan; `0` ditolak validator.
3. Jitter wajib antar-aksi se-akun dan se-IP.
4. Warm-up wajib ditawarkan (default aktif), skip hanya dengan konfirmasi eksplisit.
5. Deteksi restricted/checkpoint otomatis → karantina → antrean resolusi.
6. UI jujur: tampilkan `feedback_required / restricted / 429 quota` apa adanya.
7. Kredensial + **OAuth token Threads** wajib terenkripsi (lihat §18).

## 2.3 Dialog First-Run

WAJIB dialog "Penggunaan Bertanggung Jawab" + centang "Saya mengerti risikonya" sebelum akun pertama. Key i18n `disclaimer.risk_threads` (teks beda: sebutkan 250/1000/500-search + risiko restricted unofficial).

## 2.4 Kepatuhan Official API (WAJIB bila pakai `official_api`)

1. Hanya endpoint resmi + token OAuth milik operator (Meta App milik operator).
2. Hormati `threads_publishing_limit` — baca SEBELUM antre (Meta eksplisit meminta app menegakkan limit sendiri "especially if your app allows scheduling"). Bila `quota_usage/config > 75%` → throttle 2x; `> 90%` → pause 10 mnt.
3. Hormati budget `4800 × impressions`; baca header/usage, backoff eksponensial untuk 429, dan 401 → refresh token sekali lalu retry 1x.
4. Hormati `reply_control` target (jangan paksa reply ke post `mentioned_only` via unofficial — tolak validasi).
5. Satu-satunya batas link resmi: maks 5/post — validator menolak >5 sebelum kirim (`E-VALID-LINK-LIMIT`).

---

# 03 — Arsitektur Sistem

> Copy 90% IGBuzzer §03. Yang beda hanya isi Engine Router + storage path + handshake string.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PROSES 1 — Electron (thbuzzer-ui)                                           │
│  Main (window/tray/notif/spawn+watchdog) + Renderer sandboxed (REST+WS)      │
└─────────────┬───────────────────────────────────┬──────────────────────────┘
              │ spawn + stdio handshake           │ HTTP/WS 127.0.0.1
┌─────────────▼───────────────────────────────────▼──────────────────────────┐
│  PROSES 2 — Python Core (thbuzzer-core, FastAPI + uvicorn, 1 worker)        │
│  API → Services (Account/Proxy/Thread/Reply/Campaign/Analytics/AI/...)     │
│       → Task Engine (queue persisten, worker adaptif, limiter, kill)        │
│       → Engine Router (official_api / private_unofficial / browser)         │
│       → Proxy Manager → Storage %APPDATA%\THBuzzer\                         │
└────────────────────────────────────────────────────────────────────────────┘
```

## 3.1–3.2 Handshake & Lifecycle (sama, rename)

1. Electron spawn `thbuzzer-core.exe --headless` + `THBUZZER_PARENT_PID`.
2. Core pilih port acak, serve `127.0.0.1`, cetak 1 baris: `THBUZZER_READY {"port":..,"token":"..","pid":..,"version":".."}`.
3. Renderer pakai `Bearer` token sesi (tidak ke disk, filter dari log).
4. Watchdog restart backoff 1s/5s/30s maks 5x → dialog. Job `running` saat crash → `interrupted` → reschedule sesuai idempotensi.
5. X → tray (scheduler tetap 24/7, tooltip antrian). Quit → `POST /system/shutdown` → flush ≤15 dtk → exit else kill.

## 3.3 Konkurensi (sama, angka default sama)

- `AccountExecutionGuard` 1 aksi/akun.
- Unofficial sync → `ThreadPoolExecutor` `max_concurrent_actions` default **64** (8–512); tulis DB hanya di event loop.
- Browser pool `min(browser_max_contexts=4 [1–16], RAMbebas/1.5GB)`, persisten per akun on-demand.
- Reply-poller pool `low` round-robin; interval default **15 mnt/akun** ±20%; prioritas 5 mnt.
- Limiter 3 lapis: per-akun (§19.5 baru), per-IP **6 aksi/mnt**, global **120/mnt**.
- Adaptif psutil 10 dtk (CPU>85%/RAM>90% 3x → -20% min 8; idle 5 mnt → +20%).
- Prioritas `critical > high > normal > low`.

## 3.4 Contoh Alur (versi Threads)

- **A. Jadwal thread ke 50 akun:** UI → `POST /threads-posts` → 1 `scheduled_thread` + 50 job `publish_thread` (±jitter, hormati kuota 250/akun) → container → poll FINISHED → publish → (opsional) job `first_reply` 1–5 mnt kemudian → `job_runs` + `activity_logs` + WS.
- **B. Kampanye 500 akun reply:** 1 URL Threads target + aksi reply + 500 peserta + `drip` 180 mnt → 500 job tersebar truncated-exponential → progress WS.
- **C. Restricted saat reply (`4279013`):** → status `restricted`, karantina, job `critical`, alert; resolusi manual/browser; sukses → `active` + limit 50% 24 jam.

## 3.5 Taxonomy Error (adaptasi)

| Kode | Kelas | Contoh Threads | Kebijakan |
|---|---|---|---|
| `E-AUTH-LOGIN` | Auth | password IG salah (unofficial) | Tanpa retry; `wrong_password` + alert |
| `E-AUTH-2FA` | Auth | 2FA Meta/IG | Antrean 2FA + alert |
| `E-AUTH-CHECKPOINT` | Auth | Meta Account Center challenge | Karantina + job critical + alert |
| `E-AUTH-TOKEN-EXPIRED` | Auth | OAuth 401 | Refresh sekali → retry 1x; gagal → antre re-auth + alert |
| `E-AUTH-SESSION-EXPIRED` | Auth | sesi unofficial mati tanpa password | `needs_password`, tanpa retry |
| `E-LIMIT-BLOCK` | Limit | `4279013 restricted` / `feedback_required` | **Tanpa retry**; cooldown 24 jam ±jitter; health -30 |
| `E-LIMIT-QUOTA` | Limit | 429 kuota 250/1000/500 | Reschedule besok/minggu sesuai bucket; bukan error akun; tanpa pengurang health |
| `E-LIMIT-RATE` | Limit | 429 budget call | Backoff 5m→15m→45m maks 3x |
| `E-NET-PROXY/TIMEOUT` | Net | proxy mati/timeout | Sama seperti IG (cadangan 2x / backoff 1→5→25 mnt 3x) |
| `E-ENGINE-BUG` | Engine | parse unofficial / container ERROR | Tanpa retry; snapshot + dashboard Error |
| `E-VALID-*` | Input | teks >500, link >5, topic_tag invalid, container EXPIRED, reply_control melarang | Tanpa retry; `failed_validation` |
| `E-INTERNAL` | App | bug | Tanpa retry; log + alert |

Health score rumus SAMA (lihat §5.9), bobot block -30 dipertahankan, ditambah `E-LIMIT-QUOTA` TIDAK mengurangi health (kuota ≠ reputasi).

## 3.6–3.8 Startup/Migrasi, Lapisan Data, Ekstensibilitas

Sama seperti IGBuzzer §3.6–3.8 (Alembic, writer tunggal, batch log ≤2 dtk/200 baris, read-only analytics, paginasi 50/500, interface `Engine.perform(action)->ActionResult` generik agar IG/TikTok bisa ditambah nanti tanpa rombak).

---

# 04 — Stack Teknologi [TERKUNCI]

> D2 terkunci. Delta vs IGBuzzer §04 hanya baris engine Threads.

## 4.1 Backend `apps/core`

| Komponen | Pilihan | Catatan Threads |
|---|---|---|
| Bahasa | **Python 3.12.x** | sama |
| Web | **FastAPI + uvicorn** (1 worker asyncio) | sama |
| Validasi | **Pydantic v2** + settings | sama |
| ORM | **SQLAlchemy 2.0 async + aiosqlite (WAL) + Alembic** | sama, tanpa `create_all` |
| Official Threads | **httpx** ke `graph.threads.net/v1.0` (tanpa SDK berat; wrapper tipis `engines/official/*`) — BOLEH pakai `pythreads`/`threads-python-sdk` (aiohttp+Pydantic v2) bila lolos uji bundel, tapi default httpx agar PyInstaller ringan | PENGGANTI `instagrapi` sebagai engine utama publish |
| Unofficial Private | Pluggable wrapper `engines/private_unofficial/*` (Danie1 arsip 2023 sudah tidak stabil; gunakan fork/penerus aktif jika tersedia, isolasi total error ke E-*). Sangat rapuh; jangan jadikan tumpuan tunggal | Diperlakukan sebagai fragile/eksperimental |
| Browser | **Playwright Python + Chromium** (+`patchright`/stealth, pilih satu) dengan **`storageState.json`** per akun (cookies + localStorage terenkripsi) untuk ephemeral execution; `user_data_dir` persisten hanya dialokasikan untuk sesi BrowserView manual/checkpoint | **Pilar First-Class** untuk growth, balasan massal, fallback media lokal, dan checkpoint |
| Cloud Storage (opsional) | **httpx S3 signer / boto3 lightweight client** untuk presigned upload ke Cloudflare R2 / AWS S3 | Kebutuhan URL publik media container official API; opsional jika operator pakai fallback browser |
| HTTP | **httpx** semua (timeout 30 s; upload/poll container 300 s) | sama |
| LLM | **openai SDK v1** base_url configurable | sama |
| TOTP | **pyotp** (2FA IG/Meta bila tersedia) | sama |
| Media | **Pillow** + **ffmpeg** (`imageio-ffmpeg`/`resources/bin`) | validasi 8 MB / 320–1440px / ≤300 dtk / ≤1 GB |
| Log/Sys/Crypto/Util/Test | **loguru, psutil, cryptography+keyring (AES-GCM+DPAPI), dateutil/tzdata/orjson, pytest+pytest-asyncio+respx+ruff+mypy** | sama |

Aturan: bind 127.0.0.1 saja; tanpa deps native sulit-PyInstaller; semua I/O ada timeout eksplisit.

## 4.2 Frontend `apps/ui`

SAMA PERSIS: Electron + React 18 + TS5 + AntD 5 + Vite 5 + react-query + zustand + ECharts + react-i18next (id default) + dayjs + client dari OpenAPI (orval) + electron-builder NSIS. `contextIsolation/sandbox true`, tanpa konten remote kecuali BrowserView `threads.com` di main untuk checkpoint manual, tabel virtual, tanpa logika bot di JS.

## 4.3 Struktur Monorepo

```
threads-bot/
├─ apps/
│  ├─ core/thbuzzer/{api/,services/,engines/{official/,private_unofficial/,browser/,base.py},
│  │   tasks/,models/,db/,security/,utils/} + tests/ + pyproject.toml
│  └─ ui/src/{main/,preload/,renderer/{pages/,components/,api/,i18n/},shared/}
├─ resources/{bin/ffmpeg.exe,icons/}
├─ docs/spec/ + SPEC-LENGKAP-THBuzzer.md
├─ scripts/ + DECISIONS.md + README.md
```

## 4.4–4.5 Kontrak API & Konvensi

Sama: OpenAPI → generator TS, tanpa URL manual, regenerasi tiap ubah endpoint; kode English, string via i18n, mypy strict + ruff + ESLint/Prettier, commit konvensional.

---

# 05 — Modul Manajemen Akun

> Struktur SAMA seperti IGBuzzer §05. Delta: akun Threads = terhubung Instagram; auth ganda (OAuth resmi + kredensial IG untuk unofficial/browser).

## 5.1 Data Akun (`accounts`)

Field IGBuzzer dipertahankan + adaptasi: `username` (Threads handle, unik case-insensitive), `password_enc` (password IG terhubung — untuk unofficial/browser), `email/email_password_enc + imap_*` (auto-OTP Meta), `totp_secret_enc`, `status`, `health_score`, `group_id`, `tags[]`, `priority`, `timezone` (default `Asia/Jakarta`), `locale/country`, `device_params` (fingerprint Threads: app-version + android/ios + UA — dibuat sekali, permanen), `session_blob_enc` (token unofficial), **`storage_state_enc`** (Playwright cookies + localStorage terenkripsi untuk browser ephemeral), **`threads_user_id`** (ID numerik resmi), **`oauth_token_id`** (FK ke `threads_tokens`), `default_engine` (default `official_api` untuk brand, `browser` untuk buzzer), **`account_tier`** (`brand_official | buzzer_satellite`), **`account_role`** (`scout | actor` — default `actor`), `daily_limit_overrides`, `warmup_plan_id`, `proxy_id`, timestamps, soft-delete.

Tabel token baru `threads_tokens`: `id, account_id, app_id, scopes[], access_token_enc (long-lived 60 hari), refresh_token_enc?, expires_at, last_refreshed_at`. Auto-refresh H-50 via recurring job. Khusus akun `brand_official`.

## 5.2 Status (sama + 1 status baru)

`new, login_pending, two_factor_required, wrong_password, warming_up, active, checkpoint, restricted (pengganti action_blocked — untuk 4279013), suspended, disabled, retired, deleted` + flag `needs_password` / `needs_reauth` (OAuth kadaluarsa). Semua transisi → `account_status_history` + WS `account.status_changed` + alert.

## 5.3 Tambah Akun

- **A. Manual:** username/handle + password IG + (opsional) email/IMAP + TOTP + grup/timezone/proxy + pilih tier (`brand_official` atau `buzzer_satellite`) dan role (`scout` atau `actor`). Opsional langsung sambung OAuth (paste auth-code atau wizard §7.6) untuk tier brand.
- **B. Import sesi/token tanpa password:** file `session_*.json` (unofficial), `storageState_*.json` (Playwright cookies+localStorage), atau `token.json` (OAuth). Validasi ringan (`GET /me?fields=id,username` atau navigasi browser cepat) sebelum terapkan. Tanpa password → `needs_password`; tanpa refresh-token → `needs_reauth` saat 401.
- **C. Bulk CSV/Excel** header WAJIB: `username,password,email,email_password,proxy,totp_secret,timezone,country,group,tags,priority,account_tier,account_role,threads_user_id,oauth_token` — antre login berurutan jarak 30–120 dtk, maks 20 login baru/jam global + progress WS `import.progress`.
- **D. Export** sama (password/token TIDAK ikut kecuali centang + konfirmasi + zip opsional).

## 5.4 Fingerprint Stabil (KRITIS, adaptasi)

Dibuat sekali, simpan permanen di `device_params`; JANGAN regenerasi saat restart. Untuk unofficial: app-version + device-id + uuid; untuk browser: UA/viewport/locale/timezone threads.com wajib konsisten dengan `device_params` + negara proxy (warning bila mismatch).

## 5.5 Sesi & Token Persisten

- Browser: simpan `storage_state_enc` (cookies + localStorage terenkripsi) tiap sesi sukses. Context browser di-spawn secara *ephemeral* (hidup hanya selama aksi berjalan) untuk menghemat RAM dan mencegah penumpukan file profil ratusan GB di disk.
- Unofficial: simpan `session_blob` tiap aksi sukses (cookies berputar). Re-login auto maks 1x/akun/24 jam, global 30/jam.
- Official: simpan token terenkripsi; refresh H-50 otomatis; 401 → refresh sekali → retry 1x; gagal → `needs_reauth` + alert (tanpa retry buta).

## 5.6 Warm-up 14 Hari (template default, editable per grup)

| Hari | Aktivitas (jam aktif acak akun) |
|---|---|
| 1–2 | Browse timeline 3–8 sesi, view 5–15 thread; TANPA tulis |
| 3–5 | + like 10–20; lengkapi profil sekali |
| 6–10 | + follow 5–10, like 15–30 |
| 11–14 | + reply 1–3 (template/AI), repost 1–3 |
| 15+ | Naik 25%/hari ke 100% (hari 21 full) |

Berhenti saat checkpoint/restricted → ulang fase saat ini. Skip hanya konfirmasi eksplisit.

## 5.7 Checkpoint & Restricted

Karantina (`held` semua pending) + job `critical` + alert — sama. 4 jalur: Auto-IMAP (20 dtk × 10 mnt), Auto-SMS provider (SMS-Activate/5SIM, 5 dtk × 180 dtk), kode manual, browser manual threads.com (`BrowserView` partisi per akun → "Saya sudah selesai" → verifikasi `GET /me`). Sukses → `active` + limit 50% 24 jam, health -15. Maks 3 attempt/24 jam → `checkpoint_manual_only`. `4279013 restricted` = tanpa auto-retry; hanya manual + cooldown 24 jam (±jitter), 2x/7 hari → 72 jam.

## 5.8 Edit Profil Massal

`name, bio (≤150 char), avatar, link (≤5), privat/publik` + spintax `{username}|{random_name_id}|{niche_word}`. 1 job/akun, jarak 2–10 mnt, maks 50/hari/grup.

## 5.9 Health Score (rumus SAMA, klarifikasi kuota)

```
skor = clamp(0,100, 100 -15×checkpoint_7h -30×restricted_7h -2×fail% +1×streak(maks14))
```
`E-LIMIT-QUOTA/429-kuota` TIDAK mengurangi skor. Kategori: ≥80 sehat, 50–79 waspada, 20–49 kritis, <20 bahaya + saran istirahat.

## 5.10 Grup/Tag/Operasi Massal + 5.11 Acceptance

Sama seperti IGBuzzer (filter grup/tag/health/locale; bulk pause/resume/limit/engine/proxy/logout/disable/delete/export/tes-proxy; tabel virtual). Acceptance: ganti `account_info` → `GET /me`, `challenge_required` → checkpoint Meta/`4279013`, bio ≤150, fingerprint Threads stabil.

---

# 06 — Modul Proxy Manager

> Copy 95% IGBuzzer §06. Satu-satunya delta: host health-check + pengecualian.

- Semua trafik unofficial + browser WAJIB via proxy akun. Official `graph.threads.net` default LANGSUNG (server-side resmi), opsional via proxy dengan setting `official_via_proxy=false` default.
- LLM/captcha/webhook langsung (tanpa proxy).
- Model `proxies` SAMA (+`cooling_down`, `rotation_url/interval/cooldown 15s/last_rotated_at` untuk mobile proxy).
- Sticky `accounts.proxy_id`, rekomendasi maks **3 akun/proxy** (warning), auto-assign load terkecil + cocok country≈locale, hapus terpakai → konfirmasi + reassign.
- Format import SAMA (`host:port`, `host:port:user:pass`, `protocol://...`, CSV + provider fetch JSON).
- Health check job `low` tiap 30 mnt (5–360): `GET https://www.threads.com/` timeout 10 dtk (PENGGANTI `i.instagram.com`); latensi >3 dtk → degraded; gagal 3x → dead + alert + exclude. Retry `E-NET-PROXY` via cadangan (sticky tidak berubah otomatis).
- Mobile proxy: tombol "Putar IP", trigger auto saat `E-LIMIT-BLOCK/CHECKPOINT`, prosedur GET `rotation_url` → 15 dtk → `cooling_down` → verifikasi via `api.ipify.org` → `alive`, gagal 3x → degraded. (§24.1)

---

# 07 — Engine Router

> Bagian PALING BEDA dari IGBuzzer. Interface SAMA, isi diganti total.

Interface SAMA: `Engine.perform(ctx) -> ActionResult {success, data, error_code, raw_snapshot, engine_used, latency}`. Service DILARANG panggil library Threads langsung.

## 7.1 `official_api` (utama publish/reply/insight/delete untuk tier brand)

- httpx ke `graph.threads.net/v1.0`, timeout 30 s (upload/poll 300 s).
- Publish 2-langkah + poll `IN_PROGRESS→FINISHED→PUBLISHED` (1x/mnt, ≤5 mnt) + `threads_publish`; baca `threads_publishing_limit` sebelum antre; hormati 75%/90% (throttle/pause); 429 → `E-LIMIT-QUOTA/RATE`; 401 → refresh → retry 1x.
- **Alur Khusus Media Lokal (Container URL Requirement):** Meta Graph API menolak upload file lokal langsung. Jika job mempublikasikan gambar/video lokal:
  1. Jika Cloudflare R2 / S3 terkonfigurasi di Settings → upload file sementara, peroleh presigned URL publik ber-TTL 1–2 jam, kirim ke Meta sebagai `image_url`/`video_url`, hapus file dari cloud setelah container sukses dibuat.
  2. Jika cloud storage TIDAK terkonfigurasi → job otomatis dialihkan ke engine `browser` untuk direct upload via DOM tanpa memerlukan URL publik.
- Kapabilitas ✅: thread teks, image/carousel (2–20), video (≤5 mnt), reply, quote (via container `quote_post_id`), repost (endpoint repost resmi bila tersedia, else fallback), delete sendiri (100/hari), hide/unhide reply, insights, keyword search (jatah mingguan), baca post/reply sendiri.
- ❌: follow/unfollow/like massal orang lain, reply ke post `mentioned_only` yang melarang, DM (tidak ada), edit setelah publish.

## 7.2 `private_unofficial` (fragile/eksperimental — growth/search legacy)

- Adapter pluggable di `engines/private_unofficial/*`. Sinkron → ThreadPool. Login via kredensial IG + `cached_token_path` bersama untuk hemat login. Mapping error terpusat `engines/private_unofficial/errors.py` (termasuk `4279013` → `E-LIMIT-BLOCK` non-retryable).
- ✅: follow/unfollow, like/unlike, baca followers/following/likers, timeline/search luas (tanpa jatah 500/minggu), post/reply (cadangan).
- ⚠️: Sangat rapuh terhadap perubahan internal Meta/Bloks. Jika 3x `E-ENGINE-BUG` beruntun → tandai `degraded_engine` 24 jam + otomatis fallback ke `browser`.

## 7.3 `browser` (threads.com via Playwright — Pilar First-Class)

- **Lifecycle & Optimasi Resource:** Browser singleton Chromium berjalan di background. Tiap aksi akun me-load context secara *ephemeral* menggunakan **`storageState.json`** (cookies + localStorage terenkripsi, ~20 KB/akun). Begitu aksi selesai, storage state disimpan kembali dan context ditutup. Ini menghemat RAM (hanya 150–250 MB per active context) dan mengeliminasi kebutuhan ratusan GB folder `user_data_dir`. `user_data_dir` persisten hanya dibuka saat sesi interaktif manual/checkpoint.
- Fitur pendukung: stealth + `selectors.py` + `humanize.py` (mouse/scroll/ketik acak) + screenshot saat `E-ENGINE-BUG`.
- ✅ utama: direct media upload lokal tanpa butuh S3/R2, checkpoint manual via BrowserView, growth/like/follow/reply untuk tier `buzzer_satellite`, audit visibilitas reply (deteksi Hidden Replies).
- Konkurensi: pool dibatasi `min(browser_max_contexts=4 [1–16], RAMbebas/1.5GB)`.

## 7.4 Routing (berbasis Tier & Job Type)

Override job > override akun > hard rules:
- `resolve_checkpoint` / login gagal checkpoint → `browser` (BrowserView manual).
- **Akun `brand_official`:**
  - `publish_thread / reply / quote / repost / delete / insight` → `official_api` (jika media lokal & tanpa R2 → alihkan ke `browser`).
  - `search hemat` (jatah resmi) → `official_api`.
- **Akun `buzzer_satellite`:**
  - `like / follow / unfollow / reply / repost / quote / publish` → default `browser` (atau `private_unofficial` jika modul aktif & sehat). Akun buzzer DILARANG memakai Meta App ID operator untuk mencegah pemblokiran massal App ID.
- `search luas / follower scraping` → HANYA dijalankan oleh akun role `scout` (via `browser` atau `private_unofficial`).
- `dm_*` TIDAK ADA — request `dm_*` ditolak `E-VALID-UNSUPPORTED` dengan pesan "gunakan Replies (§10)".
- `E-ENGINE-BUG` 3x → fallback + `degraded_engine` 24 jam.
- Publish teks resmi tidak di-fallback (anti dobel-post; container `creation_id` sekali pakai).

## 7.5 Token Wizard (adaptasi Graph IG)

Wizard Meta App Threads: App ID/Secret, redirect URI, scopes (`threads_basic, threads_content_publish, threads_manage_replies, threads_manage_insights, threads_keyword_search, threads_delete`), tukar code→short→long-lived (60 hari), simpan terenkripsi, tombol Test (`GET /me`) + Refresh. Token per akun (bukan per app) — tabel `threads_tokens`.

## 7.6 Rate Hormat Resmi

`X-App-Usage` analog + `threads_publishing_limit` dibaca tiap enqueue + tiap jam: >75% throttle 2x, >90% pause 10 mnt, 429 → reschedule sesuai bucket (post→besok, search→minggu depan).

---

# 08 — Growth Automation

> Struktur SAMA (aktivitas reusable + wizard 4 langkah), isi target/aksi diganti Threads.

- **Aksi:** `like, follow, unfollow` (hanya dari `followed_by_us` + opsi non-followback ≥3 hari), `reply` (1x/post/akun, hormati `reply_control`), `repost`, `quote` (wajib teks unik AI/spintax), serta **top-reply engagement** (like/reply balasan teratas untuk mendongkrak visibilitas). **DIHAPUS vs IG:** `comment→reply` (rename), `view_story/save_post/poll_vote` dihapus; `view_thread/timeline` hanya untuk warm-up (tanpa kuota tulis).
- **Target & Delegasi Peran Scout:**
  - Sumber: keyword/topic search, followers/following kompetitor (cache 24 jam, cursor persisten), repliers/likers thread viral, timeline For You (browser), list manual URL/handle (txt/CSV), feed sendiri (untuk first-reply).
  - **ATURAN KERAS SCOUT:** Seluruh aktivitas pencarian target (keyword search) dan scraping profil/follower WAJIB dieksekusi oleh akun dengan role **`scout`** (1–3 akun khusus). Akun berstatus **`actor`** dilarang menjalankan job search/scraping mandiri guna menjaga jatah kuota mingguan (500 search/7 hari) dan melindungi reputasi akun aktor.
- **Filter** (cache profil 7 hari): followers 50–∞, thread-count min 3, avatar wajib, privat skip default, verified skip opsional, blacklist never, whitelist bypass, re-interaksi skip <30 hari, bio keyword, rasio, business. Verified via Meta Verified dipertahankan.
- **Teks reply/quote:** spintax (1–500 char — NAIK dari 150 IG, 0–2 emoji) / AI (konteks caption 500 char + persona, cache per akun-post) / keyword-mapping. Fallback AI→template. Quote WAJIB unik (blok duplikat persis saat build).
- **Human-like:** slot di window aktif, delay 60–240 dtk (LEBIH LONGGAR dari IG 40–180), break 15–45 mnt tiap 15–30 aksi, variasi harian ±30%, refresh sumber staggered 1–3 jam.
- **UI:** daftar + wizard (akun → aksi+target → filter+limit+preview total → jadwal) + detail live feed WS. Preview WAJIB tampilkan estimasi jatah search mingguan bila target pakai official search.

---

# 09 — Posting & Scheduling

> Struktur SAMA (library + kalender + queue + manifest + hashtag→topic + AI), validasi diganti total.

## 9.1 Jenis & Validasi `MediaService` (angka RESMI 2026)

- Thread teks: ≤500 char, ≤5 link, 1 `topic_tag` (1–50, tanpa `.`/`&`), `reply_control` default `everyone`.
  - **Topic Tag Auto-Sanitizer:** Jika input operator/AI memiliki beberapa hashtag (misal `#inovasi #teknologi #ai`), sanitizer otomatis mengekstrak hashtag pertama menjadi 1 `topic_tag` resmi, lalu membersihkan karakter `#` pada kata-kata berikutnya menjadi teks biasa (`inovasi teknologi ai`) agar mematuhi aturan 1-tag Meta tanpa error validasi.
- Image: JPG/PNG ≤8 MB, lebar 320–1440, aspek ≤10:1, sRGB. Carousel 2–20 (campur foto/video, 1 post dihitung 1 kuota).
- Video: MOV/MP4 H264/HEVC AAC 23–60fps ≤1920px ≤1 GB ≤300 dtk. GIF animasi → video.
- **Strategi Upload Media Lokal:**
  - Official API: Wajib URL publik. Jika Cloudflare R2 / S3 terkonfigurasi → upload dengan presigned URL (TTL 1 jam) → kirim URL ke Meta container → hapus file di cloud setelah publish.
  - Jika R2/S3 tidak dikonfigurasi → posting media lokal otomatis dialihkan via `browser` engine yang mengunggah langsung via DOM `input[type="file"]`.
- Text attachment 10k char (fitur app 2025): v1 TIDAK didukung API resmi → validator tolak dengan pesan jelas (catat DECISIONS.md), bukan cangkok diam-diam.
- **DIHAPUS vs IG:** feed/carousel-IG/Reels/Story/stiker-story/first-comment/watermark-story/best-time-story. **PENGGANTI:** `first_reply` (balasan pertama di utas sendiri 1–5 mnt setelah publish, untuk pancing diskusi + tambah konteks/link).
- Alt-text ≤1020 didukung (opsional per media).

## 9.2–9.6 Library, Caption Utas, Penjadwalan, Repost→Repost/Quote, UI

- Library `%APPDATA%/THBuzzer/media/library/<id>/` + hash dedup + tag + CSV manifest (`media_path,account_filter_group,text_template,topic_tag,reply_control,first_reply,scheduled_at,timezone`).
- Caption utas: spintax + variabel `{username,group_name,topic_tag:X,date,niche:X}` (maks 500, bukan 2200). **Topic-tag manager** (pengganti hashtag manager): set bernama 1-tag/post, **tanpa banned-checker** (diganti spam-word checker lokal + cek 5-link), pakai acak dari set + auto-sanitizer.
- AI caption utas (persona+topik+CTA, ≤500) editable; threadstorm panjang → pecah otomatis per 500 char dengan prioritas potong antar-kalimat (format Ayrshare: jaga kalimat utuh, bila kalimat >500 potong antar-kata).
- **Threadstorm Linear Chaining & Failure Recovery:**
  - Pola rantai linear: Post 1 (root) → Post 2 me-reply Post 1 (`reply_to_id = Post1`) → Post 3 me-reply Post 2 (`reply_to_id = Post2`), menjaga utas bersambung rapi.
  - Penanganan kegagalan bertingkat: Jika segmen ke-N gagal publish (setelah batas retry habis), seluruh segmen lanjutan (N+1...) otomatis di-pause dengan status **`threadstorm_interrupted`** + alert ke operator. Sistem DILARANG melanjutkan sisa segmen secara buta agar tidak tercipta postingan yatim piatu. Operator dapat memilih "Lanjutkan setelah fix" atau "Batalkan sisa segmen".
- `scheduled_threads`: teks dirender saat `queued`, eksekusi `scheduled_at ±jitter 0–15 mnt` dalam window aktif, retry `E-NET` auto, guard dobel (cek `published_threads_id` + hash 6 post terakhir — PENTING karena flow 2-langkah rawan "500 yang sebenarnya sudah publish" → sebelum retry WAJIB `GET` verifikasi), `first_reply` 1–5 mnt sesudahnya.
- UI: kalender (drag reschedule), queue 24 jam, bulk geser/pause/batal/duplikat, **quick-thread** (stagger 1–8 mnt/akun). Repost native (tanpa download-upload) + quote dengan kredit + rewrite AI; 1 sumber tidak 2x ke akun sama.

---

# 10 — Reply & Mention Automation (PENGGANTI DM)

> Modul DM IGBuzzer (§10) TIDAK di-port 1:1 karena Threads tidak punya DM mandiri via API. Seluruh konsep dipetakan ulang:

| IG DM (§10) | Threads (§10 baru) |
|---|---|
| Polling inbox 15 mnt | Polling replies/mentions/quotes 15 mnt ±20% (priority/rule-aktif 5 mnt) — via official `replies` + unofficial `mentions` |
| Unified inbox 3-panel + balas manual ≤30 dtk | **Unified REPLIES inbox 3-panel** (daftar utas → daftar reply → detail + balas manual sebagai reply ≤30 dtk, prioritas `high`) |
| Rules keyword/regex/any/first/story_mention/story_reply/new_follower | Rules trigger `keyword/regex/any/first_reply/mention/quote/new_follower`; kondisi jam/offline; respons template/AI (konteks 6 pesan, ≤500, no URL default, strip markdown); delay ketik 2–8 dtk +60–150ms/char (3–20 s) + baca 1–5 dtk |
| Anti-loop 3/24 jam, skip sesama kelolaan, kuota→besok, regex tester | SAMA (3 balasan bot/utas/24 jam, skip sesama kelolaan, kuota habis→antre besok, tester) |
| Welcome DM 15–120 mnt 1x/follower 20/hari | **Sapa follower baru** via follow-back + 1 reply sapaan di thread mereka (delay 15–120 mnt, 1x/follower, 20/hari, dedup) |
| Story-mention auto-thanks 10–60 mnt | **Mention/quote auto-thanks** 10–60 mnt + opsi view/like dulu |
| Broadcast `dm_campaigns` + filter privat/blacklist/cooldown-14-hari + personalisasi + warning URL + 1 DM/penerima | **Mass-reply campaign** (`reply_campaigns`): sumber followers/list/repliers/likers/follower-7hari, filter + cooldown 14 hari, template/AI + 1 gambar, warning URL, throttling linear-acak, 1 reply/penerima/kampanye, report terkirim/gagal/pending |
| Aturan 24-jam window Graph | **DIHAPUS** (tidak ada window messaging di Threads) |
| Tabel `dm_conversations/messages/rules/campaigns/recipients` | Rename → `thread_conversations/messages, reply_rules, reply_campaigns/recipients` (skema sama, kolom `channel='threads_reply'`) |

- **Audit Visibilitas & Deteksi Hidden Replies (Shadowban Check):**
  - Algoritma Threads secara otomatis menyembunyikan komentar spam/bot ke dalam lipatan *"Lihat balasan tersembunyi"* (*Hidden Replies*). Balasan yang disembunyikan Meta tetap mengembalikan respons API `200 OK / PUBLISHED`, tetapi tidak terlihat oleh pengguna umum.
  - THBuzzer menyertakan **Visibility Auditor**: job prioritas `low` dijadwalkan 10–15 menit setelah balasan dipublish, mengecek via unauthenticated HTTP request atau akun `scout` apakah ID balasan muncul di DOM/feed publik.
  - Jika terdeteksi masuk *Hidden Replies*: tandai balasan sebagai status `hidden_by_platform`, catat di dashboard, berikan peringatan akun (*soft-warning*), dan kurangi frekuensi balasan akun tersebut selama 24 jam.

Catatan webhook: endpoint reply/mention webhook resmi DICATAT di arsitektur sebagai ekstensi (relay publik opsional) — v1 tetap polling karena desktop lokal. Jangan janjikan real-time <15 mnt di spec v1.

---

# 11 — Campaign Buzzer

> Pembeda 1-klik dipertahankan; aksi + pre-flight + preset diganti Threads.

- Model SAMA: `targets` 1–20 URL **threads.com/@user/post/ID**, `actions[]`, `participants` (filter grup/tag/health/locale/active + count sampling + exclude; count dibaca saat eksekusi), `schedule {now/scheduled/recurring, spread}`, `distribution`, `safety {maks 1 aksi/jenis/target}`, status draft→scheduled→running⇄paused→done/stopped/failed_partial.
- **Aksi:** like, **reply** (unik/akun, blok duplikat persis), **repost**, **quote** (rewrite unik), view-timeline (warm only). Preset "Amplifikasi Thread": like 100% + reply 60% + repost 30% + quote 20%. **`share_to_story/repost_to_feed/share_dm/upvote_comment` DIHAPUS**; nested discussion diterapkan sebagai **Top-Reply Amplification** (10–20% akun buzzer me-reply balasan buzzer kawan + like balasan tersebut untuk mendongkraknya ke peringkat teratas komentar).
- **Distribusi & Target-Side Velocity Pacing:**
  - Pola: `burst` (min 30 mnt/100+ akun, validator tolak <30) + `drip` truncated-exponential median spread/2 (`tasks/distribution.py`, seed deterministik; pause/resume deterministik).
  - **TARGET-SIDE PACING GUARD (KRITIS):** Parameter `max_target_actions_per_minute` (default 3–6 aksi/menit per URL target). Meskipun ratusan akun siap jalan, kecepatan interaksi yang masuk ke 1 URL target dibatasi secara ketat agar tidak memicu sistem pendeteksi anomali lonjakan Meta yang dapat menyebabkan thread target di-shadowban atau balasan dibuang ke *Hidden Replies*.
- **Pre-flight WAJIB** (1 job burner): cek target ada/publik/`reply_control` mengizinkan/`deleted=false`; gagal → `aborted_target_invalid` tanpa makan kuota. Guard: active + health≥30 + kuota tersedia (cek `threads_publishing_limit` dulu), cadangan otomatis.
- Kontrol pause/resume/stop/tambah-peserta/retry-gagal, overflow `hold` (tunda besok, default) / `mark`. Progress WS 5 dtk.
- UI: daftar + wizard 4 langkah (target+preview → aksi+spintax+AI [dengan Stance Distribution] → armada+sampling → jadwal+histogram+ringkasan kuota **250/1000** + setting target-pacing) + detail per-peserta + export.

---

# 12 — Analytics & Monitoring

> Struktur SAMA, metrik diganti Threads.

- Dashboard: akun per status, aksi 24 jam + success%, antrian + backlog 1 jam, replies unread + balasan bot, kampanye aktif, grafik aksi/jam + donut error + follower 7/30 hari, live feed WS (buffer, 10 fps, tahan 10rb event/mnt).
- Snapshot harian `low` staggered malam timezone akun: followers/following/thread-count + **N thread terakhir** (PENGGANTI 12 media IG) + metrics views/likes/replies/reposts/quotes → `account_stats_snapshots`. Gagal → `skipped`. Lookback pendek → jangan hapus snapshot lokal (retensi 90 hari).
- Halaman per akun (kurva ECharts, health history, success ratio, metrik thread, tanggal restricted), per grup (agregat+ranking), per konten (semua thread + filter topic_tag/reply_control), audit `activity_logs` (filter+export, retensi 90 hari auto-clean).
- Alert SAMA + pemicu `threads_quota_90` (kuota 250/1000 >90%) dan `search_quota_weekly_80` (400/500 mingguan). Kanal desktop + Telegram + Discord + generic JSON, dedup 1/5 mnt, quiet hours. Telegram 2-arah SAMA (`/status /kill /resume /otp` + `/pause_campaign`). Kuota disk SAMA (media/cache 5GB, screenshot 7 hari, sisa <2GB warning + tolak download, DB >4GB warning).

---

# 13 — AI / LLM

> Copy 90% IGBuzzer §13. Beda: batas 500 char + topic_tag + quote-rewrite + stance distribution.

- Provider SAMA: OpenAI SDK v1 base_url configurable, multi-profil (rpm default 60, daily_budget, harga/1K, timeout 30 s). Tanpa key → fallback template + badge "AI nonaktif".
- Persona per grup SAMA (tone, language/dialect, emoji none/light/heavy, age, interests, catchphrases, taboo, max_length, few-shot).
- **Stance & Angle Distribution (Anti-Semantic Clustering):**
  Untuk mencegah model deteksi spam NLP Meta mengelompokkan balasan botnet karena keseragaman opini, prompt AI pada kampanye buzzer menerapkan variasi sudut pandang otomatis:
  - 60% *Mendukung / Afirmatif* (menguatkan narasi thread)
  - 20% *Kepo / Bertanya* (memancing percakapan lanjutan)
  - 10% *Testimonial / Pengalaman Nyata* (berbagi cerita personal singkat)
  - 10% *Menanggapi Komentar Lain* (me-reply top komentar orang lain di utas)
  Distribusi ini dapat disesuaikan per kampanye di UI Wizard.
- Use-case (adaptasi): `reply` (6 pesan konteks, ≤500, no URL default, strip markdown), **`quote_rewrite`** (tulis ulang angle berbeda, ≤500, no duplikat 7 hari), **`thread_caption`** (≤500; utas panjang → outline per 500 char), `campaign_reply`, `first_reply`. Prompt editable DB (`{{persona/context/instruction/stance}}`), temp reply 0.7/quote 0.9/caption 0.8. Post-proc: trim, validasi 500/5-link/1-tag (+auto-sanitizer), regenerate 1x → fallback, dedup 7 hari. Timeout→retry 1x→fallback (tidak gagalkan job bisnis), cache `(account,context_hash)`. Budget habis → stop AI hari itu + alert. Halaman AI Usage 30 hari SAMA.

---

# 14 — Task Engine & Scheduler

> Copy 95% IGBuzzer §14. Beda: daftar job-type + guard kuota resmi.

- `jobs` SAMA (prioritas critical>high>normal>low, payload JSON, engine_hint, status scheduled/pending/running/held/completed/failed/cancelled/interrupted/dead_letter/needs_review, scheduled_at UTC, attempt/max, dedup_key, idempotency safe/no_retry).
- **Job-type baru:** `publish_thread, publish_carousel, publish_video, first_reply, reply, repost, quote, hide_reply, delete_thread, poll_replies, snapshot, health_check, campaign_reply/*, warmup_*, recurring, login, verify_oauth, refresh_oauth`. **Dihapus:** `publish_post/feed/reels/story, first_comment, dm_send, poll_inbox(DM), view_story, save_post`.
- Tick 1 dtk SAMA. Guard +1: **cek `threads_publishing_limit` sebelum `publish_thread/reply`** (kuota habis → `held` besok, bukan gagal; tanpa pengurang health). Tulis `job_runs` + `activity_logs` + WS + kuota. Retry per E-* (§3.5). DLQ default growth+reply. `no_retry` crash → `needs_review`.
- Recurring SAMA + 2 baru: `oauth_refresh` (H-50 per akun), `quota_reset` tengah malam **timezone tiap akun** (rolling-24-jam dihitung mundur, bukan kalender — dokumentasikan eksplisit). Poll-replies dinamis, snapshot staggered, proxy check, `db_maintenance`, `warmup_tick`, `llm_reset`, backup mingguan.
- Fairness SAMA (aging 30 mnt, semaphore publish 32, backpressure 10rb + warning, kill 3 lapis global/grup/akun + `Ctrl+Shift+X` + tray ≤5 dtk + banner merah).
- Recovery SAMA (running→interrupted; sleep freeze 15 dtk + reset pool + ping proxy; overdue >24 jam expired else jitter 30–120 mnt; single-writer queue batch ≤1000 ms/200 baris, busy 15 dtk).

---

# 15 — Database Schema

> Konvensi SAMA (INTEGER PK, unixepoch UTC, bool 0/1, JSON TEXT, `_enc` ciphertext, WAL+NORMAL+FK+busy 5 dtk, optimize mingguan, retensi 90 hari, backup `VACUUM INTO` 4 terakhir). Delta tabel:

- `settings (+storage_provider, storage_bucket, storage_endpoint, storage_keys_enc, storage_public_base_url), account_groups, accounts (+threads_user_id, oauth_token_id, account_tier, account_role, storage_state_enc), account_tags, account_status_history, account_stats_snapshots (kolom views/likes/replies/reposts/quotes), warmup_plans, proxies, media_library, scheduled_threads (PENGGANTI scheduled_posts; kolom text_rendered, topic_tag, reply_control, link_urls[5], container_id, published_threads_id), activities, activity_cursors, interactions (action ∈ like/follow/unfollow/reply/repost/quote), campaigns (+max_target_actions_per_minute, stance_distribution_json), campaign_participants, campaign_schedule, thread_conversations/messages (PENGGANTI dm_*; kolom is_hidden_by_platform, last_visibility_checked_at), reply_rules (PENGGANTI dm_rules), reply_campaigns/recipients (PENGGANTI dm_campaigns), jobs, job_runs, recurring_jobs, quota_usage (PK account,day TZ-akun,action + kolom bucket official: posts/replies/deletes/searches), activity_logs, alerts_history, ai_profiles/usage, personas, checkpoint_events, threads_tokens (baru), topic_sets/items (PENGGANTI hashtag_sets; 1-tag/post)`.
- DDL lengkap ditulis di implementasi Fase 0–1 mengikuti pola IGBuzzer `15-database-schema.md` (subset inti dulu: settings, groups, accounts, tags, history, proxies, threads_tokens, jobs, runs, logs).

---

# 16 — API Internal (backend ⇄ UI)

> Pola SAMA (127.0.0.1 + Bearer, ISO-8601 UTC, envelope error, paginasi 50/500, async→202, client TS dari OpenAPI, tanpa URL manual). Rename endpoint:

- System: info/shutdown/killswitch/diagnostics (sama).
- Accounts: CRUD, import/export, login/logout, checkpoint resolve, checkpoint-queue, bulk, details, groups, warmup-plans, profile-update (bio ≤150) + **`oauth/start, oauth/callback, oauth/refresh, oauth/status`**.
- Proxies: CRUD, import, test/test-all, auto-assign (sama).
- Engines: status + **`threads-tokens` CRUD/refresh/test** (PENGGANTI graph-tokens IG).
- Activities (growth): CRUD + pause/resume/stats/preview-targets (action ∈ like/follow/unfollow/reply/repost/quote).
- **Threads-posts** (PENGGANTI posts): CRUD + bulk-reschedule/import-manifest/quick-thread/repost/quote/first-reply + `publishing-limit` (baca kuota live) + media + **topic-sets** (+spam-check, PENGGANTI hashtag-check) + templates.
- **Replies** (PENGGANTI DM): conversations/messages/reply/mark-read, rules (+test), campaigns.
- Campaigns (+participants/simulate/start/pause/resume/stop/retry/add) — payload aksi threads.
- Analytics: dashboard, account/group series, threads (PENGGANTI posts), logs (+export), jobs (+retry/cancel), dead-letter.
- Alerts (+settings/test), AI (profiles/usage/test/personas/prompts), Settings/backup/export.
- WS `/ws?token=`: `job.updated, activity.created, account.status_changed, reply.new_message (PENGGANTI dm.new_message), campaign.progress (5 dtk), import.progress, alert.raised, system.stats (10 dtk), thread.updated (PENGGANTI post.updated)`, buffer 1000/tipe.

---

# 17 — UI/UX

> Struktur SAMA (sidebar + pola wajib). Rename halaman:

Sidebar: Dashboard, **Akun Threads**, Proxy, Growth, **Threads** (kalender/queue/media/**topic**/template — PENGGANTI Posting IG), **Balasan** (inbox 3-panel/rules/mass-reply — PENGGANTI DM), Kampanye, Analytics, AI, Pengaturan.

- Pola wajib SAMA: tabel virtual + sort server + filter chip + bulk bar, wizard stepper, editor spintax (tes render 3x + hitung **500 char** + hitung link ≤5 + 1 topic_tag), badge warna konsisten, live feed throttle, konfirmasi destruktif (ketik bila >20), empty/skeleton/error, waktu relatif+hover absolut, id default + en, dark default.
- Editor utas WAJIB: counter 500, peringatan link ke-6, dropdown `reply_control`, preview threadstorm (pecah per 500), tombol "cek kuota 250/1000" live.
- Tray SAMA (tampilkan/pause/resume/quit + tooltip antrian + balon critical, X→tray, single-instance, `Ctrl+K`, kill banner <1 dtk).
- Kontrol Manual (BrowserView `threads.com`, partisi per akun) SAMA — porsi dipakai LEBIH SERING (checkpoint + growth cadangan).

---

# 18 — Keamanan & Data

> Copy IGBuzzer §18, rename path + tambah token.

- Master key 32B di Credential Manager/keyring (DPAPI), AES-256-GCM nonce acak + AAD kolom+id via HKDF; hilang → dialog input ulang (tanpa backdoor).
- Layout `%APPDATA%/THBuzzer/{db,sessions,media,logs/screenshots,backups,config/app.toml}` (+`portable.flag→data/`).
- Backup kredensial + **OAuth token** wajib passphrase.
- IPC: token 256-bit/sesi, tidak ke disk, filter `THBUZZER_READY`, sandbox renderer, BrowserView partisi per akun, tolak Origin non-localhost.
- Log: redaksi password/token/cookie, INFO default, screenshot hanya `E-ENGINE-BUG`. Nol telemetri. Uninstall opsi hapus semua + key.

---

# 19 — Anti-Detection & Velocity Limit

> Kerangka SAMA (jitter/break/night-pause/IP-cap/warm-up), ANGKA BARU — JANGAN copy IG. Alasan: Threads lebih ketat di reply/quote berulang + search dijatah mingguan.

## 19.1 Prinsip

Default konservatif; limiter 3 lapis tidak bisa mati; jitter wajib; warm-up ditawarkan; karantina otomatis; UI jujur.

## 19.2 Jitter & Pola (sama struktur, rentang dilonggarkan)

Delay antar-aksi se-akun **60–240 dtk** (vs 40–180 IG), break 15–45 mnt tiap 15–30 aksi, variasi harian ±30%, night pause 22–08 TZ-akun, per-IP 6 aksi/mnt, global 120/mnt.

## 19.3 Fingerprint & Sesi (lihat §5.4–5.5)

## 19.4 Captcha

Funcaptcha IG jarang di threads.com → generik rate-limit solver + jeda; screenshot + antre manual bila muncul.

## 19.5 Tabel Velocity Dewasa/Hari (AKUN >30 HARI, warm-up lulus) — [AWAL, kalibrasi ulang via QA akun uji]

| Aksi | Aman/hari | Maks saran | Catatan |
|---|---|---|---|
| thread teks (official) | 5 | 10 | Jauhi 250 kuota resmi — reputasi ≪ kuota |
| thread image/carousel/video | 3 | 8 | ≤8 MB / ≤300 dtk / 2–20 item |
| reply | 10 | 20 | (IG comment 30/50 → turun 3x; unik wajib) |
| repost | 10 | 20 | — |
| quote | 5 | 10 | rewrite unik wajib |
| like | 50 | 100 | (IG 100/150 → turun 2x awal) |
| follow | 20 | 50 | (IG 100/150 → turun 4x awal) |
| unfollow | 15 | 30 | hanya followed_by_us |
| sapa follower baru | 10 | 20 | 1x/follower |
| edit profil | 1 | 2 | — |
| keyword search resmi | 30 | 70 | hemat — 500/minggu; default via unofficial |
| Per-jam | 20% harian | — | — |
| Akun <30 hari | 30% tabel | — | — |
| Cooldown restricted | 24 jam ±6 | 2x/7 hari → 72 jam | `4279013` tanpa retry |

Turunan WAJIB: per-jam 20%, jitter 60–240 dtk, break tiap 15–30 aksi, night pause, IP 6/mnt, global 120/mnt, serta **Target-Side Pacing Guard (3–6 aksi/menit per URL target)**. Aksi keyword search dan follower scraping WAJIB dibatasi hanya untuk akun role **`scout`** (akun `actor` dilarang melakukan scraping). Naikkan hanya bertahap + catat DECISIONS.md + uji akun burner dulu.

---

# 20 — Non-Functional & Packaging

> Copy IGBuzzer §20, rename biner.

- Startup ≤5 dtk, API p95 ≤100 ms, 1000+ akun tanpa drop, idle ≤400 MB, +≤300 MB/100 akun, context browser ephemeral Playwright 150–250 MB saat running (~20 KB storageState di disk per akun), job 100% tahan restart, log ≤500 MB.
- PC: ≤50 (4c/8GB/20GB), 51–500 (8c/16GB/50GB), 501–2000 (12c+/32GB/100GB), >2000 (16c+/64GB/NVMe).
- PyInstaller `onedir` (`thbuzzer-core.exe`) + ffmpeg + stealth; Chromium `resources/browser` (target ≤500 MB); electron-builder NSIS x64 (`THBuzzer.exe`); tanpa signing (dokumentasikan SmartScreen); tanpa auto-update (cek manual); `scripts/build.ps1` 1 perintah + sha256; SemVer; portable mode; **Job Object `KILL_ON_JOB_CLOSE 0x2000`** anti-zombie.

---

# 21 — Testing & Acceptance

> Strategi SAMA (pytest+respx, mock engine, simulasi skala). Kriteria diadaptasi:

- [ ] Tambah akun manual (pilih tier brand/buzzer & role scout/actor) → `active` ≤60 dtk (mock).
- [ ] OAuth connect + refresh H-50 untuk tier `brand_official` (mock 401→refresh→retry 1x).
- [ ] Container flow: create→FINISHED→publish sukses; simulasi `500-yang-sudah-publish` → guard dobel mencegah dobel-post.
- [ ] Solusi media: presigned URL S3/R2 sukses dibuat dan ditarik Meta container, atau fallback otomatis direct DOM upload via Playwright jika R2 belum dikonfigurasi.
- [ ] Threadstorm: linear chaining terbukti (`reply_to_id` menunjuk post sebelumnya); simulasi post ke-3 gagal → sisa post (4+) di-pause dengan status `threadstorm_interrupted`.
- [ ] Validator tolak teks >500 / link >5 / topic_tag invalid / reply ke post `mentioned_only`.
- [ ] Topic Tag auto-sanitizer: teks input dengan `#a #b #c` otomatis terekstrak menjadi 1 tag `a` dan sisa teks bersih dari simbol `#`.
- [ ] Target-side pacing: kampanye 500 akun dibatasi laju interaksinya (maks 3–6 aksi/menit per URL target).
- [ ] Kuota 250/1000 habis → job `held` besok (mock `threads_publishing_limit`), health TIDAK turun.
- [ ] `4279013` → `restricted`, tanpa retry, cooldown + alert.
- [ ] Hidden Replies detection: balasan bot yang disembunyikan platform terdeteksi oleh auditor dan memicu soft-warning.
- [ ] Import CSV 100 baris (10 invalid) → 90 antre + laporan 10.
- [ ] Restart tengah 5000 job → 0 hilang/dobel (simulasi `scripts/scale-sim.py` 1000 akun × 5000 job).
- [ ] Kampanye 500 mock → distribusi deterministik + pause/resume deterministik + pre-flight abort saat target privat/deleted.
- [ ] Reply-rule 3/24 jam anti-loop + skip sesama kelolaan.
- [ ] Fingerprint stabil setelah restart; sesi browser ephemeral berhasil di-restore dari `storageState.json`.
- [ ] Check hijau (ruff+mypy+pytest) tiap gate fase.

---

# 22 — Roadmap Implementasi (Fase 0–6)

> Urutan SAMA seperti IGBuzzer §22. Beda isi per fase (browser porsi naik, DM diganti replies).

- **F0 Fondasi (10%):** repo+handshake `THBUZZER_READY`+tabel inti (settings [+storage_settings], groups, accounts [+tier/role/storage_state], tags, history, proxies, threads_tokens, jobs, runs, logs)+settings+tray+build/check+FakeEngine → installed + "backend connected".
- **F1 Akun/Proxy/Official (20%):** login/2FA/checkpoint/fingerprint/sesi/health + **OAuth wizard + refresh + `threads_publishing_limit` guard** + router tiering (brand vs buzzer, scout vs actor) + enkripsi (termasuk token & storage_state).
- **F2 Task+Growth (20%):** queue/retry/kuota/kill/recurring + limiter 3 lapis + warm-up + growth like/follow/reply via Playwright browser engine & unofficial (spintax) → MVP.
- **F3 Threads Posting (15%):** library/ffmpeg/kalender/manifest/**container-flow + guard-dobel**/solusi media R2 & DOM fallback/topic-tag auto-sanitizer/first-reply/quick-thread/repost/quote/threadstorm recovery.
- **F4 Replies+AI (12%):** unified replies-inbox/rules/mass-reply + provider/persona/budget (**quote_rewrite** + **stance distribution** termasuk) + **Visibility Auditor (Hidden Replies detector)**.
- **F5 Campaign+Analytics (13%):** distribusi deterministik + **target-side velocity pacing** + pre-flight `reply_control` + top-reply amplification + snapshot/views-likes-replies-reposts-quotes + dashboard/alert (termasuk alert kuota 250/1000 + search-mingguan).
- **F6 Hardening+Browser-Optimization+Packaging (10%):** pool ephemeral Playwright context (`storageState.json`) + stealth/humanize threads.com/captcha-generik + backup + NSIS final + QA nyata + kalibrasi §19.5 via akun burner.
- Gate tiap fase = DoD + check hijau; simulasi 1000 akun & kampanye 500 mock wajib lulus. Jangan lompat fase.

---

# 23 — Petunjuk AI Agent (aturan kerja)

> Copy IGBuzzer §23, rename.

1. Baca 01→24 berurutan; keputusan [TERKUNCI] tidak boleh diubah tanpa pemilik.
2. RFC 2119 Bahasa Indonesia (WAJIB/TIDAK BOLEH/SEBAIKNYA/BOLEH).
3. Ambigu → pilih paling konservatif (paling aman akun), catat ke `DECISIONS.md` + tandai review manusia.
4. Ikuti roadmap §22; jangan lompat fase sebelum gate lulus.
5. Kontrak OpenAPI → regenerasi TS client tiap ubah endpoint; tanpa URL manual.
6. Tanpa `create_all` prod (Alembic saja); tanpa log kredensial/token; tanpa dobel-publish (verifikasi container sebelum retry).
7. Angka §19.5 hanya boleh DINAIKKAN via QA burner + catat alasan; tidak boleh copy angka IG.
8. Unofficial naik versi hanya sadar (breaking sering) + smoke test.
9. Bahasa kode English, string UI via i18n `id` default.

---

# 24 — Rekomendasi Arsitektur & Operasional (lanjut, non-blokir v1)

> Pararel IGBuzzer §24 (mobile-proxy rotasi, SMS OTP, pre-flight, sleep-recovery, job-object, Telegram remote, disk-quota, single-writer) + 6 khusus Threads:

1. **Hemat search mingguan (Role Scout):** default semua riset target didelegasikan ke 1–3 akun role `scout` via unofficial/browser; official `keyword_search` hanya untuk verifikasi akhir + bit `search_budget_guard` (tolak aktivitas baru bila sisa <20% dengan pesan jelas). Akun `actor` dilarang melakukan pencarian aktif.
2. **Verifikasi-sebelum-retry container:** setiap `publish_thread/reply` yang gagal setelah `threads_publish` WAJIB `GET` daftar post terbaru (hash 6 terakhir) sebelum retry — cegah kasus "500 yang sebenarnya sudah publish".
3. **Penyimpanan Browser Ringan (`storageState.json`):** jangan gunakan folder `user_data_dir` penuh untuk ratusan akun buzzer. Gunakan ephemeral context Playwright yang mengimpor dan mengekspor `storageState.json` (cookies + localStorage) terenkripsi untuk menghemat hingga 95% ruang disk.
4. **Cloudflare R2 untuk Media Container Official:** integrasikan Cloudflare R2 untuk akun `brand_official` karena memiliki free-tier 10 GB dan tanpa biaya transfer keluar (zero egress fee), ideal untuk hosting gambar/video sementara selama container Meta dibuat.
5. **Target-Side Pacing pada Kampanye:** selalu tetapkan laju interaksi maksimal 3–6 aksi/menit per URL target untuk melindungi thread target dari deteksi lonjakan anomali spam Meta.
6. **Relay webhook opsional (pasca-v1):** bila butuh inbox <15 mnt, sediakan relay publik kecil (VPS) yang meneruskan webhook reply/mention resmi → polling lokal tetap sebagai fallback. Tanpa relay, jangan janjikan real-time.

---

# Lampiran A — Matriks Engine × Aksi (ringkas)

| Aksi | official_api | private_unofficial | browser |
|---|---|---|---|
| thread teks/gambar/video/carousel | ✅ utama brand (via R2) | ⚠️ cadangan | ✅ utama buzzer (direct upload) |
| reply / first_reply | ✅ utama brand | ⚠️ fragile | ✅ utama buzzer |
| quote / repost | ✅ (quote via container) | ⚠️ | ✅ |
| delete / hide-reply | ✅ | ❌ | ⚠️ |
| like / follow / unfollow | ❌ (tidak didukung Meta) | ⚠️ fragile | ✅ utama |
| search luas / followers / likers | ⚠️ jatah mingguan | ⚠️ fragile | ✅ utama (khusus Scout) |
| insights | ✅ terbaik | ⚠️ | ❌ |
| checkpoint/manual | ❌ | ⚠️ | ✅ utama (BrowserView) |
| DM | ❌ tidak ada | ❌ | ❌ (gunakan IGBuzzer) |

# Lampiran B — Mapping IGBuzzer → THBuzzer (rename cepat)

`IGBuzzer→THBuzzer, igbuzzer→thbuzzer, IGBUZZER_READY→THBUZZER_READY, %APPDATA%/IGBuzzer→%APPDATA%/THBuzzer, private_api→official_api (+private_unofficial baru), graph_api→(lebur ke official_api), comment→reply, first_comment→first_reply, dm_*→reply_*, posts→threads-posts, scheduled_posts→scheduled_threads, hashtag→topic_tag, story/reels/save/view_story/poll→hapus, checkpoint→checkpoint/restricted(4279013), action_blocked→restricted`
