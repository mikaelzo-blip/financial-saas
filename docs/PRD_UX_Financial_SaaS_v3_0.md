# PRD UX v3.0 — Financial SaaS Kontraktor
## Owner-First UX, Accounting Classification, Review Workflow & Consultant-Aligned Reporting

**Versi:** 3.0<br>
**Tanggal:** 7 September 2026<br>
**Status:** IMPLEMENTATION DRAFT — menunggu Owner sign-off setelah implementasi visual<br>
**Produk:** Financial SaaS Kontraktor<br>
**Primary User:** Owner / Direktur / Administrator non-akuntan<br>
**Operating Model:** Local-first pada PC Windows<br>
**WhatsApp Transport:** Baileys lokal saat PC menyala<br>
**Accounting Model:** Accrual accounting + double-entry backend
**Prinsip utama:** Owner tidak perlu memilih debit/kredit secara manual.

---

# 0. Tujuan Dokumen

Dokumen ini adalah **PRD khusus UX/UI dan klasifikasi transaksi** untuk Financial SaaS.

Dokumen ini memperbarui konsep UX sebelumnya dengan tujuan:

1. membuat aplikasi mudah dipakai Owner yang bukan akuntan;
2. menyatukan istilah dan struktur laporan dengan laporan konsultan keuangan;
3. menghilangkan input teknis seperti debit/kredit, raw JSON, UUID, atau kode internal dari workflow Owner;
4. membuat klasifikasi transaksi proyek vs kantor lebih jelas;
5. memperjelas status dokumen, review, approval, posting, dan reversal;
6. menjaga integritas akuntansi tanpa membuat UI terasa seperti software akuntansi tradisional;
7. memastikan PPh Final jasa konstruksi, retensi, aset kontrak, dan biaya proyek tidak salah klasifikasi;
8. membuat halaman yang sudah ada tetap dipakai jika sudah baik, bukan rewrite tanpa alasan.

Dokumen ini **tidak menggantikan keputusan konsultan pajak/akuntansi** untuk perlakuan pajak final, tarif, masa manfaat aset, cut-off, maupun kebijakan lain yang memerlukan penilaian profesional.

---

# 1. Product Principles yang Dikunci

## 1.1 Owner-first, accounting-backed

Owner berinteraksi dengan bahasa operasional:

- beli material;
- bayar vendor;
- fee;
- bensin;
- listrik;
- gaji;
- terima pembayaran proyek;
- bayar cicilan;
- tambah modal;
- ambil uang pemilik;
- upload invoice/SPK/bukti transfer.

Backend menerjemahkan pilihan tersebut menjadi:

- COA;
- debit/kredit;
- AR/AP;
- journal;
- project allocation;
- cash movement;
- tax treatment;
- reporting.

**Owner tidak memilih debit/kredit.**

---

## 1.2 Single input

Satu kejadian bisnis hanya diinput sekali.

Contoh:

> Owner mencatat pembayaran material proyek.

Sistem harus dapat membentuk dari satu input yang sama:

- cash movement;
- transaction;
- project cost;
- vendor linkage;
- document linkage;
- journal;
- report impact.

Tidak boleh meminta Owner menginput transaksi yang sama kembali di halaman lain.

---

## 1.3 Project context before accounting category

Sebelum menentukan akun, UX lebih dahulu menanyakan:

> **Transaksi ini untuk apa?**

Pilihan utama:

1. Proyek tertentu
2. Operasional kantor
3. Pemilik / modal
4. Pinjaman / pendanaan
5. Pajak
6. Belum yakin

Pilihan ini digunakan untuk mempersempit kategori berikutnya.

---

## 1.4 Accounting engine tetap authoritative

AI/Hermes boleh:

- membaca bukti;
- menyarankan kategori;
- menyarankan project;
- menyarankan vendor/customer;
- menyarankan nominal;
- memberi confidence;
- menjelaskan alasan.

AI/Hermes tidak boleh:

- mengubah jurnal posted secara langsung;
- memilih debit/kredit secara bebas;
- melewati review gate untuk kasus ambigu;
- mengubah data lintas tenant;
- membuat accounting treatment di luar rule engine.

---

## 1.5 Human review sebelum posting untuk exception

Dokumen/transaksi dengan ambiguity, confidence rendah, conflict, atau rule yang membutuhkan persetujuan harus masuk:

**Perlu Diperiksa**

sebelum menghasilkan jurnal final.

---

## 1.6 Reversal, bukan edit histori

Transaksi yang sudah posted tidak diedit secara destruktif.

Koreksi dilakukan melalui:

**Batalkan / Reverse → buat transaksi pengganti bila diperlukan.**

Audit trail harus tetap utuh.

---

# 2. UX Direction

## 2.1 Visual style

Pertahankan karakter UI saat ini:

- sidebar gelap;
- content area terang;
- primary action biru;
- status sukses hijau;
- warning kuning/oranye;
- destructive merah;
- card radius sedang;
- whitespace cukup;
- tabel sederhana dan rapi.

Tidak diperlukan redesign total.

Fokus perbaikan:

- information hierarchy;
- bahasa;
- status;
- raw technical data;
- actionable empty state;
- consistency;
- transaction classification.

---

## 2.2 Desktop-first

Primary device adalah desktop Windows.

Target minimum:

- 1366 × 768 usable;
- optimal 1440p/1080p desktop;
- sidebar tetap terbaca;
- modal tidak lebih tinggi dari viewport;
- tabel dapat scroll horizontal jika benar-benar diperlukan.

Mobile bukan prioritas RC saat ini.

---

# 3. Information Architecture

Sidebar utama tetap sederhana:

```text
1. Dashboard
2. WhatsApp Inbox
3. Proyek
4. Kas & Bank
5. Rekonsiliasi Bank
6. Perlu Diperiksa
7. Transaksi
8. Dokumen Bukti
9. Piutang Pelanggan
10. Utang Vendor
11. Laporan Keuangan
    - Laba Rugi
    - Posisi Keuangan / Neraca
    - Arus Kas
    - Profitabilitas Proyek
    - Posisi Kas Proyek
    - Anggaran vs Realisasi
    - Neraca Saldo
    - Buku Besar
    - Umur Piutang
    - Umur Utang
    - Rekonsiliasi Konsultan
12. Data Master
    - Pelanggan
    - Vendor & Subkon
    - Aset Tetap
    - Daftar Akun Akuntansi
    - Kategori Transaksi
13. Pengaturan & Sistem
```

---

# 4. Dashboard — UX Terbaru

## 4.1 Dashboard harus menjawab 6 pertanyaan Owner

Saat membuka aplikasi, Owner harus langsung dapat mengetahui:

1. Berapa uang tersedia?
2. Berapa uang masuk dan keluar?
3. Berapa pendapatan dan laba?
4. Berapa piutang yang belum dibayar?
5. Berapa utang yang harus dibayar?
6. Apa yang membutuhkan tindakan sekarang?

---

## 4.2 KPI utama

Card yang direkomendasikan:

```text
Total Kas & Bank
Cash Runway
Pendapatan YTD
Proyek Aktif

Kas Masuk Bulan Ini
Kas Keluar Bulan Ini
Net Cash Flow MTD
Belanja Proyek Bulan Ini

WhatsApp Inbox
Piutang Usaha
Utang Usaha
Antrean Review
```

Card harus clickable ke halaman detail.

---

## 4.3 Insight Manajemen

Tampilan raw seperti:

```text
revenue
25000000.00

ap total
38850000.00
```

**tidak boleh ditampilkan kepada Owner.**

Ganti dengan format:

```text
Ringkasan Periode
1 Sep 2026 — 7 Sep 2026

Pendapatan        Rp 25.000.000
Laba Kotor        Rp 8.000.000
Margin Kotor      32,0%
Laba Bersih       Rp 8.000.000
Kas & Bank        Rp 108.000.000
Piutang           Rp 0
Utang             Rp 38.850.000
```

Kemudian:

```text
Perhatian
• Ada Rp38.850.000 utang melewati jatuh tempo.
• Tidak ada piutang tertunggak.
```

Jangan expose field internal berbahasa Inggris ke UI Owner.

---

## 4.4 Ask Finance

Fitur tanya jawab keuangan boleh tetap tersedia.

Placeholder:

> Contoh: Utang mana yang paling mendesak dibayar?

Jawaban harus read-only/advisory.

AI tidak boleh posting jurnal dari kotak chat Dashboard.

---

# 5. Model Input Transaksi Owner

Form transaksi saat ini sudah memiliki fondasi yang baik, tetapi urutan pertanyaannya perlu dibuat lebih natural.

## 5.1 Urutan baru

### Langkah 1 — Apa yang terjadi?

```text
Jenis transaksi
[ Pembelian / Pengeluaran ]
[ Tagihan Vendor ]
[ Penerimaan Customer ]
[ Invoice Customer ]
[ Modal / Prive ]
[ Pinjaman / Cicilan ]
[ Pajak ]
[ Lainnya ]
```

### Langkah 2 — Digunakan untuk apa?

```text
[ Proyek tertentu ]
[ Operasional kantor ]
[ Pemilik / Modal ]
[ Pendanaan ]
[ Pajak ]
[ Belum yakin ]
```

Jika `Proyek tertentu`, field Project wajib.

### Langkah 3 — Kategori

Kategori yang muncul harus disaring berdasarkan konteks.

### Langkah 4 — Detail transaksi

- tanggal;
- nominal;
- kas/bank;
- vendor/customer;
- nomor referensi;
- keterangan.

### Langkah 5 — Bukti

Upload:

- PDF;
- JPG/JPEG;
- PNG;
- WEBP;
- HEIC jika pipeline mendukung.

### Langkah 6 — Ringkasan sebelum simpan

Contoh:

```text
Pembelian material proyek

Proyek:
Demo Perbaikan Panel Listrik

Vendor:
PT Nusa Engineering

Nominal:
Rp 12.000.000

Dibayar dari:
Bank Mandiri

Kategori:
Material Proyek

Dampak:
Biaya langsung proyek + pengeluaran kas
```

Owner tidak perlu melihat:

```text
Debit 5101
Credit 1101
```

kecuali membuka menu advanced accounting detail.

---

# 6. Kategori Transaksi Owner

Kategori UX **tidak harus sama persis dengan nama COA**.

Kategori Owner adalah bahasa bisnis.
Backend melakukan mapping ke COA authoritative.

---

## 6.1 Biaya proyek

### A. Material / Barang Proyek

Contoh:

- kabel;
- panel;
- breaker;
- pipa;
- semen;
- besi;
- sparepart;
- komponen;
- barang pengadaan untuk proyek.

UX:

```text
Untuk Proyek
→ Material / Barang Proyek
```

Treatment:

- direct project cost;
- masuk HPP/proyek;
- wajib link project.

---

### B. Subkontraktor / Jasa Spesialis

Contoh:

- teknisi spesialis;
- subcontractor;
- jasa instalasi pihak ketiga;
- jasa fabrikasi;
- jasa machining.

UX:

```text
Untuk Proyek
→ Subkontraktor / Jasa Spesialis
```

---

### C. Fee / Komisi Proyek

Contoh:

- fee tenaga ahli;
- fee pengawas khusus proyek;
- fee perantara yang jelas terkait satu proyek;
- jasa orang berdasarkan keberhasilan proyek.

UX:

```text
Untuk Proyek
→ Fee / Komisi Proyek
```

Bukan `Beban Kantor`.

---

### D. Upah Tenaga Kerja Proyek

Contoh:

- harian lapangan;
- borongan tenaga kerja;
- mandor;
- helper;
- teknisi lapangan.

---

### E. BBM / Transportasi Proyek

Contoh:

- bensin perjalanan site;
- tol proyek;
- parkir site;
- transport material;
- perjalanan teknisi untuk satu proyek.

UX:

```text
Untuk Proyek
→ Transportasi / BBM Proyek
```

---

### F. Sewa Alat Proyek

Contoh:

- crane;
- genset;
- scaffolding;
- forklift;
- alat berat;
- alat kerja sewaan.

---

### G. Logistik / Ekspedisi Proyek

Contoh:

- cargo;
- pengiriman barang;
- trucking;
- ongkir material proyek.

---

### H. Legal / Perizinan Proyek

Dipakai hanya jika pengeluaran memang khusus untuk satu proyek.

Contoh:

- izin site tertentu;
- sertifikasi kerja khusus proyek;
- izin akses pekerjaan;
- biaya pengujian/sertifikasi yang diwajibkan kontrak proyek.

---

### I. Biaya Lapangan Lainnya

Dipakai jika direct project cost valid tetapi tidak cocok dengan kategori di atas.

Jangan gunakan kategori ini sebagai default jika Hermes belum yakin.

Jika tidak yakin → `Perlu Diperiksa`.

---

# 7. Beban Operasional Kantor

## 7.1 Gaji & Upah Kantor

Untuk pegawai/staf yang bukan direct project labour.

---

## 7.2 Fee / Komisi / Jasa Non-Proyek

Contoh:

- fee akuntan;
- konsultan perusahaan;
- jasa administrasi;
- komisi non-proyek;
- jasa profesional umum.

UX:

```text
Operasional Kantor
→ Fee / Jasa Profesional
```

---

## 7.3 BBM, Parkir & Transportasi Kantor

Contoh:

- bensin urusan kantor;
- parkir meeting;
- perjalanan bank;
- transport non-proyek.

Perbedaan utama dengan BBM proyek:

> **Apakah biaya ini terjadi untuk satu proyek tertentu?**

Ya → proyek.<br>
Tidak → kantor.

---

## 7.4 Listrik & Utilitas

Contoh:

- listrik kantor;
- internet kantor;
- air;
- telepon;
- utilitas lain.

UX:

```text
Operasional Kantor
→ Listrik & Utilitas
```

---

## 7.5 Keperluan Kantor

Contoh:

- ATK;
- tinta printer;
- konsumsi kantor;
- perlengkapan kecil;
- barang habis pakai.

---

## 7.6 Administrasi Bank

Contoh:

- biaya admin;
- biaya transfer;
- biaya layanan bank.

---

## 7.7 Legal / Perizinan Perusahaan

Contoh:

- legalitas perusahaan;
- sertifikasi perusahaan umum;
- perpanjangan izin;
- notaris perusahaan;
- dokumen administratif badan usaha.

---

## 7.8 Penyusutan Aset Tetap

Tidak diinput manual sebagai transaksi operasional harian.

Dihasilkan dari Fixed Asset Register dan depreciation run.

---

# 8. Pembelian Barang: Decision UX

Ketika Owner memilih `Beli Barang`, sistem harus bertanya:

```text
Barang ini digunakan untuk:

○ Proyek tertentu
○ Kantor / operasional umum
○ Menjadi aset perusahaan
○ Belum yakin
```

## Jika Proyek tertentu

→ Material / Barang Proyek.

## Jika Kantor

Kemudian:

```text
Apakah barang dipakai jangka panjang sebagai aset perusahaan?

○ Ya
○ Tidak
```

Jika tidak:

→ Keperluan Kantor.

Jika ya:

→ evaluasi Fixed Asset Policy.

Threshold kapitalisasi dan masa manfaat adalah **kebijakan perusahaan/konsultan**, bukan asumsi universal AI.

---

# 9. Aset Tetap

Halaman Fixed Assets saat ini secara visual sudah baik dan dipertahankan.

Perbaikan:

1. dropdown kategori tidak boleh terpotong;
2. tampilkan preview penyusutan sebelum menyimpan;
3. format rupiah saat mengetik;
4. tampilkan:
   - harga perolehan;
   - nilai residu;
   - tanggal digunakan;
   - masa manfaat;
   - metode;
   - penyusutan per bulan;
5. `Jalankan Penyusutan Bulanan` harus menunjukkan periode yang akan diposting;
6. mencegah double depreciation untuk periode yang sama.

Owner tidak perlu memilih akun aset/akumulasi penyusutan.

---

# 10. Fee — Decision UX

Ketika transaksi mengandung kata:

- fee;
- honor;
- komisi;
- jasa;
- tenaga ahli;

Hermes/UI tidak boleh langsung menentukan akun.

Sistem harus menentukan konteks:

```text
Fee ini terkait langsung dengan proyek tertentu?

YES
→ Fee / Jasa Proyek
→ Project required

NO
→ Fee / Jasa Profesional Kantor

UNKNOWN
→ Perlu Diperiksa
```

---

# 11. BBM / Bensin — Decision UX

```text
Bensin digunakan untuk pekerjaan proyek tertentu?

YES
→ BBM / Transportasi Proyek

NO
→ BBM / Parkir / Transportasi Kantor

UNKNOWN
→ Perlu Diperiksa
```

Deskripsi dan project link menjadi evidence utama.

Jangan hanya memakai merchant/SPBU untuk menentukan project.

---

# 12. Listrik — Decision UX

Default:

```text
Listrik kantor
→ Listrik & Utilitas
→ Operasional Kantor
```

Jika ada fasilitas/site proyek sementara dan bukti jelas terkait satu proyek:

```text
Listrik site proyek
→ Biaya Langsung Proyek
```

Jika ambiguity tinggi:

→ Perlu Diperiksa.

---

# 13. Loan / Pinjaman

UX harus memisahkan:

### Pinjaman masuk

Bukan pendapatan.

### Bayar pokok pinjaman

Bukan beban.

### Bunga pinjaman

Beban keuangan.

### Biaya administrasi pinjaman

Beban sesuai kebijakan.

Owner memilih aktivitas, bukan debit/kredit.

---

# 14. Modal & Prive

## Tambah Modal

Bukan pendapatan.

UX:

```text
Pemilik memasukkan uang ke perusahaan
→ Tambahan Modal
```

## Prive

Bukan beban operasional.

UX:

```text
Pemilik mengambil uang perusahaan untuk kepentingan pribadi
→ Prive
```

Harus mudah dibedakan dari reimbursement biaya usaha.

---

# 15. Pajak — UX dan Accounting Classification

## 15.1 Pisahkan kategori pajak

Jangan hanya menyediakan satu kategori `Pajak`.

Minimal pisahkan:

```text
PPh Final Jasa Konstruksi
PPh yang dapat dikreditkan / pajak dibayar dimuka
PPN Masukan
PPN Keluaran
PPh 21
Pajak & Retribusi Non-PPh
```

---

## 15.2 PPh Final jasa konstruksi

PPh Final harus memiliki dua konsep berbeda di accounting backend:

```text
PPh Final Dipotong / Dibayar Dimuka
```

dan

```text
Beban PPh Final
```

Potongan oleh customer/pemberi kerja dapat ditampung sebagai pajak dibayar dimuka sampai direkonsiliasi dengan kewajiban/beban final sesuai kebijakan dan bukti potong.

Tarif **tidak boleh hard-coded satu angka global**.

Tarif harus configurable berdasarkan:

- proyek/kontrak;
- jenis jasa;
- klasifikasi/sertifikasi yang relevan;
- periode;
- keputusan konsultan.

---

# 16. Retensi

Retensi harus menjadi first-class accounting concept.

## Retensi dari Customer

```text
Piutang Retensi
```

Artinya hak tagih perusahaan ditahan customer sampai syarat tertentu terpenuhi.

## Retensi kepada Vendor/Subkon

```text
Utang Retensi
```

Artinya bagian kewajiban kita kepada vendor/subkon ditahan sampai syarat terpenuhi.

UX Project Detail harus dapat menampilkan:

```text
Nilai Kontrak
Sudah Ditagih
Sudah Dibayar Customer
Piutang
Retensi
```

---

# 17. Profitabilitas Proyek

Formula Owner-facing:

```text
Pendapatan Proyek
- Biaya Langsung Proyek
= Laba Kotor Proyek
```

Tambahkan label permanen:

> **Belum termasuk alokasi biaya kantor umum dan pajak perusahaan.**

Jangan menamai angka ini `Laba Bersih Proyek`.

Breakdown biaya:

```text
Material
Subkontraktor/Jasa Spesialis
Tenaga Kerja
Fee Proyek
BBM/Transport
Sewa Alat
Logistik
Legal/Perizinan Proyek
Biaya Langsung Lainnya
```

---

# 18. Laba Rugi — Struktur Terbaru

Laporan formal Owner harus mengikuti struktur:

```text
I. PENDAPATAN USAHA

Pendapatan Proyek dan Jasa

II. HARGA POKOK PROYEK

Material/Jasa Langsung
Tenaga Kerja/Fee Proyek
Operasional Langsung Proyek

LABA KOTOR

III. BEBAN OPERASIONAL KANTOR

Gaji dan Upah Kantor
Fee/Komisi/Jasa Non-Proyek
BBM/Parkir/Transportasi Kantor
Ongkos Kirim Non-Proyek
Konsumsi/Keperluan Kantor
Administrasi Bank
Legal/Perizinan Perusahaan
Listrik & Utilitas
Penyusutan Aset Tetap
Beban Operasional Lainnya

LABA USAHA

IV. PENDAPATAN / BEBAN LAIN-LAIN

Pendapatan Bunga / Pendapatan Lain
Beban Pajak & Retribusi Non-PPh
Beban Non-Operasional Lain

LABA SEBELUM PPh FINAL

V. PAJAK PENGHASILAN FINAL

Beban PPh Final

LABA BERSIH PERIODE BERJALAN
```

---

## 18.1 UX Laba Rugi

Pertahankan gaya laporan saat ini karena sudah mudah dibaca.

Tambahkan:

- toggle `Sembunyikan akun Rp0`;
- opsi period;
- export Excel/PDF;
- drilldown nilai ke ledger/transaksi;
- subtotal yang jelas;
- PPh Final terpisah;
- format `Rp` konsisten;
- angka negatif konsisten dengan `(Rp x)` atau minus, jangan campur.

---

# 19. Neraca / Laporan Posisi Keuangan

Backend harus mendukung struktur lebih lengkap daripada dataset demo.

## Aset Lancar

```text
Kas dan Bank
Piutang Usaha
Piutang Retensi
Aset Kontrak
Uang Muka / Transaksi Menunggu Bukti
Persediaan
Pajak Dibayar Dimuka
PPh Final Dibayar Dimuka
PPN Masukan
```

## Aset Tetap

```text
Peralatan
Kendaraan
Aset Tetap Lain
(-) Akumulasi Penyusutan
```

## Liabilitas

```text
Utang Usaha
Liabilitas Sewa
Utang Pajak
PPN Keluaran / Utang PPN
Uang Muka Pelanggan
Liabilitas Kontrak
Utang Retensi
Penerimaan Belum Teridentifikasi
Utang Pihak Berelasi
```

## Ekuitas

```text
Modal
Saldo Laba
(-) Prive
Laba/Rugi Periode Berjalan
```

---

## 19.1 UX Neraca

Default:

**hide zero rows** agar mudah dibaca Owner.

Tambahkan toggle:

```text
[ ] Tampilkan akun bernilai Rp0
```

Tetap tampilkan:

```text
TOTAL ASET
TOTAL KEWAJIBAN
TOTAL EKUITAS
TOTAL KEWAJIBAN + EKUITAS
SELISIH
```

Jika selisih bukan nol:

status merah dan export laporan formal diblokir sampai masalah ditinjau.

---

# 20. Kas & Bank

Halaman Kas & Bank saat ini mudah dipahami, tetapi ada satu prinsip penting:

Setiap rekening/kas adalah **payment account / subledger yang berbeda**, walaupun semuanya dapat roll-up ke akun laporan `Kas & Bank`.

Contoh Owner-facing:

```text
Bank Mandiri
BCA
BRI
Kas
Petty Cash
```

Jangan membuat owner bingung karena seluruh rekening menampilkan kode COA yang sama tanpa konteks.

Jika memakai parent COA yang sama, UI tidak perlu menampilkan kode tersebut sebagai identitas utama.

---

# 21. Rekonsiliasi Bank

UX flow:

```text
1. Pilih rekening bank
2. Upload rekening koran
3. Validasi file
4. Sistem melakukan matching
5. Tampilkan:
   - Cocok
   - Cocok sebagian
   - Hanya di bank
   - Hanya di pembukuan
   - Perlu diperiksa
6. Owner review exception
7. Finalisasi rekonsiliasi
```

Tombol `Impor & Rekonsiliasi Otomatis` disabled sampai:

- rekening dipilih;
- file valid.

Loading skeleton tidak boleh terlihat permanen tanpa label.

Gunakan:

```text
Memuat saldo rekening...
```

atau error state eksplisit.

---

# 22. Review Queue

Nama Owner-facing:

**Perlu Diperiksa**

Tab:

```text
Dokumen Masuk
Transaksi Ambigu
```

Setiap item menampilkan:

- thumbnail/preview;
- nama file;
- tanggal;
- sender/source;
- nominal;
- project suggestion;
- counterparty suggestion;
- kategori suggestion;
- confidence;
- alasan kenapa perlu review.

Prioritas:

```text
TINGGI
SEDANG
RENDAH
```

berdasarkan risiko, bukan hanya confidence AI.

---

# 23. Document Review Screen

Ini salah satu area UX yang paling perlu diperbaiki.

## 23.1 Hapus raw JSON dari workflow Owner

Raw JSON jangan tampil sebagai panel utama.

Ganti dengan:

```text
Hasil Pembacaan Dokumen

Jenis Dokumen
Bukti Transfer

Tanggal
4 Mei 2026

Nominal
Rp 30.788.350

Bank
Mandiri

Penerima
...

Nomor Referensi
...

Deskripsi
DP SPK ...
```

Raw JSON hanya boleh tersedia melalui:

```text
Detail Teknis
```

yang collapsed secara default.

---

## 23.2 Jangan meminta raw Project ID / Counterparty ID

Field:

```text
Project ID
Counterparty ID
```

diganti dengan autocomplete:

```text
Proyek
[ Demo Perbaikan Panel Listrik ▼ ]

Vendor / Customer
[ PT .... ▼ ]
```

Backend tetap menyimpan UUID.

---

## 23.3 Document type harus konsisten

Dokumen seperti:

- SPK;
- PO;
- kontrak;
- BAST;
- surat jalan;

boleh menjadi `Evidence-Only`.

Tetapi bukti transfer/bukti pembayaran **tidak boleh otomatis dianggap Evidence-Only** jika sebenarnya dapat membentuk atau mendukung transaksi keuangan.

Rule:

```text
Supporting Contract Document
→ evidence only

Financial Evidence
→ transaction candidate or match candidate

Ambiguous
→ review required
```

---

# 24. Status Model

Raw backend enum tidak boleh langsung dijadikan bahasa UI.

## 24.1 Document Analysis Status

```text
DITERIMA
MENUNGGU_ANALISIS
SEDANG_DIANALISIS
PERLU_DIPERIKSA
SELESAI_DIANALISIS
DITOLAK
GAGAL_ANALISIS
```

Label UI:

```text
Diterima
Menunggu Analisis
Sedang Dianalisis
Perlu Diperiksa
Selesai Dianalisis
Ditolak
Gagal Diproses
```

---

## 24.2 Approval Status

Terpisah:

```text
BELUM_DIAJUKAN
MENUNGGU_PERSETUJUAN
DISETUJUI
DITOLAK
```

---

## 24.3 Posting Status

Terpisah lagi:

```text
BELUM_DIPOSTING
TERPOSTING
DIBATALKAN
```

Dengan demikian:

`Disetujui` tidak berarti otomatis `Terposting` jika sistem memang memisahkan kedua event.

---

## 24.4 UI Status Dokumen

Di tabel dokumen tampilkan dua status bila relevan:

```text
Analisis: Selesai
Accounting: Terposting
```

atau:

```text
Analisis: Perlu Diperiksa
Accounting: Belum Diposting
```

Ini lebih jelas daripada satu badge yang mencampur seluruh lifecycle.

---

# 25. Transactions Page

Pertahankan desain tabel sekarang.

Perbaikan:

1. default sort berdasarkan **Tanggal Transaksi DESC**, bukan created_at;
2. kode transaksi clickable;
3. tampilkan kategori Owner-facing;
4. status Bahasa Indonesia;
5. filter:
   - Semua;
   - Siap Posting;
   - Terposting;
   - Perlu Diperiksa;
   - Dibatalkan;
6. pencarian mencakup:
   - nomor;
   - vendor/customer;
   - project;
   - keterangan;
   - nominal.

Row dapat membuka detail:

```text
Transaksi
Dokumen
Project
Counterparty
Journal
Audit Trail
```

---

# 26. Dokumen Bukti

Table saat ini sudah cukup baik.

Perbaikan:

- `REJECTED` → `Ditolak`;
- `PROCESSED` → `Selesai Dianalisis`;
- nama file asli jika tersedia;
- source badge:
  - WhatsApp;
  - Upload Web;
  - Bank Import;
- status accounting terpisah;
- preview image/PDF sebenarnya jika browser dapat merender;
- jika preview tidak tersedia, tampilkan reason + tombol download.

---

# 27. Piutang dan Utang

## Piutang

Owner harus dapat melihat:

```text
Belum Jatuh Tempo
1–30 Hari
31–60 Hari
61–90 Hari
>90 Hari
Total Piutang
```

## Utang

Sama.

Action:

```text
Catat Pembayaran
```

bukan edit saldo manual.

Aging berasal dari invoice/bill + settlement.

---

# 28. Budget vs Actual

Jika project belum mempunyai RAB/budget:

Jangan pura-pura menampilkan perbandingan.

Tampilkan:

> **Project ini belum memiliki anggaran yang ditetapkan. Saat ini hanya realisasi biaya yang dapat ditampilkan.**

CTA opsional:

```text
Tambah Anggaran
```

Jika Owner memang belum membutuhkan RAB, fitur tetap boleh dipakai sebagai `Realisasi Biaya Proyek`.

---

# 29. Buku Besar

Desain saat ini dipertahankan.

Perbaikan:

- account dropdown searchable;
- kode + nama;
- opening balance jelas;
- debit;
- kredit;
- running balance;
- link ke journal;
- link dari journal ke source transaction/document;
- format tanggal konsisten.

Advanced accounting page boleh memakai kode akun.

---

# 30. Accounting Period

Halaman periode akuntansi harus menjadi guardrail.

Status:

```text
OPEN
SOFT CLOSED
CLOSED
```

Bahasa UI:

```text
Terbuka
Ditutup Sementara
Ditutup
```

Rule:

- transaksi draft boleh dibuat sesuai kebijakan;
- posting ke periode CLOSED dilarang;
- reopening memerlukan role/persetujuan yang tepat;
- seluruh perubahan dicatat audit trail.

---

# 31. Empty State

Jangan hanya menampilkan area kosong.

Contoh Projects:

> Belum ada proyek.<br>
> Tambahkan proyek pertama agar transaksi dapat dialokasikan dan profitabilitas dapat dihitung.

Button:

`Tambah Proyek`

Contoh Review:

> Tidak ada transaksi yang membutuhkan pemeriksaan.

Contoh Fixed Asset:

> Belum ada aset tetap terdaftar.

---

# 32. Error State

Error tidak boleh berupa:

- stack trace;
- raw HTTP;
- raw JSON;
- database error.

Owner-facing:

```text
Rekening koran belum dapat diproses.

Penyebab:
Format tanggal pada file tidak dikenali.

Tindakan:
Periksa format file lalu unggah kembali.

[ Coba Lagi ]
```

Detail technical tersedia untuk admin/developer melalui logs.

---

# 33. Formatting Rules

## Currency

Owner-facing:

```text
Rp 38.850.000
Rp 0
```

Tidak:

```text
38850000.00
```

Detail formal jika perlu:

```text
Rp 38.850.000,00
```

## Date

UI Indonesian:

```text
07/09/2026
```

atau:

```text
7 Sep 2026
```

Gunakan konsisten per context.

## Percentage

```text
32,0%
```

---

# 34. UI Language Policy

Owner-facing default: **Bahasa Indonesia**.

Istilah Inggris boleh menjadi keterangan sekunder:

```text
Utang Usaha (Accounts Payable)
Piutang Usaha (Accounts Receivable)
```

Jangan expose enum:

```text
REVIEW_REQUIRED
VENDOR_BILL
CUSTOMER_PAYMENT
```

sebagai label utama.

---

# 35. Accounting Detail Mode

Agar owner-friendly dan tetap audit-friendly:

Default:

```text
Mode Owner
```

Opsional:

```text
Lihat Detail Akuntansi
```

Detail accounting menampilkan:

- Journal ID;
- account code;
- debit;
- credit;
- source;
- posted at;
- posted by;
- reversal link.

Jangan tampilkan ini pada form transaksi utama.

---

# 36. Canonical Category vs COA

Gunakan dua layer:

```text
OWNER CATEGORY
        ↓
DETERMINISTIC ACCOUNTING RULE
        ↓
CANONICAL COA
```

Contoh:

```text
Bensin ke site proyek Ancol
        ↓
Transportasi / BBM Proyek
        ↓
Direct Project Cost
```

atau:

```text
Bensin ke bank untuk urusan kantor
        ↓
BBM / Transportasi Kantor
        ↓
Operating Expense
```

Ini mencegah Owner salah debit/kredit dan tetap membuat laporan konsisten.

---

# 37. Canonical Accounting Mapping Requirement

Satu COA authoritative harus dipakai oleh:

- transaction engine;
- journal engine;
- report engine;
- project profitability;
- Hermes classification;
- export;
- consultant reconciliation.

Tidak boleh ada:

```text
kategori sama → kode berbeda
```

tanpa alasan dan mapping eksplisit.

Sebelum implementasi kategori baru, Hermes harus audit COA existing lalu melakukan migration/mapping terkendali bila diperlukan.

---

# 38. Data Integrity Guardrails

Setiap release UX tidak boleh merusak:

```text
Total Debit = Total Kredit
Total Aset = Total Liabilitas + Ekuitas
Laba periode berjalan = nilai yang masuk ke ekuitas
No orphan journal detail
No cross-tenant data
No direct WhatsApp posting
No duplicate financial mutation
No posted transaction destructive edit
```

---

# 39. WhatsApp UX

Operating model sekarang:

```text
PC ON
→ Baileys connected
→ incoming WhatsApp captured
→ Document
→ OCR / extraction
→ candidate
→ review if required
```

Saat PC OFF:

capture WhatsApp deferred sesuai keputusan local-first saat ini.

Jangan mengubah kembali requirement menjadi VPS/always-on sampai Owner mengambil keputusan baru.

---

# 40. WhatsApp Message Policy

WhatsApp bukan tempat accounting approval.

Bot cukup memberi acknowledgement sederhana jika diperlukan.

Contoh:

```text
Dokumen diterima dan akan diproses oleh sistem keuangan.
```

Jangan melakukan percakapan panjang mengenai debit/kredit via WhatsApp.

---

# 41. UX Priorities — Implementation Order

## P0 — Critical

1. raw JSON pada Document Review disembunyikan dari Owner;
2. raw Project ID dan Counterparty ID diganti dropdown/autocomplete;
3. status document / approval / posting dipisahkan;
4. transaction classification context `Proyek vs Kantor` diterapkan;
5. PPh Final ditambahkan ke struktur Laba Rugi;
6. evidence-only rule dibetulkan untuk financial evidence;
7. canonical COA mapping diaudit.

## P1 — High

8. Dashboard Insight diformat Owner-friendly;
9. Transaction page sort berdasarkan transaction date;
10. semua enum Inggris diganti label Indonesia;
11. Profitabilitas Proyek diberi label `belum termasuk overhead/pajak`;
12. Retensi customer/vendor masuk project detail;
13. Budget vs Actual empty state dibetulkan.

## P2 — Medium

14. searchable dropdown;
15. hide zero rows;
16. empty states actionable;
17. consolidated formatting;
18. fixed asset depreciation preview;
19. drilldown laporan ke transaction/journal/document.

---

# 42. Acceptance Criteria

UX release dinyatakan PASS jika:

1. Owner dapat mencatat pembelian material tanpa tahu debit/kredit.
2. Owner dapat membedakan biaya proyek dan kantor dengan satu pertanyaan konteks.
3. Fee dapat diklasifikasikan proyek vs non-proyek.
4. BBM dapat diklasifikasikan proyek vs kantor.
5. Listrik kantor masuk utilitas tanpa memilih akun manual.
6. Pembelian barang proyek masuk biaya langsung proyek.
7. Pembelian aset tidak otomatis menjadi beban jika memenuhi policy aset.
8. Pokok pinjaman tidak menjadi beban.
9. Tambahan modal tidak menjadi pendapatan.
10. Prive tidak menjadi beban.
11. PPh Final terpisah dari pajak creditable.
12. Laba Rugi memiliki `Laba Sebelum PPh Final` dan `Beban PPh Final`.
13. Neraca dapat menampilkan pajak dibayar dimuka, retensi, aset/liabilitas kontrak bila memiliki saldo.
14. Profitabilitas proyek tidak mengklaim sebagai laba bersih.
15. Raw JSON tidak terlihat pada workflow normal Owner.
16. Project/customer/vendor dipilih lewat nama, bukan UUID.
17. Dokumen memiliki status analisis dan status accounting yang jelas.
18. Posted transaction hanya dikoreksi melalui reversal.
19. Dashboard tidak menampilkan raw field English/raw decimal.
20. Semua journal tetap balance setelah perubahan UX.

---

# 43. Out of Scope untuk UX Release Ini

Tidak termasuk:

- VPS;
- deployment cloud always-on;
- rewrite backend accounting engine;
- Meta WhatsApp reactivation;
- payroll system penuh;
- inventory/WMS penuh;
- procurement ERP penuh;
- automatic tax filing;
- unrestricted AI auto-posting;
- mobile-first redesign.

---

# 44. Owner Sign-Off Decisions

Keputusan yang dianggap dikunci untuk implementasi:

```text
1. Local-first tetap dipakai.
2. Tidak memakai VPS dulu.
3. WhatsApp hanya capture, bukan approval.
4. Owner tidak memilih debit/kredit.
5. Single input dipertahankan.
6. Konteks Proyek vs Kantor harus ditentukan sebelum kategori.
7. PPh Final dipisahkan dari PPh creditable.
8. Retensi menjadi konsep eksplisit.
9. Profitabilitas proyek = laba kotor proyek, bukan laba bersih.
10. Laba Rugi mengikuti struktur konsultan yang diperbarui.
11. Neraca backend lengkap, UI boleh menyembunyikan akun nol.
12. Satu canonical COA menjadi source of truth.
13. Raw technical data tidak ditampilkan di workflow normal Owner.
14. Accounting invariants tidak boleh dilemahkan demi UX.
```

---

# 45. Target End State

Owner workflow ideal:

```text
BUKA FINANCIAL SAAS
        ↓
LIHAT KONDISI KEUANGAN
        ↓
INPUT / TERIMA DOKUMEN
        ↓
PILIH KONTEKS BISNIS
Proyek / Kantor / Modal / Pinjaman / Pajak
        ↓
SISTEM SARANKAN KATEGORI
        ↓
OWNER KONFIRMASI JIKA DIPERLUKAN
        ↓
ACCOUNTING ENGINE
        ↓
JOURNAL / AR / AP / CASH / PROJECT
        ↓
LAPORAN
```

Owner berpikir dalam bahasa bisnis.

Sistem berpikir dalam bahasa akuntansi.

Keduanya tidak boleh tercampur pada form utama.

---

# 46. Final Product Rule

> **Financial SaaS harus terasa seperti aplikasi pengelolaan keuangan perusahaan kontraktor untuk Owner, tetapi di belakang layar berperilaku seperti sistem akuntansi yang disiplin.**

UX boleh sederhana.

Accounting tidak boleh disederhanakan sampai salah.
