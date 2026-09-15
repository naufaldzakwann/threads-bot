# THBuzzer — decisions log (aturan §23.3: ambigu -> paling konservatif + catat + tandai review)

## 2026-09-15 — Fase 0 bootstrap
- Official engine default httpx (tanpa SDK berat) agar PyInstaller ringan; `threads-python-sdk` opsional bila lolos uji bundel.
- Browser: `patchright`/stealth dipilih saat F6; F0-F2 Playwright polos + storageState ephemeral.
- Unofficial private diperlakukan fragile: default nonaktif, 3x E-ENGINE-BUG -> degraded 24 jam + fallback browser.
- DB bootstrap dev memakai create_all; prod WAJIB Alembic (lihat alembic/). [review manusia: tuliskan migrasi awal]
- Text attachment 10k char ditolak validator (bukan dicangkok diam-diam).
- Angka §19.5 dipakai sebagai default awal; kenaikan hanya via QA burner.
