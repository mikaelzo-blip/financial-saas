# Task Remediasi Audit 2026-10-07 — dieksekusi Hermes Coder, diorkestrasi Claude

Sumber: audit mendalam `main` @ `690e761` (2026-10-07). Setiap task kecil, berdiri sendiri, dan
punya kriteria terima yang bisa diverifikasi.

**Peran:**
- **Hermes Coder** mengeksekusi T01–T17 (implementasi, tes, verifikasi, PR).
- **Claude** adalah orchestrator: menetapkan urutan dan antrean di `PROJECT_STATUS.md`, mengaudit
  setiap PR, dan memberi putusan merge.
- **Pemilik (user)** memutuskan item kebijakan D1–D9.

Dokumen ini adalah artefak task yang disetujui pemilik untuk batch remediasi ini (setara
`tasks.md` + klarifikasi yang disetujui dalam urutan otoritas `AGENTS.md`). Setiap task adalah
*contained bug fix*: ikuti jalur BUG FIX di `.hermes/skills/financial-saas-orchestrator/SKILL.md`
(reproduksi → tes regresi → perbaikan terkecil → verifikasi). Tidak perlu siklus Spec Kit penuh
per task, **kecuali** task ternyata membutuhkan kebijakan bisnis baru — saat itu berhenti dan
laporkan (lihat aturan 1).

---

## 0. Aturan main (WAJIB dibaca sebelum task apa pun)

1. Baca `AGENTS.md` dan `.specify/memory/constitution.md`. Urutan otoritas di `AGENTS.md` berlaku.
   **Jangan menciptakan kebijakan akuntansi baru.** Kalau sebuah task ternyata butuh keputusan
   kebijakan, berhenti dan tulis pertanyaannya di deskripsi PR — jangan menebak.
2. **Satu task = satu branch = satu PR** (satu-satunya pengecualian: T01 dan T02 digabung, lihat tabel urutan).
   - Branch: `hermes/<ID>-<slug>` dibuat dari `origin/main` terbaru (contoh `hermes/T03-review-flag-posted`).
   - Judul PR diawali ID task: `[T03] fix(review): ...`.
   - Base PR: `main`. Jangan force-push, jangan push ke `main`.
   - **Gerbang merge batch ini (instruksi pemilik, berlaku di atas langkah 8 skill orchestrator):**
     PR **tidak boleh di-squash-merge**, walau CI hijau, sebelum ada komentar
     `Claude audit: APPROVE` dari Claude di PR tersebut. Setelah APPROVE dan CI hijau, Hermes
     boleh squash-merge lalu sinkronkan `main`. Jika putusannya `REQUEST CHANGES`, perbaiki di
     branch yang sama lalu minta audit ulang.
3. Ubah **hanya** file yang disebut di task. Kalau terpaksa menyentuh file lain, jelaskan alasannya
   di PR. Jangan refactor di luar scope.
4. **Dilarang melemahkan tes** (menghapus assert, menambah skip/xfail, melonggarkan nilai yang
   diharapkan) supaya hijau. Pengecualian satu-satunya: T01, yang memang memperbaiki tes yang salah.
5. Setiap perubahan perilaku wajib disertai tes regresi yang **gagal sebelum** perbaikan dan
   **lulus sesudahnya**. Tulis output kedua kondisi itu di PR.
6. Uang selalu `Decimal`/`NUMERIC`, tidak pernah `float`.
7. Pesan error ke pengguna mengikuti gaya yang sudah ada (`InvariantViolationException` → HTTP 422).
8. Jangan menyentuh database produksi, secret, `.env`, atau layanan berbayar. Di Finance PC,
   container `financial-saas-postgres` (port 5432) berisi data operasional — **jangan pernah**
   menjalankan tes, migrasi uji, atau probe terhadapnya. Gunakan hanya DB sekali pakai di bawah.
9. Jangan perbarui `PROJECT_STATUS.md` di PR task. Status antrean dikelola orchestrator; kemajuan
   diukur dari PR `[Txx]` yang sudah merge ke `main` (Git adalah sumber kebenaran).

### Urutan dan ketergantungan

| Gelombang | Task | Catatan |
|---|---|---|
| 1 (buka blokir CI) | T01, T02 | Kerjakan dalam **satu PR** `[T01+T02]` (dua commit terpisah) di branch `hermes/T01-T02-unblock-ci`: PR salah satunya saja tetap merah karena kegagalan yang diperbaiki yang lain. Harus merge dulu; tanpa ini semua PR lain merah. |
| 2 (independen) | T03, T04, T06, T07, T08, T09, T11, T12, T13, T14, T15, T16, T17 | Kerjakan sesuai urutan nomor. Boleh lanjut ke task berikutnya saat PR sebelumnya menunggu audit, **maksimal 3 PR terbuka** sekaligus. |
| 3 (berurutan — migrasi Alembic) | T05 → T10 | Rantai migrasi harus linear; T10 dikerjakan setelah T05 di-merge dan juga setelah T09. |

### Lingkungan verifikasi (dipakai semua task backend)

Port **55432** dipakai supaya tidak bentrok dengan `financial-saas-postgres` (5432). Contoh di
bawah memakai bash; di PowerShell ganti `export X=...` dengan `$env:X = "..."` dan
`.venv/bin/python` dengan `.venv\Scripts\python`.

```bash
# PostgreSQL 16 sekali pakai (hapus setelah selesai: docker rm -f fin-audit-pg)
docker run -d --name fin-audit-pg -p 55432:5432 \
  -e POSTGRES_USER=fin001_ci_user -e POSTGRES_PASSWORD=fin001_ci_password \
  -e POSTGRES_DB=fin001_ci_disposable postgres:16

cd backend
uv sync --locked --extra test
export U=postgresql+asyncpg://fin001_ci_user:fin001_ci_password@127.0.0.1:55432/fin001_ci_disposable
export SLICE5_TEST_DATABASE_URL=$U FIN_001_TEST_DATABASE_URL=$U RECON_001_TEST_DATABASE_URL=$U \
       FEATURE_012_TEST_DATABASE_URL=$U LIVE_POSTGRES_URL=$U DATABASE_URL=$U
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check                     # harus: No new upgrade operations detected
.venv/bin/python -m pytest -q -p no:cacheprovider    # suite penuh
```

Probe regresi (menguji perilaku lewat API asli + login JWT). Pakai DB terpisah karena probe
meninggalkan data:

```bash
docker exec fin-audit-pg createdb -U fin001_ci_user fin_audit_disposable
DATABASE_URL=postgresql+asyncpg://fin001_ci_user:fin001_ci_password@127.0.0.1:55432/fin_audit_disposable \
  .venv/bin/python -m alembic upgrade head
AUDIT_PROBE_DATABASE_URL=postgresql+asyncpg://fin001_ci_user:fin001_ci_password@127.0.0.1:55432/fin_audit_disposable \
  .venv/bin/python ../tools/audit/regression_probe.py
```

Baris probe untuk ID task Anda harus berubah dari `DEFECT` menjadi `OK`, dan baris lain tidak
boleh berubah dari `OK` menjadi `DEFECT`.

### Template deskripsi PR

```
## Task
T0x — <judul>

## Perubahan
- ...

## Bukti
- Tes regresi baru: <nama tes> — GAGAL sebelum perubahan (tempel output), LULUS sesudahnya (tempel output)
- Suite penuh: <N passed, M skipped, 0 failed>
- alembic check: <output>  (jika menyentuh model/migrasi)
- Probe: baris T0x = OK (tempel baris)

## Penyimpangan dari task / pertanyaan
- (kosongkan jika tidak ada)
```

---

## Gelombang 1 — buka blokir CI

### T01 — Perbaiki tes "bom waktu" (tanggal hardcoded)
- **Masalah:** sejak 2026-10-01 dua tes gagal karena memakai tanggal tetap `2026-09-01`/`2026-09-02`
  dengan termin 30 hari, sedangkan status jatuh tempo dihitung dari `date.today()`
  (`backend/src/api/v1/receivables.py:87`, `backend/src/api/v1/payables.py:84`).
  - `tests/integration/test_customer_invoice_uat.py::test_customer_invoice_api_exposes_ar_subledger`
  - `tests/integration/test_vendor_bill_uat.py::test_vendor_bills_list_api_returns_persisted_bills`
- **Perubahan:** buat tanggal di tes relatif terhadap hari ini (mis. `date.today()` dan
  `date.today() + timedelta(days=30)`) **atau** patch `date.today()` di modul API menjadi tanggal
  tetap. Nilai yang diharapkan (`NOT_DUE`, jumlah, kode) tidak boleh dilonggarkan.
- **File:** hanya kedua file tes di atas.
- **Terima jika:** kedua tes lulus hari ini **dan** tetap lulus saat jam sistem dimajukan 1 tahun
  (buktikan dengan `faketime` atau patch tanggal, tempel outputnya di PR).
- **Commit:** `test(ar-ap): make due-status UAT tests independent of the current date`

### T02 — Upgrade dependensi rentan backend
- **Masalah:** `pip-audit --strict` (gate CI) gagal dengan 25 kerentanan: `pyjwt 2.13.0` (perbaikan di
  2.14.0/2.15.0), `pypdf 6.16.2` (perbaikan di 6.19.0), `urllib3 2.7.0` (perbaikan di 2.8.0).
- **Perubahan:**
  - Naikkan batas bawah di `backend/pyproject.toml`: `pyjwt[crypto]>=2.15.0`, `pypdf>=6.19.0`.
  - `uv lock --upgrade-package pyjwt --upgrade-package pypdf --upgrade-package urllib3`.
  - `PYSEC-2026-4146` (pyjwt, GHSA-gvp8-978c-rx2q) **tidak punya versi perbaikan**. Kerentanan ini
    hanya berdampak bila `decode()` dipanggil dengan dict `options` yang dipakai ulang dan
    `verify_signature` bernilai falsy; `backend/src/core/security.py:70` tidak pernah mengirim
    `options`. Jika versi terbaru masih terdampak, tambahkan `--ignore-vuln PYSEC-2026-4146` pada
    langkah pip-audit di `.github/workflows/quality-gates.yml`, **dengan komentar YAML** yang
    menjelaskan alasan di atas. Jangan meng-ignore ID lain.
- **File:** `backend/pyproject.toml`, `backend/uv.lock`, (jika perlu) `.github/workflows/quality-gates.yml`.
- **Terima jika:** perintah audit CI lulus:
  `uv export --locked --no-dev --no-emit-project --format requirements-txt -o /tmp/req.txt && uvx pip-audit==2.9.0 -r /tmp/req.txt --strict`;
  `uv sync --locked --extra test` dan `python -m pip check` bersih; suite penuh hijau.
- **Commit:** `chore(deps): upgrade pyjwt, pypdf and urllib3 to patched releases`

---

## Gelombang 2 — perbaikan independen

### T03 — Review flag tidak boleh mengubah transaksi yang sudah POSTED
- **Masalah (terbukti):** OPERATOR dapat memanggil `POST /transactions/{id}/review-flags` pada
  transaksi POSTED; status berubah ke `REVIEW_REQUIRED` (lalu `STAGED` setelah di-resolve), dan
  reversal menjadi tertolak. Lokasi: `backend/src/services/review_service.py:61-96` (`add_review_flag`).
- **Perubahan:**
  - Di `add_review_flag`, tolak dengan `InvariantViolationException` (422) jika status transaksi
    `POSTED`, `RECONCILED`, atau `REVERSED`. Pesan: koreksi transaksi terposting harus lewat reversal.
  - Tambah parameter `actor_id` ke `add_review_flag`, isi dari `current_user.id` di
    `backend/src/api/v1/review.py`, dan teruskan ke `audit_service.log_event(..., actor_id=...)`.
- **File:** `review_service.py`, `api/v1/review.py`, tes baru di `backend/tests/unit/` atau `tests/integration/`.
- **Tes wajib:** (a) flag pada POSTED → 422 dan status tetap POSTED; (b) flag pada STAGED tetap
  berfungsi seperti sebelumnya; (c) audit log flag mencatat `actor_id`.
- **Probe:** baris `T03` = OK.
- **Commit:** `fix(review): reject review flags on posted or reversed transactions`

### T04 — Tolak reversal atas transaksi bertipe REVERSAL
- **Masalah (terbukti):** reversal dari transaksi REVERSAL diterima (201), sehingga dampak GL
  muncul lagi sementara invoice/bill sudah `CANCELLED` dan alokasi sudah dihapus.
- **Perubahan:** di `ReversalService.reverse_transaction`
  (`backend/src/services/reversal_service.py`, setelah pengecekan status POSTED) tolak dengan 422
  jika `original_trx.transaction_type == TransactionType.REVERSAL` atau `original_trx.reversal_of_id`
  tidak `None`. Pesan: buat transaksi koreksi baru, bukan membalik reversal.
- **Tes wajib:** reversal kedua → 422; jumlah journal entry dan status transaksi asal tidak berubah.
- **Probe:** baris `T04` = OK.
- **Commit:** `fix(reversal): forbid reversing a reversal transaction`

### T06 — Validasi status sebelum approve/post (tidak boleh 500)
- **Masalah (terbukti):** `ProcessingPolicyService.authorize_and_post`
  (`backend/src/services/processing_policy_service.py:127-129`) menimpa status menjadi `APPROVED`
  **sebelum** validasi, sehingga pemeriksaan "already posted" di `AccountingEngine.post_transaction`
  tidak pernah jalan. Approve ulang transaksi POSTED menghasilkan **HTTP 500** (hanya tertahan
  unique constraint DB). Status `REJECTED` juga tidak dijaga.
- **Perubahan:**
  - Di `authorize_and_post`, segera setelah transaksi dimuat dan sebelum mengubah apa pun: izinkan
    hanya `STAGED` dan `APPROVED`; selain itu raise `InvariantViolationException` (422) dengan
    `details={"status": ...}`.
  - Di `AccountingEngine.post_transaction` (`accounting_engine.py:68-79`) ganti blacklist status
    menjadi whitelist yang sama (`STAGED`, `APPROVED`), dengan pesan khusus untuk `POSTED`.
- **Perhatian:** pemanggil yang sah memakai `STAGED` (TransactionService, opening balance, retensi,
  posting dokumen) dan `APPROVED` (penyusutan aset). Jalankan suite penuh untuk memastikan tidak ada
  jalur lain yang rusak; jika ada, laporkan di PR — jangan menambah status ke whitelist tanpa alasan.
- **Tes wajib:** approve ulang POSTED → 422; approve REVERSED → 422; approve REJECTED → 422; jalur
  normal STAGED → POSTED tetap 200.
- **Probe:** baris `T06` = OK.
- **Commit:** `fix(posting): validate workflow status before approval and posting`

### T07 — Catat `created_by` dan audit pembuatan transaksi
- **Masalah (terbukti):** `POST /transactions` memanggil `create_transaction(org_id, data)` tanpa
  `created_by` (`backend/src/api/v1/transactions.py:35`), sehingga pembuat selalu NULL; pembuatan
  transaksi juga tidak tercatat di audit log.
- **Perubahan:**
  - Teruskan `created_by=current_user.id` di endpoint.
  - Di akhir `TransactionService.create_transaction`, tulis audit event `CREATE` (entity
    `transactions`, `actor_id=created_by`, `new_values` berisi kode, tipe, tanggal, `amount` sebagai
    string, status awal).
- **Tes wajib:** transaksi dari API memiliki `created_by` = user login; ada tepat satu audit `CREATE`.
- **Probe:** baris `T07` = OK. (Baris `D1` tetap DECISION — jangan menambah aturan maker/checker.)
- **Commit:** `fix(transactions): record creator and audit transaction creation`

### T08 — Audit pembuatan dan perubahan status periode akuntansi
- **Masalah (terbukti):** buat/tutup/buka-ulang periode menghasilkan 0 baris audit; alasan reopen
  diminta tapi dibuang (`backend/src/services/accounting_period_service.py:35-90`).
- **Perubahan:** tambah parameter `actor_id` pada `create_period`; tulis audit event
  `CREATE` di `create_period` dan `STATUS_CHANGE` di `update_period_status` dengan
  `old_values={"status": lama}`, `new_values={"status": baru}`, `reason=update_data.reason`.
  Teruskan `actor_id=current_user.id` dari `backend/src/api/v1/accounting_periods.py`.
- **Tes wajib:** create + close + reopen → 3 baris audit; baris reopen menyimpan alasan; status yang
  tidak berubah (no-op) tidak menulis audit.
- **Probe:** baris `T08` = OK.
- **Commit:** `fix(periods): audit accounting period creation and status changes`

### T09 — `SUBCONTRACTOR_BILL` dan `PAY_SUBCONTRACTOR` wajib masuk subledger AP
- **Masalah (terbukti):** `SUBCONTRACTOR_BILL` meng-kredit GL 2101 tetapi tidak membuat `VendorBill`,
  karena engine hanya menangani `VENDOR_BILL` (`backend/src/services/accounting_engine.py:159`).
  `allocate_vendor_payment` hanya menerima `PAY_VENDOR_BILL` (`payable_service.py`), dan reversal
  hanya membatalkan bill untuk `VENDOR_BILL` (`reversal_service.py:112`).
- **Perubahan:**
  - Engine: blok pembuatan `VendorBill` berlaku untuk `VENDOR_BILL` **dan** `SUBCONTRACTOR_BILL`.
  - `allocate_vendor_payment`: terima `PAY_VENDOR_BILL` **dan** `PAY_SUBCONTRACTOR`.
  - Reversal: cabang pembatalan bill + cek alokasi berlaku untuk kedua tipe bill.
- **Tes wajib:** posting `SUBCONTRACTOR_BILL` → tepat 1 `VendorBill` dengan amount sama; pembayaran
  `PAY_SUBCONTRACTOR` bisa dialokasikan ke bill itu; reversal bill tanpa pembayaran → `CANCELLED`;
  saldo GL 2101 sama dengan total outstanding subledger dalam skenario tes.
- **Probe:** baris `T09` = OK.
- **Commit:** `fix(ap): keep subcontractor bills and payments in the AP sub-ledger`

### T11 — Larang `JOURNAL_ADJUSTMENT` generik menyentuh akun kontrol subledger
- **Masalah (terbukti):** OPERATOR dapat membuat penyesuaian `DR:1201 / CR:4101` lewat
  `POST /transactions`, sehingga GL piutang bergerak tanpa invoice. Kode akun diambil dari teks bebas
  `notes` (`backend/src/services/posting_rules.py:422-458`).
- **Perubahan:** di `TransactionService.create_transaction`, khusus `JOURNAL_ADJUSTMENT`:
  - setiap allocation `notes` wajib cocok dengan regex `^(DR|CR):\d{4}$` (selain itu 422);
  - tolak (422) jika kode akun termasuk akun kontrol subledger
    `{"1201", "1202", "1301", "2101", "2201"}`;
  - wajib ada minimal satu leg DR dan satu leg CR.
- **Di luar scope:** `OpeningBalanceService` (tidak melewati `create_transaction`) — jangan diubah;
  saldo awal AR/AP adalah item keputusan D6. Jangan mengubah semantik field `amount`.
- **Tes wajib:** tiap aturan di atas punya tes tolak; penyesuaian valid antar-akun non-kontrol
  (mis. `DR:6199 / CR:6103`) tetap bisa dibuat dan diposting.
- **Probe:** baris `T11` = OK.
- **Commit:** `fix(adjustments): block generic adjustments on sub-ledger control accounts`

### T12 — Hardening edge-relay (fail-closed)
- **Masalah:** `edge-relay/src/index.ts` (belum dideploy, tapi ada skrip deploy):
  - POST `/webhook/whatsapp` tidak memverifikasi `X-Hub-Signature-256`;
  - allowlist gagal-terbuka: nomor yang **tidak** terdaftar diterima (`allowlistEntry !== null && ...`);
  - secret default `'dev-relay-secret'` dan `'financial-saas-wa-token'` bila env kosong;
  - perbandingan token tidak constant-time; pesan error internal dikembalikan ke klien.
- **Perubahan:**
  - Tambah env `WHATSAPP_APP_SECRET`; verifikasi HMAC-SHA256 atas **raw body** (baca `request.text()`
    sebelum `JSON.parse`) via `crypto.subtle`, bandingkan constant-time; gagal → 401.
  - Jika `RELAY_API_KEY`, `WHATSAPP_VERIFY_TOKEN`, atau `WHATSAPP_APP_SECRET` kosong → respons 503
    (tanpa nilai default).
  - Allowlist: terima hanya jika entri ada **dan** `is_active === 1`.
  - Perbandingan Bearer token constant-time.
  - Error 400 tidak memuat `err.message`.
  - Perbarui `edge-relay/README.md` (env baru).
- **Terima jika:** `cd edge-relay && npm install && npx tsc --noEmit` bersih (tambahkan `tsconfig.json`
  minimal bila belum ada); PR memuat contoh `curl` tanpa signature → 401, dan dengan signature valid → 200.
- **Commit:** `fix(edge-relay): verify webhook signatures and fail closed on missing secrets`

### T13 — `/inbox/capture` wajib memakai validasi upload yang sama
- **Masalah:** `RemoteInboxService.ingest_remote_capture` (`backend/src/services/remote_inbox_service.py:57-75`)
  menyimpan file base64 tanpa validasi MIME/magic-byte, ekstensi, dan batas ukuran yang dipakai
  `DocumentService.ingest_document` (`backend/src/services/document_service.py`, `ALLOWED_MIME_SIGNATURES`).
- **Perubahan:** ekstrak validasi di `ingest_document` menjadi fungsi modul yang bisa dipakai ulang
  (mis. `validate_document_upload(header_bytes, size, mime_type, file_name)`), panggil dari kedua
  tempat. Payload tidak valid → 422. Base64 tidak valid → 422 (bukan 500). Perilaku
  `ingest_document` tidak boleh berubah.
- **Tes wajib:** capture dengan `text/html`, ekstensi tidak cocok, file melebihi batas, dan base64
  rusak → 422; PDF/JPEG valid tetap diterima; tes document upload yang ada tetap hijau.
- **Commit:** `fix(inbox): apply document upload validation to remote captures`

### T14 — Default konfigurasi lokal yang aman
- **Masalah:** mode operasional nyata (Finance PC) berjalan dengan `ENVIRONMENT=development` dan
  `DEBUG=true`; `DEBUG` membuat SQLAlchemy meng-echo SQL beserta parameter data keuangan ke log
  (`backend/src/core/database.py:47`), dan `SECRET_KEY` disalin dari placeholder `.env.example`.
- **Perubahan:**
  - `backend/.env.example`: `DEBUG=false`.
  - `scripts/windows/Start-Financial-SaaS.ps1` (blok penyalinan `.env`, sekitar baris 113-116): saat
    membuat `backend/.env` pertama kali, ganti nilai `SECRET_KEY` dengan string acak ≥ 48 karakter
    (`[System.Security.Cryptography.RandomNumberGenerator]`), dan saat start tolak (throw) jika
    `SECRET_KEY` masih sama dengan placeholder `.env.example`.
  - `backend/src/core/database.py`: `echo` hanya aktif jika variabel baru `SQL_ECHO=true`
    (default false), bukan mengikuti `DEBUG`. Tambahkan field `SQL_ECHO: bool = False` di `config.py`.
- **Terima jika:** suite penuh hijau; PR menjelaskan cara memverifikasi skrip PowerShell (jalankan
  `pwsh` jika tersedia, atau sertakan potongan skrip yang diuji terpisah).
- **Commit:** `fix(config): safe local defaults for debug logging and secret key`

### T15 — Tes PostgreSQL `test_scenario_j` harus di-scope per organisasi
- **Masalah:** `tests/integration/test_fin001_cp3_retry_postgresql.py:821` mencari transaksi hanya
  berdasarkan `transaction_code`, sehingga gagal jika DB berisi data organisasi lain.
- **Perubahan:** tambahkan filter `Transaction.organization_id == org_id`. Periksa query sejenis di
  file yang sama dan perbaiki dengan cara yang sama.
- **Terima jika:** tes lulus walau DB sudah berisi transaksi dengan kode `TRX-2026-000001` milik
  organisasi lain (buktikan dengan menjalankan probe dulu, lalu tes ini).
- **Commit:** `test(fin001): scope sequence retry assertions to the test organization`

### T16 — Tolak reversal invoice yang retensinya sudah dilepas
- **Masalah:** `reverse_transaction` untuk `CUSTOMER_INVOICE` hanya mengecek alokasi pembayaran
  (`reversal_service.py:101-111`). Jika retensi sudah dilepas (`RETENTION_RELEASE`: Dr 1201 / Cr 1202),
  invoice dibatalkan sementara jurnal pelepasan retensi tetap ada → GL dan subledger tidak cocok.
- **Perubahan:** tolak (422) reversal `CUSTOMER_INVOICE` jika `invoice.retention_released_amount > 0`
  atau ada baris `CustomerRetentionRelease` untuk invoice itu. Pesan: balik pelepasan retensi dulu.
- **Tes wajib:** invoice dengan retensi dilepas → 422; invoice tanpa pelepasan retensi dan tanpa
  pembayaran tetap bisa direversal.
- **Commit:** `fix(reversal): block invoice reversal while retention releases exist`

### T17 — Tolak reversal transaksi penyusutan aset (sementara)
- **Masalah:** reversal `FIXED_ASSET_DEPRECIATION` membalik GL tetapi tidak mengubah
  `FixedAsset.accumulated_depreciation` maupun `FixedAssetDepreciation`, sehingga register aset dan GL
  berbeda; bulan yang sama juga tidak bisa disusutkan ulang (kode transaksi `DEP-...` unik).
- **Perubahan:** di `reverse_transaction`, tolak (422) tipe `FIXED_ASSET_DEPRECIATION` dengan pesan
  bahwa koreksi penyusutan memerlukan alur khusus aset. **Jangan** merancang alur itu (item D4).
- **Tes wajib:** reversal transaksi penyusutan → 422; register aset tidak berubah.
- **Commit:** `fix(reversal): block depreciation reversal until asset register sync exists`

---

## Gelombang 3 — migrasi (kerjakan berurutan)

> Setiap migrasi baru mengganti head Alembic. Perbarui semua referensi string
> `029_whatsapp_document_sessions` sebagai head yang diharapkan:
> `.github/workflows/quality-gates.yml` (2 tempat) dan konstanta `EXPECTED_ALEMBIC_HEAD`/sejenis di
> `backend/tests/integration/{fin001_postgresql_support,f012_postgresql_support,test_recon_001_postgresql_constraints,test_slice5_postgresql_concurrency,test_live_postgresql_schema,test_tenant_code_migration_postgresql}.py`
> dan `backend/tests/unit/test_whatsapp_migration.py` (cek dulu apakah tiap referensi memang "head
> yang diharapkan" sebelum diganti). Migrasi wajib punya `downgrade()` yang benar, dan
> `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`, `alembic check` harus bersih.

### T05 — Satu transaksi hanya boleh punya satu reversal (dijamin DB)
- **Masalah:** tidak ada unique constraint pada `transactions.reversal_of_id`, dan
  `reverse_transaction` tidak mengunci baris transaksi asal; keamanan saat ini hanya kebetulan dari
  lock sequence.
- **Perubahan:**
  - Migrasi `030_unique_reversal_of`: unique index parsial
    `uq_transactions_reversal_of_id ON transactions (reversal_of_id) WHERE reversal_of_id IS NOT NULL`.
    Sebelum membuat index, migrasi harus **gagal dengan pesan jelas** bila data duplikat sudah ada
    (jangan menghapus atau mengubah data).
  - Model `Transaction.__table_args__`: `Index(..., unique=True, postgresql_where=..., sqlite_where=...)`
    supaya `alembic check` bersih.
  - `reverse_transaction`: muat transaksi asal dan journal entry-nya dengan `.with_for_update()`.
  - Konflik unique pada jalur ini → 409/422 yang rapi, bukan 500.
- **Tes wajib (PostgreSQL):** 4 reversal paralel pada transaksi yang sama → tepat 1 sukses, sisanya
  409/422, tepat 1 baris reversal. Tambahkan ke file tes PostgreSQL yang sudah ada dan ke langkah CI
  bila file baru.
- **Probe:** baris `T05` = OK.
- **Commit:** `fix(reversal): enforce a single reversal per transaction in the database`

### T10 — Nomor tagihan vendor unik per vendor, bukan per organisasi
- **Prasyarat:** T05 dan T09 sudah merge (rantai migrasi + cabang `SUBCONTRACTOR_BILL`).
- **Masalah (terbukti):** engine memakai `transaction.reference_no` (nomor invoice dari vendor)
  sebagai `VendorBill.bill_code`, sedangkan constraint `uq_vendor_bills_org_code` unik per
  **organisasi**. Dua vendor dengan nomor "INV-001" → posting kedua **HTTP 500**. Sebaliknya, vendor
  yang sama mengirim nomor yang sama tidak ditandai duplikat.
- **Perubahan:**
  - Migrasi `031_vendor_bill_code_per_vendor`: ganti `uq_vendor_bills_org_code (organization_id, bill_code)`
    dengan `uq_vendor_bills_org_vendor_code (organization_id, vendor_id, bill_code)`; downgrade
    mengembalikan constraint lama (gagal jelas jika data tidak lagi memenuhi).
  - Perbarui model `VendorBill` dan peta `RETRYABLE_GENERATED_CODE_CONSTRAINTS` di
    `backend/src/services/transaction_retry.py` ke nama constraint baru.
  - `TransactionService.create_transaction`: untuk `VENDOR_BILL`/`SUBCONTRACTOR_BILL` dengan
    `reference_no`, jika sudah ada transaksi tipe bill dengan vendor + `reference_no` sama di
    organisasi itu → status `REVIEW_REQUIRED` dengan flag `DUPLICATE_SUSPECTED` (pola yang sama
    seperti invoice pelanggan di file tersebut).
- **Tes wajib:** dua vendor, nomor sama → keduanya terposting; vendor sama, nomor sama → transaksi
  kedua `REVIEW_REQUIRED`; tes migrasi upgrade/downgrade di PostgreSQL.
- **Probe:** kedua baris `T10` = OK.
- **Commit:** `fix(ap): scope vendor bill numbers per vendor and flag duplicates`

---

## Bukan untuk Hermes — butuh keputusan pemilik bisnis atau desain dari Claude

| ID | Topik | Yang dibutuhkan |
|---|---|---|
| D1 | Maker/checker | Apakah pembuat transaksi boleh meng-approve transaksinya sendiri? Untuk tipe/nominal apa? |
| D2 | Mata uang | Hanya IDR, atau multi-currency dengan kurs? (saat ini USD diterima tanpa konversi) |
| D3 | Rekening wajib untuk transaksi kas | Wajibkan `payment_account_id` untuk tipe yang menyentuh 1101? Dampak ke alur dokumen/WhatsApp. |
| D4 | Aset tetap | Jurnal disposal (akun laba/rugi pelepasan), keterkaitan register ↔ GL 1501, alur koreksi penyusutan. |
| D5 | Tutup buku | Closing laba periode ke laba ditahan (neraca saat ini menampilkan laba kumulatif sejak awal). |
| D6 | Saldo awal AR/AP | Cara migrasi saldo awal piutang/utang beserta subledger-nya. |
| D7 | Reversal tanpa menghapus histori | Reversal sekarang hard-delete alokasi, settlement, money movement, dan pelepasan retensi. Perlu desain soft-void (kolom + migrasi + semua pembaca) — Claude akan menulis spesifikasinya. |
| D8 | Imutabilitas di level DB | Trigger penolak UPDATE/DELETE untuk `journal_entries`, `journal_lines`, `audit_logs`; tinjau `ON DELETE CASCADE` dari `organizations`. |
| D9 | Uang muka vendor/pelanggan | `VENDOR_ADVANCE`/`SETTLE_VENDOR_ADVANCE`/`CUSTOMER_ADVANCE` belum punya subledger dan aplikasi uang muka ke invoice. |

---

## Serah terima ke Claude (orchestrator) untuk audit

Setelah PR dibuka dan CI selesai, Hermes menulis komentar di PR:
`Siap audit Claude: Txx` (beserta bukti sesuai template). Pemilik meneruskan nomor PR ke Claude,
atau Claude menemukannya sendiri saat memantau PR `hermes/T*`. Claude akan:

1. Membaca diff terhadap scope task dan aturan di bagian 0 (perubahan di luar scope = ditolak).
2. Menjalankan ulang gate CI secara lokal di PostgreSQL 16 (suite penuh, grup PG wajib, `alembic check`,
   pip-audit, frontend jika tersentuh).
3. Memverifikasi tes regresi benar-benar gagal pada `main` dan lulus pada branch PR.
4. Menjalankan `tools/audit/regression_probe.py`: baris task harus `OK`, tidak boleh ada regresi.
5. Mencari jalan pintas secara adversarial (bypass lewat endpoint lain, jalur worker/dokumen,
   konkurensi) dan memberi putusan dengan komentar di PR: `Claude audit: APPROVE` atau
   `Claude audit: REQUEST CHANGES` beserta temuan spesifik.
6. Setelah merge, memperbarui antrean di `PROJECT_STATUS.md` (task berikutnya, blocker).
