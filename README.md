# THBuzzer — Threads Bot Desktop Multi-Akun (Windows)

Tool internal single-operator paralel **IGBuzzer**, untuk ratusan–ribuan akun **Threads** dari satu panel:
manajemen akun & proxy, growth automation, scheduling utas, **reply & mention automation (pengganti DM — Threads tidak punya DM via API)**, kampanye buzzer, analytics. **100% lokal** di PC.

> Spec lengkap: `SPEC-LENGKAP-THBuzzer.md` (adaptasi 1:1 dari `../instagram-bot/SPEC-LENGKAP-IGBuzzer.md`).
> Stack, arsitektur 2-proses, task engine, keamanan, NFR: sama. Yang beda: engine Threads, limit 500-char/250-post/1000-reply, reply-inbox, topic_tag.

## Stack [TERKUNCI]
- Backend: **Python 3.12 + FastAPI + uvicorn**, Pydantic v2, SQLAlchemy 2.0 async + aiosqlite (WAL), Alembic
- UI: **Electron + React 18 + TypeScript + Ant Design 5**, Vite 5, react-query, zustand, ECharts, i18n (id default)
- Engine: **Official `graph.threads.net/v1.0` (httpx)** + **Unofficial Private (pin sadar)** + **Browser Playwright (threads.com)**

## Handshake backend ⇄ UI
1. Electron spawn `thbuzzer-core.exe --headless` (+ `THBUZZER_PARENT_PID`).
2. Backend port acak 127.0.0.1 + stdout: `THBUZZER_READY {"port":..,"token":"..","pid":..,"version":".."}`.
3. Renderer REST via `http://127.0.0.1:<port>` + `Authorization: Bearer <token>`.
4. Quit: `POST /system/shutdown` → flush ≤15 dtk → exit.

## Batas resmi yang dipegang teguh (2026)
- 250 post / 1000 reply / 100 delete / 24 jam per profil + 500 keyword-search / 7 hari + budget 4800×impressions.
- Teks 500 char, ≤5 link, 1 topic_tag, carousel 2–20, video ≤5 mnt/1 GB, gambar ≤8 MB.
- Publish 2-langkah (container → poll FINISHED → publish); retry WAJIB verifikasi dulu (anti dobel-post).
- `4279013 restricted` = non-retryable, cooldown 24 jam.

## Disclaimer (first-run wajib)
Unofficial + browser automation melanggar ToS — risiko restricted/checkpoint/suspend. Default konservatif (§19.5 JANGAN copy angka IG); limiter tidak bisa dimatikan total.
