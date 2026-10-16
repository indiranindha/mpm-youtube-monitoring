# Dashboard bisa dibuka orang lain lewat URL (GitHub Pages)

Hasil akhir: alamat tetap seperti `https://namakamu.github.io/mpm-youtube-monitoring/` yang bisa dibuka siapa saja
dari laptop atau HP. GitHub menjalankan pencarian YouTube **otomatis tiap pagi pukul ±06.17 WIB**, laptopmu tidak
perlu menyala. Gratis. Karena dibuka lewat https, **video bisa diputar langsung di dalam dashboard**.
Semua langkah lewat browser, tanpa install apa pun (±15 menit, sekali saja).

## Penting dibaca dulu: siapa yang bisa melihat

- Pada akun GitHub gratis, GitHub Pages hanya tersedia untuk repository **Public**. Artinya **siapa pun yang tahu
  URL-nya bisa membuka dashboard**, dan isi repository (kode + `data/videos.json`) juga bisa dilihat publik.
  Videonya sendiri memang publik di YouTube, tetapi daftar keyword dan rangkuman pantauan MPM ikut terlihat.
- **Kunci API tetap rahasia**: disimpan sebagai *Secret* di GitHub, tidak pernah masuk ke repository atau dashboard.
- Bila dashboard hanya boleh dibuka orang tertentu (mis. email kantor), pakai cara di bagian "Akses terbatas" di bawah.

## 1. Buat repository

1. Login / daftar di **github.com**.
2. Klik **+** (kanan atas) → **New repository**.
3. Repository name: `mpm-youtube-monitoring` · pilih **Public** · biarkan yang lain → **Create repository**.

## 2. Unggah file

1. Di halaman repository baru, klik **uploading an existing file**.
2. Dari folder `youtube_monitoring` di komputermu, seret file-file ini ke browser:
   `yt_crawl.py`, `dashboard_template.html`, `keywords.xlsx`, `PANDUAN.md`, `PASANG_DI_GITHUB.md`,
   `JALANKAN.bat`, `LIHAT_DASHBOARD.bat`.
   Bila ingin riwayat yang sudah ada ikut, seret juga folder **`data`** (berisi `videos.json` dan `pencarian.json`).
   **Jangan** unggah `youtube_api_key.txt` dan `dashboard.html`.
3. Klik **Commit changes**.

## 3. Tambahkan workflow (jadwal otomatis)

Folder berawalan titik kadang tidak ikut terunggah, jadi buat file ini langsung di GitHub:

1. Klik **Add file** → **Create new file**.
2. Di kolom nama, ketik persis: `.github/workflows/youtube.yml` (garis miring otomatis membuat folder).
3. Buka file `.github\workflows\youtube.yml` dari zip dengan Notepad, salin seluruh isinya, tempel ke GitHub.
4. Klik **Commit changes** → **Commit changes**.

## 4. Simpan kunci API sebagai Secret

1. Di repository: **Settings** → (menu kiri) **Secrets and variables** → **Actions**.
2. **New repository secret** → Name: `YOUTUBE_API_KEY` → Secret: tempel kunci API (diawali `AIza`) → **Add secret**.

Di Google Cloud Console, kunci ini sebaiknya: *Application restrictions* = **None** (GitHub memakai alamat IP
yang berganti-ganti) dan *API restrictions* = **YouTube Data API v3**.

## 5. Aktifkan GitHub Pages

**Settings** → **Pages** → bagian *Build and deployment* → **Source: GitHub Actions**.

## 6. Jalankan pertama kali

1. Tab **Actions** → bila diminta, klik **I understand my workflows, go ahead and enable them**.
2. Pilih **YouTube monitoring** (kiri) → **Run workflow** → **Run workflow**.
3. Tunggu ±2 menit sampai tanda centang hijau. Klik run tersebut: URL dashboard tampil di kotak
   *crawl-and-publish* (juga di **Settings → Pages**).
4. Bagikan URL itu. Mulai besok dashboard diperbarui otomatis setiap pagi.

## Sehari-hari

- **Perbarui sekarang:** Actions → YouTube monitoring → Run workflow (bisa juga mengisi jumlah hari).
- **Ubah keyword:** edit `keywords.xlsx` di Excel, lalu di GitHub **Add file → Upload files** → seret file itu → Commit
  (menimpa yang lama). Berlaku di run berikutnya.
- **Ubah jam:** edit baris `cron: "17 23 * * *"` di `.github/workflows/youtube.yml`. Waktunya UTC (WIB − 7 jam),
  contoh `17 23 * * *` = 06.17 WIB, `17 5 * * *` = 12.17 WIB. Tambah baris `- cron:` lagi untuk dua kali sehari.
- **Kuota bersama:** run di GitHub dan run di laptop memakai kunci yang sama, jadi berbagi 100 pencarian/hari.
  Cukup satu run per hari (tier 2 & 3 dicari bergiliran memakai sisa jatah). Setelah pindah ke GitHub, cukup pakai
  URL-nya; tidak perlu menjalankan JALANKAN.bat lagi.
- **Bila run gagal**, GitHub mengirim email ke akunmu. Pesan error ada di Actions → run yang merah → langkah
  *Crawl YouTube and build dashboard*. Yang paling umum: kunci salah → perbarui Secret (langkah 4).
- GitHub bisa menunda jadwal beberapa menit, dan menonaktifkan jadwal di repository Public yang tidak ada aktivitas
  selama 60 hari. Workflow ini menyimpan data setiap hari, jadi biasanya tetap aktif. Bila sempat nonaktif, tab
  Actions menampilkan tombol untuk mengaktifkannya lagi.

## Akses terbatas (hanya orang tertentu)

GitHub Pages gratis tidak bisa dikunci dengan login. Pilihan bila dashboard tidak boleh publik:

1. **Cloudflare Pages + Cloudflare Access** (gratis sampai 50 pengguna): dashboard di-host Cloudflare, pembuka
   harus memasukkan email kantor lalu kode verifikasi. Workflow GitHub di atas tetap dipakai untuk menjalankan
   pencarian; hanya tujuan publikasinya yang diganti.
2. **GitHub Enterprise** (bila kantor sudah memakainya): repository Private dengan Pages yang hanya bisa dibuka
   anggota organisasi.
3. **Dashboard di server kantor / Google Cloud** bersama media monitoring berita (v1.x), dengan login perusahaan.

Minta bantuan Claude untuk menyiapkan pilihan 1 bila perlu.
