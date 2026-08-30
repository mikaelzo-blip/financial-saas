# Feature Specification: Financial Reporting & Management Dashboard

**Feature Branch**: `004-financial-reporting-dashboard`  
**Status**: SPECIFIED & CLARIFIED  
**Created**: 2026-08-30  
**Governing Documents**:
- [.specify/memory/constitution.md](file:///c:/Projects/financial-saas/.specify/memory/constitution.md)
- [docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md](file:///c:/Projects/financial-saas/docs/Sistem_Keuangan_Kontraktor_Final_Concept_v1.md)
- [specs/002-core-financial-domain-model/spec.md](file:///c:/Projects/financial-saas/specs/002-core-financial-domain-model/spec.md)
- [specs/003-core-operational-ui/spec.md](file:///c:/Projects/financial-saas/specs/003-core-operational-ui/spec.md)

---

## Clarifications

### Session 2026-08-30
- **Q01: Supported Report Periods & Temporal Nature** → **Decision**: Supported periods for MVP are **Bulanan (Monthly)**, **Kuartalan (Quarterly)**, **Tahunan (Yearly)**, and **Rentang Tanggal Kustom (Custom Date Range)**. P&L, Arus Kas, dan Project P&L dihitung berdasarkan *aktivitas periode*, sedangkan Neraca dan AR/AP Aging dihitung sebagai *posisi saldo as-of per tanggal*.
- **Q02: Opening Balances Representation** → **Decision**: Saldo awal (*Opening Balances*) tidak boleh diinput manual pada layar laporan. Seluruh saldo awal wajib berasal dari transaksi saldo awal terposting (*Opening Balance Journal Transactions*) atau data migrasi berotorisasi.
- **Q03: Profit & Loss Period Scope** → **Decision**: Laporan Laba Rugi menyajikan akumulasi aktivitas periode yang dipilih, dengan dukungan perbandingan *Bulan Berjalan vs Bulan Sebelumnya*, *Tahun Berjalan vs Tahun Lalu*, dan *Year-to-Date (YTD)*.
- **Q04: Balance Sheet Date Logic** → **Decision**: Neraca disusun secara kumulatif *As-of Date* (per tanggal penutupan periode) dari seluruh baris jurnal buku besar yang terposting hingga tanggal tersebut.
- **Q05: Cash Flow Method** → **Decision**: MVP menggunakan **Metode Langsung (Direct Method)** karena dapat diturunkan secara deterministik dan transparan dari mutasi kas/bank (`1101.xx`) dan tipe transaksi operasional. Arsitektur backend dirancang modular untuk mendukung penambahan Metode Tidak Langsung (*Indirect Method*) di masa mendatang.
- **Q06: Cash Flow Classification & Ambiguity** → **Decision**: Arus kas diklasifikasikan ke *Operasi*, *Investasi*, dan *Pendanaan* berdasarkan kombinasi tipe transaksi dan akun lawan. Mutasi kas yang tidak dapat diklasifikasikan secara pasti disajikan dalam grup *"Transaksi Kas Perlu Klasifikasi"* dan tidak ditebak secara otomatis.
- **Q07: AR Aging Buckets & Basis** → **Decision**: Umur Piutang dihitung berdasarkan **Tanggal Jatuh Tempo Efektif (Effective Due Date)**, bukan tanggal invoice, dengan kelompok umur: *Belum Jatuh Tempo*, *1–30 Hari*, *31–60 Hari*, *61–90 Hari*, dan *> 90 Hari*.
- **Q08: AP Aging Buckets & Basis** → **Decision**: Umur Utang Vendor dihitung berdasarkan **Tanggal Jatuh Tempo Tagihan (Bill Due Date)** dengan kelompok umur yang identik, menampilkan saldo utang murni dan uang muka vendor belum lunas secara terpisah.
- **Q09: Project Profitability Formula & Open Policy** → **Decision**: $\text{Laba Proyek} = \text{Pendapatan Diakui} - \text{Biaya Proyek Terposting}$. Rumus $\text{Nilai Kontrak} - \text{Kas Keluar}$ dilarang keras. Karena kebijakan formal pengakuan pendapatan (*revenue recognition*) masih berstatus **OPEN POLICY**, laporan menampilkan pendapatan diakui berdasarkan invoice termin terposting yang tersedia.
- **Q10: Separation of Project Cash Position** → **Decision**: Posisi Kas Proyek (*Project Cash Position = Kas Diterima - Kas Keluar*) wajib ditampilkan pada kartu/tabel terpisah dengan penegasan bahwa laba proyek tidak sama dengan likuiditas kas proyek.
- **Q11: Budget vs Actual Handling** → **Decision**: Jika anggaran (*budget lines*) proyek belum dimasukkan oleh pengguna, sistem menampilkan status anggun *"Anggaran Belum Ditetapkan"*, tanpa memalsukan angka anggaran 0 atau selisih palsu.
- **Q12: Comparative Reporting Scope** → **Decision**: MVP mendukung komparasi standar: *Bulan Ini vs Bulan Lalu*, *Tahun Ini vs Tahun Lalu*, serta *Realisasi vs Anggaran*.
- **Q13: General Ledger Running Balance** → **Decision**: Saldo berjalan (*running balance*) buku besar adalah murni kalkulasi pada layer pelaporan/tampilan dan tidak disimpan permanen sebagai kolom saldo COA.
- **Q14: Trial Balance Balancing Invariant** → **Decision**: Neraca Saldo menyajikan akun berdasarkan saldo normalnya dan secara wajib memverifikasi $\sum \text{Debet} == \sum \text{Kredit}$.
- **Q15: Multi-Level Drill-Down** → **Decision**: Pengguna dapat melakukan drill-down interaktif: $\text{Laporan Keuangan} \to \text{Baris Akun / Proyek} \to \text{Daftar Jurnal Buku Besar} \to \text{Detail Transaksi} \to \text{Dokumen Bukti Fisik}$.
- **Q16: Export Reconciliation (Excel & PDF)** → **Decision**: Ekspor Excel (`.xlsx`) dan PDF (`.pdf`) dibuat dari payload data otoritatif yang sama persis dengan tampilan layar. Angka total ekspor wajib rekonsiliasi hingga Rp 0,01.
- **Q17: Financial Integrity Blocking Error** → **Decision**: Jika $\text{Aset} \neq \text{Kewajiban} + \text{Ekuitas}$ atau $\sum \text{Debet} \neq \sum \text{Kredit}$, sistem menampilkan status blokir merah *"INTEGRITY_ERROR"* dan melarang sertifikasi/ekspor resmi. Penyeimbang otomatis (plug adjustment) dilarang.
- **Q18: AR/AP Sub-ledger Reconciliation** → **Decision**: Saldo piutang dan utang pada neraca wajib merekonsiliasi 100% dengan total daftar invoice/bill pada sub-ledger.
- **Q19: Project Cost Reconciliation** → **Decision**: Laporan biaya proyek dihitung langsung dari baris jurnal akun kelompok `5101`–`5109` dengan dimensi `project_id`, menjamin zero-duplication.
- **Q20: Role-Based Report Permissions** → **Decision**: **Operator** dapat mengakses laporan operasional (AR, AP, Biaya Proyek), **Manajer & Direktur** memiliki akses penuh ke seluruh Laporan Keuangan (Neraca, Laba Rugi, Arus Kas, Neraca Saldo, Buku Besar, Ekspor), dan **Administrator** mengelola konfigurasi.
- **Q21: Strict Multi-Tenant Isolation** → **Decision**: Seluruh query agregasi pelaporan, cache, ekspor, dan drill-down difilter secara ketat berdasarkan `organization_id` pada backend.
- **Q22: Empty / Incomplete Data Presentation** → **Decision**: Jika periode tidak memiliki transaksi atau proyek baru dibuat, sistem menampilkan kartu kosong *"Tidak Ada Mutasi pada Periode Ini"* tanpa menghasilkan kesimpulan finansial yang menyesatkan.
- **Q23: Monetary Precision & Presentation Formatting** → **Decision**: Seluruh kalkulasi backend menggunakan tipe data `Decimal` (presisi penuh). Pembulatan format Rupiah (`Rp 1.000.000,00`) hanya dilakukan pada layer tampilan.
- **Q24: Dynamic Report Status** → **Decision**: Status integritas laporan dihitung secara dinamis saat laporan di-generate (`VALID` vs `INTEGRITY_ERROR`) tanpa menyimpan status laporan tiruan di database.
- **Q25: Open Policies Protection** → **Decision**: Kebijakan akuntansi berikut dicatat secara eksplisit sebagai **OPEN POLICY** dan tidak di-hardcode: *Metode Pengakuan Pendapatan Persentase Penyelesaian (POC)*, *Batas Materialitas Kapitalisasi Aset*, *Metode Penyusutan Aset Tetap*, *Kebijakan Cutoff Fiskal*, dan *Penilaian Persediaan*.

---

## Executive Summary

Fitur **Financial Reporting & Management Dashboard** menyediakan modul pelaporan keuangan standar SAK bagi kontraktor berbasis proyek di Indonesia. Seluruh laporan keuangan—Laporan Laba Rugi, Neraca, Laporan Arus Kas, Neraca Saldo, Buku Besar, Umur Piutang (AR Aging), Umur Utang (AP Aging), Profitabilitas Proyek, Anggaran vs Realisasi, dan Dashboard Eksekutif—diturunkan secara deterministik dari jurnal buku besar terposting (`JournalLine`) dan sub-ledger transaksi.

Sistem tidak mengizinkan pengubahan angka laporan secara manual. Setiap angka yang tercantum dapat ditelusuri (*drill-down*) hingga ke transaksi asal dan dokumen bukti fisik.

---

## User Personas & Roles

| Peran | Akses Pelaporan | Tanggung Jawab Utama |
|---|---|---|
| **Direktur / Owner** | Dashboard Eksekutif, Laba Rugi, Neraca, Arus Kas, Profitabilitas Proyek, Ekspor PDF/Excel. | Mengambil keputusan strategis, meninjau margin proyek, arus kas likuid, dan kesehatan neraca. |
| **Manajer Keuangan** | Seluruh Laporan Keuangan, Neraca Saldo, Buku Besar, AR/AP Aging, Diagnostik Integritas. | Memastikan kepatuhan akuntansi, rekonsiliasi sub-ledger, dan penutupan buku periode. |
| **Project Manager (PIC Proyek)** | Laporan Profitabilitas Proyek, Posisi Kas Proyek, Anggaran vs Realisasi per Kategori Biaya. | Mengontrol biaya material, upah tukang, subkon, dan efisiensi anggaran lapangan. |
| **Operator Keuangan** | Laporan Operasional: Daftar Piutang (AR), Daftar Utang (AP), Riwayat Mutasi Buku Besar. | Verifikasi penagihan invoice, pembayaran tagihan vendor, dan kelengkapan bukti nota. |

---

## Functional Requirements

### 1. Periode Pelaporan & Pemilihan Rentang Tanggal
- **FR-001**: Sistem WAJIB mendukung pemilihan periode pelaporan:
  - Bulanan (*Contoh: Agustus 2026*)
  - Kuartalan (*Q1, Q2, Q3, Q4 2026*)
  - Tahunan (*Tahun Buku 2026*)
  - Rentang Tanggal Kustom (*dd/mm/yyyy - dd/mm/yyyy*)
- **FR-002**: Setiap laporan WAJIB menampilkan header periode aktif, entitas organisasi, dan timestamp penarikan data.
- **FR-003**: Sistem WAJIB mendukung komparasi periode (*Bulan Berjalan vs Bulan Lalu*, *Tahun Berjalan vs Tahun Lalu*, *Realisasi vs Anggaran*).

---

### 2. Laporan Laba Rugi (Profit & Loss Statement)
- **FR-004**: Sistem WAJIB menyusun Laporan Laba Rugi dengan hierarki standar kontraktor:
  1. **PENDAPATAN**: Pendapatan Proyek (4101), Pendapatan Jasa Lainnya (4201) $\to$ **TOTAL PENDAPATAN**.
  2. **HARGA POKOK PROYEK (HPP)**: Biaya Material (5101), Biaya Subkon (5102), Upah Tenaga Kerja (5103), Sewa Alat (5104), Transportasi & Logistik (5105), Biaya Lapangan Lainnya (5106–5109) $\to$ **TOTAL HARGA POKOK PROYEK**.
  3. **LABA KOTOR** = $\text{Total Pendapatan} - \text{Total HPP}$.
  4. **BEBAN OPERASIONAL**: Gaji/THR Staff Kantor (6101), Honorarium (6102), Sewa Kantor & Administrasi (6103), Perjalanan Kantor (6104), Perizinan (6105), Professional Service (6106), Administrasi Bank (6107), Penyusutan Kantor (6108), Beban Kantor Lainnya (6109) $\to$ **TOTAL BEBAN OPERASIONAL**.
  5. **LABA USAHA (OPERATING PROFIT)** = $\text{Laba Kotor} - \text{Total Beban Operasional}$.
  6. **PENDAPATAN / BEBAN LAIN-LAIN**: Pendapatan Jasa Giro (7101), Beban Bunga Pinjaman (7201).
  7. **LABA SEBELUM PAJAK (EBT)** = $\text{Laba Usaha} + \text{Pendapatan Lain} - \text{Beban Lain}$.
  8. **BEBAN PAJAK PENGHASILAN** (PPh Jasa Konstruksi / Badan).
  9. **LABA BERSIH (NET PROFIT)** = $\text{Laba Sebelum Pajak} - \text{Beban Pajak}$.
- **FR-005**: Setiap baris nilai Laba Rugi WAJIB dapat di-klik untuk membuka rincian jurnal buku besar terkait (*drill-down*).

---

### 3. Laporan Neraca (Balance Sheet Statement)
- **FR-006**: Sistem WAJIB menyusun Laporan Neraca per tanggal penutupan (*As-of Date*):
  1. **ASET LANCAR**: Kas dan Bank (1101), Piutang Usaha (1102), Persediaan Material (1103), Uang Muka Vendor (1104), Pajak Dibayar Dimuka (1105) $\to$ **TOTAL ASET LANCAR**.
  2. **ASET TETAP**: Peralatan & Kendaraan Proyek (1201), Akumulasi Penyusutan (1202) $\to$ **TOTAL ASET TETAP**.
  3. **TOTAL ASET** = $\text{Total Aset Lancar} + \text{Total Aset Tetap}$.
  4. **KEWAJIBAN**: Utang Usaha (2101), Utang Bank/Leasing (2102), Utang Pajak (2103), Utang Operasional (2104), Uang Muka Proyek dari Customer (2105) $\to$ **TOTAL KEWAJIBAN**.
  5. **EKUITAS**: Modal Disetor (3101), Saldo Laba Ditahan (3201), Laba/Rugi Periode Berjalan (3301), Prive/Distribusi Modal (3401) $\to$ **TOTAL EKUITAS**.
  6. **TOTAL KEWAJIBAN + EKUITAS**
- **FR-007 (Invarian Wajib)**: Jika $\text{Total Aset} \neq \text{Total Kewajiban} + \text{Total Ekuitas}$, sistem WAJIB menampilkan peringatan merah mencolok *"Neraca Tidak Seimbang — Selisih: Rp X"* dan menandai laporan sebagai `INTEGRITY_ERROR`. Penyisipan angka penyeimbang buatan dilarang keras.

---

### 4. Laporan Arus Kas (Cash Flow Statement - Direct Method)
- **FR-008**: Sistem WAJIB menyusun Laporan Arus Kas Metode Langsung:
  - **Arus Kas Aktivitas Operasi**: Penerimaan termin customer, pembayaran vendor material/subkon, kasbon tukang, beban operasional kantor.
  - **Arus Kas Aktivitas Investasi**: Pembelian/penjualan aset tetap dan alat kerja konstruksi.
  - **Arus Kas Aktivitas Pendanaan**: Setoran modal pemilik, penarikan prive pemilik, pencairan/pelunasan pinjaman bank.
- **FR-009**: Mutasi kas yang klasifikasinya belum pasti disajikan pada kelompok *"Transaksi Kas Perlu Klasifikasi"* dan tidak ditebak secara acak.

---

### 5. Neraca Saldo (Trial Balance)
- **FR-010**: Neraca Saldo WAJIB menyajikan: Kode Akun, Nama Akun, Saldo Awal Debet/Kredit, Mutasi Debet Periode, Mutasi Kredit Periode, Saldo Akhir Debet/Kredit.
- **FR-011**: Sistem WAJIB memvalidasi $\sum \text{Debet} == \sum \text{Kredit}$ pada saldo awal, mutasi periode, dan saldo akhir.

---

### 6. Buku Besar (General Ledger)
- **FR-012**: Buku Besar mendukung filter per Kode Akun dan Rentang Tanggal, menyajikan: Tanggal, Ref Jurnal, Keterangan Transaksi, Dimensi Proyek, Debet, Kredit, dan Saldo Berjalan (*Running Balance*).
- **FR-013**: Saldo berjalan murni merupakan kalkulasi pelaporan dan tidak disimpan di tabel master COA.

---

### 7. Laporan Umur Piutang (AR Aging) & Umur Utang (AP Aging)
- **FR-014**: Laporan AR Aging mengelompokkan sisa piutang berdasarkan **Tanggal Jatuh Tempo Efektif**:
  - Belum Jatuh Tempo (Current)
  - 1 – 30 Hari
  - 31 – 60 Hari
  - 61 – 90 Hari
  - \> 90 Hari (Kritis)
- **FR-015**: Laporan AP Aging mengelompokkan tagihan vendor berdasarkan Tanggal Jatuh Tempo Tagihan dengan kelompok umur yang sama, serta menyajikan saldo kasbon/uang muka vendor yang belum diselesaikan.

---

### 8. Laporan Profitabilitas & Posisi Kas Proyek (Project P&L vs Cash Position)
- **FR-016**: Laporan Profitabilitas Proyek menampilkan:
  - Nilai Kontrak Awal + Variation Order = Nilai Kontrak Revisi
  - Pendapatan Diakui (Accrual Basis)
  - Realisasi Biaya 9 Kategori: `MAT`, `SUB`, `LAB`, `EQP`, `TRN`, `TRV`, `LOG`, `SIT`, `OTH`
  - Laba Kotor Proyek & Margin Laba Kotor (%)
- **FR-017**: Laporan WAJIB menampilkan **Posisi Kas Proyek** secara terpisah:
  - Tagihan Diterbitkan (*Invoiced*)
  - Kas Diterima dari Pelanggan (*Cash In*)
  - Kas Dikeluarkan untuk Proyek (*Cash Out*)
  - Surplus / Defisit Kas Proyek (*Net Cash Position*)
  - Banner edukatif: *"Laba Proyek (Akrual) Berbeda dengan Posisi Kas Proyek (Likuiditas)."*

---

### 9. Laporan Anggaran vs Realisasi (Budget vs Actual)
- **FR-018**: Sistem menyajikan perbandingan Anggaran vs Realisasi per proyek dan per kategori biaya:
  - Anggaran (Budgeted Amount)
  - Realisasi Biaya Aktual (Posted Cost)
  - Selisih Nominal (Variance Amount)
  - Persentase Realisasi (% Consumed)
  - Status: Hijau ($\le 90\%$), Kuning ($91-100\%$), Merah ($> 100\%$). Jika anggaran belum diisi, sistem menampilkan *"Anggaran Belum Ditetapkan"*.

---

### 10. Dashboard Eksekutif Manajemen
- **FR-019**: Dashboard manajemen menyajikan kartu ringkasan otoritatif:
  1. Saldo Likuid Kas & Bank
  2. Pendapatan & Laba Kotor Berjalan
  3. Total Sisa Piutang Usaha (AR) & Invoice Overdue
  4. Total Sisa Utang Usaha (AP) & Tagihan Jatuh Tempo
  5. Jumlah Proyek Aktif & Rata-rata Gross Margin
  6. Peringatan Antrean Review / Ambiguity
  7. Grafik Tren Arus Kas Masuk vs Kas Keluar

---

### 11. Ekspor Laporan (Excel & PDF)
- **FR-020**: Setiap laporan WAJIB mendukung ekspor ke format:
  - **Microsoft Excel (`.xlsx`)**: Berisi header formal, periode, tabel angka numerik murni, dan formula penjumlahan.
  - **PDF (`.pdf`)**: Dokumen formal siap cetak dengan kop perusahaan, nomor halaman, dan kolom tanda tangan pengesahan.
- **FR-021**: Seluruh angka pada file ekspor WAJIB rekonsiliasi 100% (sama persis hingga Rp 0,01) dengan angka yang tampil pada aplikasi web.

---

## User Scenarios & Acceptance Criteria

### Scenario 1: Peninjauan Laporan Laba Rugi Bulanan
- **Given** Manajer Keuangan memilih periode "Agustus 2026"
- **When** Laporan Laba Rugi dibuka
- **Then** Sistem menampilkan Pendapatan, HPP Proyek, Laba Kotor, Beban Operasional, dan Laba Bersih yang bersumber dari jurnal terposting periode Agustus 2026
- **And** Klik pada "Biaya Material & Bahan" membuka Buku Besar akun 5101 dengan daftar seluruh jurnal terkait.

### Scenario 2: Validasi Invarian Keseimbangan Neraca
- **Given** Seluruh transaksi telah diposting hingga 31 Agustus 2026
- **When** Laporan Neraca ditampilkan
- **Then** Sistem menghitung Total Aset dan Total Kewajiban + Ekuitas
- **And** Jika Total Aset == Total Kewajiban + Ekuitas, status "Neraca Seimbang (Balanced)" berwarna hijau ditampilkan
- **And** Jika terdapat selisih, banner merah blokir "INTEGRITY_ERROR: Selisih Neraca Rp [X]" ditampilkan dan sertifikasi laporan dinonaktifkan.

### Scenario 3: Analisis Profitabilitas vs Kas Proyek
- **Given** Proyek "Pembangunan Ruko" dengan Kontrak Rp 1.000.000.000, Invoice Diterbitkan Rp 600.000.000, Kas Diterima Rp 400.000.000, dan Biaya Lapangan Rp 350.000.000
- **When** Project Manager membuka Laporan Profitabilitas Proyek
- **Then** Pendapatan Diakui menunjukkan Rp 600.000.000, Biaya Aktual Rp 350.000.000, dan Laba Kotor Rp 250.000.000 (Margin 41,67%)
- **And** Bagian Posisi Kas menunjukkan Kas Masuk Rp 400.000.000, Kas Keluar Rp 350.000.000, dan Surplus Kas Proyek Rp +50.000.000.

### Scenario 4: Ekspor Laporan Rekonsiliasi ke Excel
- **Given** Laporan Umur Piutang (AR Aging) di layar menampilkan total Rp 450.000.000
- **When** Pengguna mengklik "Ekspor ke Excel (.xlsx)"
- **Then** File spreadsheet terunduh dengan total penjumlahan seluruh baris invoice tepat bernilai Rp 450.000.000.

---

## Non-Functional Requirements & Security

- **Isolasi Multi-Tenant**: Seluruh kueri pelaporan menyertakan filter `organization_id` wajib.
- **Kinerja**: Waktu komputasi laporan $< 500$ ms untuk data hingga 100.000 baris jurnal buku besar.
- **Presisi Angka**: Kalkulasi backend menggunakan `Decimal` presisi penuh; pembulatan Rupiah hanya terjadi pada layer presentasi.
- **Bahasa & Istilah**: 100% Bahasa Indonesia sesuai istilah standar akuntansi kontraktor Indonesia.

---

## Explicit Open Policies

1. **Kebijakan Pengakuan Pendapatan (Revenue Recognition Policy)**: Metode persentase penyelesaian fisik (*Physical Progress Percentage of Completion*) vs metode penagihan invoice termin.
2. **Kebijakan Batas Kapitalisasi Aset Tetap**: Batas minimum nilai pembelian perkakas yang dikapitalisasi sebagai aset tetap vs dibebankan langsung.
3. **Metode Penyusutan Fiskal vs Komersial**: Metode garis lurus (*Straight-Line*) vs saldo menurun (*Declining Balance*).
4. **Kebijakan Cutoff Periode Buku**: Batas waktu penerimaan nota susulan akhir bulan.

---

## Success Criteria

1. **Integritas Persamaan Akuntansi**: 100% Laporan Neraca memenuhi $\text{Aset} = \text{Kewajiban} + \text{Ekuitas}$.
2. **Rekonsiliasi Jurnal**: 100% baris laporan keuangan merekonsiliasi ke baris jurnal terposting dan sub-ledger terkait.
3. **Ketertelusuran (Traceability)**: Setiap angka laporan dapat di-drill-down hingga ke jurnal, transaksi, dan bukti dokumen fisik.
4. **Presisi Ekspor**: 100% kesesuaian angka antara tampilan layar dan file ekspor Excel/PDF.
5. **Zero Manual Override**: 0 fasilitas manipulasi atau pengetikan angka manual pada laporan.
