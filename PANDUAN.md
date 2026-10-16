# MPM YouTube Monitoring: panduan cepat (Windows)

Mencari video YouTube untuk **3 tier keyword** lewat **YouTube Data API v3**, lalu membuat **dashboard.html**
interaktif yang dibuka di browser:

| Tier | Isi | Cara dicari |
|---|---|---|
| 1 · MPM | 29 keyword entitas MPM | setiap run, video **terbaru** 30 hari terakhir (semua yang menyebut MPM) |
| 2 · Industri | 95 istilah industri (7 cluster) | bergiliran, video **paling banyak ditonton** 14 hari terakhir |
| 3 · Pesaing | 51 pesaing/peer (6 kategori bisnis) | bergiliran, video **paling banyak ditonton** 14 hari terakhir |
Tidak perlu install paket, tidak perlu server: cukup Python dan satu kunci API (gratis).

## 1. Buat kunci API YouTube (sekali, ±5 menit)

a. Buka **console.cloud.google.com** dan login dengan akun Google (boleh akun pribadi).
b. Di atas, klik pemilih project → **New Project** → beri nama mis. `mpm-youtube` → **Create**.
c. Menu ☰ → **APIs & Services** → **Library** → cari **YouTube Data API v3** → **Enable**.
d. **APIs & Services** → **Credentials** → **+ Create credentials** → **API key** → salin kuncinya (diawali `AIza`).
e. (Disarankan) klik kunci itu → **API restrictions** → **Restrict key** → pilih *YouTube Data API v3* → **Save**.

Untuk kuota standar ini biasanya tidak perlu memasang kartu kredit.

## 2. Jalankan

1. Pastikan Python sudah terpasang (`python --version` di PowerShell; versi 3.9 ke atas).
2. Ekstrak zip ke folder biasa, mis. `C:\Projects\youtube_monitoring` (jangan di OneDrive).
3. **Klik dua kali `JALANKAN.bat`.** Pada run pertama, tempel kunci API saat diminta; kunci dicek dulu ke YouTube
   (1 unit, tanpa memakai kuota pencarian) lalu disimpan di `youtube_api_key.txt` (jangan dibagikan).
   Ganti kunci: hapus file itu, atau tempel kunci baru saat skrip memintanya.
4. Skrip menjalankan ±90 pencarian (±3–5 menit), lalu **dashboard terbuka sendiri di browser**.

Melihat dashboard lagi tanpa memanggil API: klik dua kali `LIHAT_DASHBOARD.bat`.

Pilihan lewat PowerShell di folder ini:
```powershell
python yt_crawl.py --hari 7         # tier 1: hanya video 7 hari terakhir (default 30)
python yt_crawl.py --hari-hot 7     # tier 2/3: konten terpopuler 7 hari terakhir (default 14)
python yt_crawl.py --maks-cari 40   # pakai paling banyak 40 pencarian di run ini (default 90)
python yt_crawl.py --tanpa-cari     # hanya perbarui tayangan/suka video yang sudah tersimpan (hemat kuota)
python yt_crawl.py --dashboard      # buat ulang dashboard saja, tanpa API
```

## 3. Isi dashboard

- **Pilih tier** di atas: Semua tier, Tier 1 · MPM, Tier 2 · Industri, atau Tier 3 · Pesaing. Seluruh halaman ikut.
- **Filter**: periode terbit, pencarian teks, kelompok (grup perusahaan / cluster industri / kategori pesaing),
  channel, minimal tayangan, "Hanya yang menyebut keyword", "Hanya baru".
- **🔥 Hot topics**: keyword (atau kelompok) yang paling banyak ditonton sekarang, diurutkan menurut
  **laju tayangan per hari**, dengan grafik mini 14 hari dan **tren 7 hari** (jumlah video 7 hari terakhir
  dibanding 7 hari sebelumnya; "baru" = belum ada sebelumnya). Klik baris untuk melihat videonya.
- **🔥 Hot content**: 8 video dengan laju tayangan tertinggi. Label 🔥 HOT di kartu = 10% teratas.
- **Laju tayangan** = kenaikan tayangan per hari antara dua run (bila sudah diukur di dua hari berbeda), atau
  rata-rata tayangan per hari sejak video terbit. Ini ukuran "hot" yang dipakai di seluruh dashboard.
- **Angka utama:** jumlah video, channel, total tayangan, laju tayangan, engagement ((suka + komentar) ÷ tayangan),
  dan video baru di run terakhir.
- **Grafik** (arahkan kursor untuk angka; klik untuk memfilter): video per hari (ditumpuk per tier, atau per
  kelompok bila satu tier dipilih), per tier/kelompok, channel teratas, keyword yang paling banyak dibahas.
- **Daftar video** sebagai kartu (thumbnail, durasi, label BARU, keyword yang cocok) atau **tabel** yang bisa
  diurutkan; klik video untuk detail lengkap (deskripsi, statistik, subscriber channel, riwayat tayangan).
  **Unduh CSV** menyimpan hasil yang sedang difilter (bisa dibuka di Excel).
- Tema terang/gelap ikut setelan Windows; tombol **◐ Tema** untuk mengganti.

**"Hanya yang menyebut keyword"** (aktif bawaan): pencarian YouTube juga mengembalikan video yang hanya "mirip".
Dashboard menandai video yang judul, deskripsi, atau tag-nya benar-benar memuat keyword:
- **Tier 1** frasa persis, aturan sama dengan crawler berita: `MPM`, `MPMX`, `JMFI`, `AUKSI` hanya huruf kapital;
  "MPM" untuk QRIS/Majelis Permusyawaratan Mahasiswa diabaikan; "MPM" di dalam "MPM Honda Jatim" tidak dihitung dua kali.
- **Tier 2** semua kata dari *kata_pencarian* (atau dari keyword Inggrisnya) harus muncul; kata "Indonesia" diabaikan.
- **Tier 3** nama atau salah satu *alias* (mis. "ACA" untuk Asuransi Central Asia; alias kapital hanya cocok bila kapital).

Hasil "mirip" tier 2/3 langsung dibuang supaya data tetap ringkas; hasil "mirip" tier 1 disimpan untuk dicek.
Matikan pilihan ini untuk melihat hasil "mirip" tier 1.

**Memutar video:** karena dashboard dibuka sebagai file di komputer, YouTube tidak mengizinkan video diputar
di dalam halaman, jadi klik "Putar di YouTube" untuk membukanya di tab baru. Bila dashboard nanti
ditaruh di server web, pemutar langsung tampil di dalam dashboard.

## 4. Kuota (gratis, dicek 16 Okt 2026 di developers.google.com/youtube/v3/determine_quota_cost)

- Pencarian (`search.list`): **100 panggilan per hari**. Ketiga tier butuh ±165 kata pencarian, jadi:
  tier 1 (21 pencarian) dicari setiap run, sisanya (±69 per hari) dipakai **bergiliran** untuk tier 2 & 3, yang paling
  lama belum dicari didahulukan (status di `data\pencarian.json`). Semua tercakup **kira-kira tiap 2–3 hari**.
  Baris di bawah pemilih tier menunjukkan berapa kata pencarian yang diperbarui dalam 48 jam terakhir.
- Cukup **satu run per hari**. Run kedua di hari yang sama hanya memakai sisa jatah (±5 pencarian, tier 1)
  tetapi tetap memperbarui tayangan semua video. Skrip berhenti sendiri di 95.
- Statistik video/channel: 10.000 unit per hari, 1 unit per 50 video; praktis tidak pernah habis.
- Kuota direset tengah malam waktu Pasifik (sekitar pukul 14.00–15.00 WIB). Pemakaian hari ini tampil di
  pojok kanan atas dashboard.

## 5. Mengubah keyword

Buka **`keywords.xlsx`** di Excel (sheet *Keywords*; penjelasan tiap kolom ada di sheet *Petunjuk*), simpan, lalu jalankan lagi:
- `tier` 1/2/3 dan `kelompok` (dipakai untuk filter dan warna di dashboard).
- `kata_pencarian`: teks yang dicari di YouTube. **Tier 2 sudah diisi terjemahan bahasa Indonesia** (mis.
  "motorcycle sales Indonesia" → "penjualan sepeda motor") karena konten YouTube Indonesia berbahasa Indonesia.
  Ini usulan awal, silakan diubah.
- `alias` (tier 3): nama lain pesaing, dipisah `|` (mis. `Asuransi Central Asia|ACA`). Juga usulan awal.
- `huruf_kapital` = `ya`: harus persis kapital. `cari_di_youtube` = `tidak`: tidak dicari (hemat kuota) tetapi
  tetap dipakai untuk menandai video. `kecuali`: teks yang membatalkan kecocokan, dipisah `|`.
- Menambah keyword: tambah baris. Setiap kata pencarian baru menambah 1 pencarian per putaran giliran.

## 6. Bagikan lewat URL / otomatis tanpa laptop

Lihat **PASANG_DI_GITHUB.md**: GitHub menjalankan pencarian tiap pagi dan memasang dashboard di alamat web
yang bisa dibuka orang lain (gratis).

## 7. Otomatis setiap hari di laptop (opsional)

Task Scheduler → **Create Basic Task** → Daily, mis. 07:00 → *Start a program* →
Program: `C:\Projects\youtube_monitoring\JALANKAN.bat` → Finish. Komputer harus menyala.
(Hapus baris `pause` di JALANKAN.bat agar jendelanya menutup sendiri.)

## Bila ada masalah

| Pesan | Solusi |
|---|---|
| `YouTube menolak kunci ...` | skrip langsung meminta kunci baru: tempel kunci dari Credentials (39 karakter, diawali `AIza`). Baris `Memakai kunci ... dari ...` menunjukkan asal kunci; kunci di `youtube_api_key.txt` selalu dipakai lebih dulu daripada variabel Windows `YOUTUBE_API_KEY` |
| `YouTube Data API v3 belum diaktifkan` | ulangi langkah 1c di project yang sama dengan kuncinya |
| `Kuota YouTube habis` / `Batas pencarian harian tercapai` | tunggu reset (±14.00–15.00 WIB) atau pakai `--tanpa-cari` |
| `python` tidak dikenali | pasang Python dari python.org, centang "Add python.exe to PATH" |
| Thumbnail tidak muncul | jaringan kantor memblokir `i.ytimg.com`; data tetap lengkap |

Data tersimpan di folder `data\` (`videos.json`, `pencarian.json`, `kuota.json`). Jangan dihapus bila ingin riwayat
tayangan dan urutan giliran tetap ada. Video yang terbit lebih dari 120 hari lalu dibuang otomatis (`--simpan-hari`).
