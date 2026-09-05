# YT-videoToMp3

Simple Python utility untuk mengunduh **YouTube playlist** dan **single YouTube video** sebagai MP3 menggunakan [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) dan FFmpeg.

Program membaca URL dari `playlist.txt`, lalu memproses beberapa URL secara paralel.

## Fitur

- Mendukung URL playlist YouTube.
- Mendukung URL single video YouTube.
- Playlist disimpan ke folder masing-masing berdasarkan nama playlist.
- Semua single video disimpan dalam satu folder `downloads/Singles/`.
- Mengambil audio terbaik yang tersedia dari YouTube lalu mengonversinya menjadi MP3 320 kbps.
- Multi-thread: beberapa playlist/video dapat diproses secara paralel.
- Tidak mengunduh ulang video yang sudah tercatat selesai.
- Memeriksa MP3 yang sudah ada sebagai fallback untuk download lama yang belum tercatat di archive.
- Mendukung resume file `.part` setelah koneksi terputus atau proses berhenti.
- Retry otomatis untuk gangguan jaringan.
- File `.webm` / `.m4a` source dihapus setelah konversi MP3 berhasil.
- URL `watch?v=...&list=...` dianggap sebagai **single video**, bukan seluruh playlist.

## Struktur Project

```text
YT-videoToMp3/
├── main.py
├── playlist.txt
├── .gitignore
├── .venv/
├── .archive/
│   ├── playlist_PLxxxxxxxx.txt
│   ├── playlist_PLyyyyyyyy.txt
│   └── singles.txt
└── downloads/
    ├── Nama Playlist A/
    │   ├── 001 - Lagu A.mp3
    │   ├── 002 - Lagu B.mp3
    │   └── ...
    ├── Nama Playlist B/
    │   └── ...
    └── Singles/
        ├── Judul Video A [VIDEO_ID].mp3
        └── Judul Video B [VIDEO_ID].mp3
```

Video ID ditambahkan pada nama file di folder `Singles` untuk mencegah collision jika dua video berbeda memiliki judul yang sama.

## Requirements

- Python 3.10 atau lebih baru
- `yt-dlp`
- FFmpeg + ffprobe

Script ini dikembangkan untuk berjalan baik pada Linux/Ubuntu, tetapi konsep yang sama dapat digunakan di OS lain.

## Installation — Ubuntu / Debian

### 1. Install Python dan FFmpeg

```bash
sudo apt update
sudo apt install python3 python3-venv ffmpeg
```

Cek:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

### 2. Buat virtual environment

Dari folder project:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Jika aktif, prompt terminal biasanya memiliki prefix `(.venv)`.

### 3. Install yt-dlp

```bash
python -m pip install -U pip
python -m pip install -U yt-dlp
```

Untuk update yt-dlp di kemudian hari:

```bash
python -m pip install -U yt-dlp
```

## Konfigurasi `playlist.txt`

Buat file:

```text
playlist.txt
```

Satu URL per baris. Playlist dan single video boleh dicampur.

Contoh:

```text
# Playlist
https://www.youtube.com/playlist?list=PLAAAAAAAAAAAA
https://www.youtube.com/playlist?list=PLBBBBBBBBBBBB

# Single videos
https://www.youtube.com/watch?v=XXXXXXXXXXX
https://youtu.be/YYYYYYYYYYY

# Video yang sedang dibuka dari dalam playlist tetap dianggap single video
https://www.youtube.com/watch?v=ZZZZZZZZZZZ&list=PLAAAAAAAAAAAA&index=5
```

Baris kosong diabaikan.

Baris yang dimulai dengan `#` dianggap komentar dan diabaikan.

Duplicate URL yang identik hanya diproses sekali dalam satu run.

## Menjalankan Program

Aktifkan virtual environment:

```bash
source .venv/bin/activate
```

Jalankan:

```bash
python main.py
```

## Output

### Playlist

URL playlist:

```text
https://www.youtube.com/playlist?list=PLAAAAAAAAAAAA
```

Misalnya playlist bernama `Reggae Indonesia`, hasilnya:

```text
downloads/
└── Reggae Indonesia/
    ├── 001 - Lagu A.mp3
    ├── 002 - Lagu B.mp3
    └── 003 - Lagu C.mp3
```

### Single Video

Single video tidak mendapatkan folder sendiri. Semua single video masuk ke:

```text
downloads/Singles/
```

Contoh:

```text
downloads/
└── Singles/
    ├── Bob Marley - Three Little Birds [abc123].mp3
    └── Another Song [xyz456].mp3
```

## Menghindari Download Ulang

Program menggunakan dua lapisan pengecekan.

### 1. Download archive

Setelah video berhasil diproses, ID video dicatat di `.archive/`.

Untuk playlist:

```text
.archive/playlist_PLAAAAAAAAAAAA.txt
```

Untuk single video:

```text
.archive/singles.txt
```

Pada run berikutnya, video yang sudah tercatat akan dilewati oleh yt-dlp.

Archive playlist dibuat terpisah per playlist. Ini disengaja agar video yang sama tetap bisa berada di dua folder playlist berbeda jika memang video tersebut terdapat di dua playlist.

Archive single video dibuat satu file bersama karena seluruh single video masuk ke folder `Singles` yang sama.

### 2. Existing MP3 check

Jika MP3 sudah ada tetapi belum tercatat di archive — misalnya file berasal dari download sebelum fitur archive digunakan — program akan mendeteksinya berdasarkan output path yang seharusnya.

Jika file ditemukan, download dilewati dan ID video dimasukkan ke archive.

## Resume Setelah Network Putus

yt-dlp menggunakan file `.part` untuk download yang belum selesai.

Contoh:

```text
Song Name.webm.part
```

Jika koneksi terputus, jangan hapus file `.part`.

Jalankan ulang:

```bash
python main.py
```

Program akan mencoba melanjutkan download yang belum selesai.

Video yang sudah sukses dan tercatat di archive akan dilewati.

## Parallel Download

Jumlah URL yang diproses bersamaan dikontrol oleh:

```python
MAX_WORKERS = 2
```

Default:

```text
2 worker
```

Artinya jika `playlist.txt` berisi 10 URL, maksimal dua URL aktif pada saat yang sama. Ketika salah satu selesai, worker akan mengambil URL berikutnya.

Untuk komputer dan koneksi yang lebih kuat, dapat dinaikkan misalnya:

```python
MAX_WORKERS = 3
```

atau:

```python
MAX_WORKERS = 4
```

Menambah worker terlalu tinggi tidak otomatis mempercepat proses. Bandwidth internet, CPU untuk FFmpeg, dan storage I/O akan menjadi bottleneck.

## MP3 320 kbps dan Kualitas Audio

Program menggunakan:

```python
"format": "bestaudio/best"
```

untuk mengambil audio source terbaik yang tersedia dari YouTube.

Setelah itu FFmpeg mengonversinya menjadi MP3 320 kbps.

Perlu dicatat: MP3 320 kbps tidak berarti source YouTube memiliki kualitas asli 320 kbps. Jika source menggunakan Opus/AAC dengan bitrate lebih rendah, transcoding ke MP3 320 kbps tidak menambah detail audio yang tidak ada pada source.

Jika prioritas utama adalah mempertahankan audio source YouTube tanpa transcoding lossy tambahan, simpan format original seperti Opus/WebM atau M4A. Project ini memilih MP3 karena kompatibilitasnya lebih luas.

## `.gitignore`

Rekomendasi:

```gitignore
.venv/
downloads/
.archive/
__pycache__/
*.pyc
```

`playlist.txt` boleh di-commit jika daftar URL memang ingin menjadi bagian dari konfigurasi repository.

## Troubleshooting

### `python: command not found`

Di luar virtual environment Ubuntu biasanya menggunakan:

```bash
python3
```

Aktifkan virtual environment:

```bash
source .venv/bin/activate
```

Setelah itu:

```bash
python --version
```

seharusnya menunjuk ke Python di `.venv`.

### `No module named yt_dlp`

Aktifkan venv dan install yt-dlp:

```bash
source .venv/bin/activate
python -m pip install -U yt-dlp
```

### `ffmpeg tidak ditemukan`

Ubuntu/Debian:

```bash
sudo apt install ffmpeg
```

### Ada `.webm` yang tertinggal

`.webm` adalah source audio yang digunakan sebelum konversi ke MP3. Setelah post-processing sukses, file source normalnya dihapus.

Jika `.webm` tertinggal, biasanya proses sebelumnya berhenti atau FFmpeg gagal sebelum cleanup selesai. Jangan langsung menghapus semua `.webm` sebelum memastikan MP3 pasangannya sudah berhasil dibuat.

### YouTube tiba-tiba gagal diekstrak

YouTube sering mengubah mekanisme internalnya. Update yt-dlp terlebih dahulu:

```bash
source .venv/bin/activate
python -m pip install -U yt-dlp
```

## Catatan Penggunaan

Gunakan downloader ini hanya untuk konten yang Anda miliki, konten yang memang diizinkan untuk diunduh, atau konten yang penggunaannya sesuai dengan hak dan ketentuan yang berlaku.
