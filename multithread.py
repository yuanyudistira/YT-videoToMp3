from __future__ import annotations

import hashlib
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

URL_FILE = BASE_DIR / "playlist.txt"
DOWNLOAD_DIR = BASE_DIR / "downloads"
ARCHIVE_DIR = BASE_DIR / ".archive"

# Semua single video masuk ke folder ini.
SINGLES_FOLDER = "Singles"

# Jumlah URL (playlist/single video) yang diproses bersamaan.
MAX_WORKERS = 2

# Bitrate MP3 hasil konversi.
MP3_BITRATE = "320"


# ============================================================
# UTILITIES
# ============================================================

def check_dependencies() -> None:
    """Pastikan ffmpeg dan ffprobe tersedia di PATH."""
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]

    if missing:
        print(f"ERROR: dependency tidak ditemukan: {', '.join(missing)}")
        print("Install di Ubuntu/Debian dengan:")
        print("  sudo apt install ffmpeg")
        sys.exit(1)


def load_urls() -> list[str]:
    """
    Membaca playlist.txt.

    Satu URL per baris. Baris kosong dan baris yang diawali # diabaikan.
    File boleh berisi campuran URL playlist dan single video.
    """
    if not URL_FILE.exists():
        print(f"ERROR: file tidak ditemukan: {URL_FILE}")
        sys.exit(1)

    urls: list[str] = []

    with URL_FILE.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            urls.append(line)

    # Hapus duplicate URL sambil mempertahankan urutan.
    return list(dict.fromkeys(urls))


def is_explicit_playlist_url(url: str) -> bool:
    """
    Hanya URL /playlist?list=... yang dianggap playlist.

    Contoh watch?v=VIDEO&list=PLAYLIST tetap dianggap SINGLE VIDEO.
    Ini mencegah seluruh playlist ikut terdownload ketika user menyalin
    URL sebuah video yang kebetulan sedang diputar dari dalam playlist.
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.rstrip("/").lower()
        query = parse_qs(parsed.query)

        return (
            (host == "youtu.be" or host.endswith("youtube.com"))
            and path == "/playlist"
            and bool(query.get("list"))
        )
    except Exception:
        return False


def get_playlist_id(url: str) -> str:
    """Ambil playlist ID dari parameter ?list=..."""
    try:
        query = parse_qs(urlparse(url).query)
        playlist_id = query.get("list", [None])[0]
        if playlist_id:
            return playlist_id
    except Exception:
        pass

    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def get_video_id(url: str) -> str:
    """Ambil video ID dari beberapa bentuk URL YouTube umum."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path_parts = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query)

        # https://www.youtube.com/watch?v=VIDEO_ID
        video_id = query.get("v", [None])[0]
        if video_id:
            return video_id

        # https://youtu.be/VIDEO_ID
        if host == "youtu.be" and path_parts:
            return path_parts[0]

        # https://youtube.com/shorts/VIDEO_ID
        # https://youtube.com/live/VIDEO_ID
        # https://youtube.com/embed/VIDEO_ID
        if len(path_parts) >= 2 and path_parts[0].lower() in {"shorts", "live", "embed"}:
            return path_parts[1]
    except Exception:
        pass

    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def archive_path_for(url: str, is_playlist: bool) -> Path:
    """
    Playlist memakai archive terpisah per playlist.

    Semua single video memakai satu archive bersama karena semuanya masuk
    ke folder Singles. Archive playlist sengaja tidak digabung dengan
    singles agar video yang sama tetap dapat ada di folder playlist dan
    juga di folder Singles bila user memang memasukkan keduanya.
    """
    if is_playlist:
        return ARCHIVE_DIR / f"playlist_{get_playlist_id(url)}.txt"

    return ARCHIVE_DIR / "singles.txt"


# ============================================================
# DOWNLOAD
# ============================================================

def download_source(url: str, worker_id: int) -> dict[str, str | int]:
    is_playlist = is_explicit_playlist_url(url)
    source_type = "PLAYLIST" if is_playlist else "VIDEO"
    archive_path = archive_path_for(url, is_playlist)

    print()
    print("=" * 72)
    print(f"[Worker {worker_id}] START {source_type}")
    print(f"[Worker {worker_id}] {url}")
    print(f"[Worker {worker_id}] Archive: {archive_path.name}")
    print("=" * 72)

    ydl_holder: dict[str, yt_dlp.YoutubeDL] = {}

    def skip_existing_mp3(info: dict, *, incomplete: bool):
        """
        Fallback untuk file MP3 yang sudah ada tetapi belum tercatat archive.

        prepare_filename() memakai output template yang aktif, sehingga:
        - playlist diperiksa di folder playlist masing-masing
        - single video diperiksa di downloads/Singles/
        """
        if incomplete:
            return None

        ydl = ydl_holder.get("ydl")
        if ydl is None:
            return None

        try:
            source_path = Path(ydl.prepare_filename(info))
            mp3_path = source_path.with_suffix(".mp3")

            if mp3_path.is_file() and mp3_path.stat().st_size > 0:
                print(f"[Worker {worker_id}] SKIP existing MP3: {mp3_path}")

                # Backfill archive untuk koleksi yang sudah ada sebelum
                # fitur download_archive digunakan.
                try:
                    ydl.record_download_archive(info)
                except Exception as exc:
                    print(f"[Worker {worker_id}] Archive warning: {exc}")

                return f"MP3 already exists: {mp3_path.name}"

        except Exception as exc:
            print(f"[Worker {worker_id}] Existing-file check warning: {exc}")

        return None

    if is_playlist:
        # Playlist tetap mendapat folder sendiri berdasarkan playlist_title.
        output_template = (
            "%(playlist_title)s/"
            "%(playlist_index)03d - %(title)s.%(ext)s"
        )
    else:
        # Semua single video berada di satu folder.
        # Video ID dimasukkan ke nama file untuk mencegah collision ketika
        # dua video berbeda memiliki judul yang sama.
        output_template = (
            f"{SINGLES_FOLDER}/"
            "%(title)s [%(id)s].%(ext)s"
        )

    ydl_opts = {
        # Ambil stream audio terbaik yang tersedia dari YouTube.
        "format": "bestaudio/best",

        # Root output directory.
        "paths": {
            "home": str(DOWNLOAD_DIR),
        },

        # Struktur output tergantung playlist/single video.
        "outtmpl": output_template,

        # URL /watch?...&list=... tetap hanya satu video.
        "noplaylist": not is_playlist,

        # Jika satu item playlist unavailable/error, lanjutkan item lain.
        "ignoreerrors": True,

        # Jangan overwrite source yang sudah ada.
        "overwrites": False,

        # Cek file MP3 existing yang belum ada di archive.
        "match_filter": skip_existing_mp3,

        # ID video yang sudah sukses disimpan di sini.
        "download_archive": str(archive_path),

        # Resume partial download saat script dijalankan ulang.
        "continuedl": True,
        "nopart": False,

        # Network resiliency.
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "socket_timeout": 30,

        # Source .webm/.m4a tidak dipertahankan setelah MP3 sukses.
        "keepvideo": False,

        # Convert ke MP3 dan embed metadata.
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": MP3_BITRATE,
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl_holder["ydl"] = ydl
            result_code = ydl.download([url])

        return {
            "worker": worker_id,
            "url": url,
            "type": source_type,
            "status": "SUCCESS" if result_code == 0 else "PARTIAL",
        }

    except Exception as exc:
        return {
            "worker": worker_id,
            "url": url,
            "type": source_type,
            "status": "FAILED",
            "error": str(exc),
        }


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print()
    print("=" * 72)
    print("YouTube Playlist / Video -> MP3 Parallel Downloader")
    print("=" * 72)

    check_dependencies()

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    urls = load_urls()

    if not urls:
        print(f"Tidak ada URL di {URL_FILE.name}")
        return

    print(f"URL ditemukan    : {len(urls)}")
    print(f"Parallel workers : {MAX_WORKERS}")
    print(f"MP3 bitrate      : {MP3_BITRATE} kbps")
    print(f"Download folder  : {DOWNLOAD_DIR}")
    print(f"Singles folder   : {DOWNLOAD_DIR / SINGLES_FOLDER}")
    print(f"Archive folder   : {ARCHIVE_DIR}")

    results: list[dict[str, str | int]] = []

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    try:
        future_to_url = {
            executor.submit(download_source, url, index): url
            for index, url in enumerate(urls, start=1)
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]

            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "worker": "?",
                    "url": url,
                    "type": "UNKNOWN",
                    "status": "FAILED",
                    "error": str(exc),
                }

            results.append(result)

            worker = result.get("worker", "?")
            status = result.get("status", "UNKNOWN")
            source_type = result.get("type", "UNKNOWN")

            print()
            print("-" * 72)
            print(f"[Worker {worker}] {source_type}: {status}")

            if status == "FAILED":
                print(result.get("error", "Unknown error"))

            print("-" * 72)

    except KeyboardInterrupt:
        print()
        print("CTRL+C diterima. Membatalkan job yang belum mulai...")
        print("Download yang sudah menghasilkan .part dapat dilanjutkan saat run berikutnya.")
        executor.shutdown(wait=False, cancel_futures=True)
        return

    else:
        executor.shutdown(wait=True)

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    success = sum(result.get("status") == "SUCCESS" for result in results)
    partial = sum(result.get("status") == "PARTIAL" for result in results)
    failed = sum(result.get("status") == "FAILED" for result in results)

    print(f"Total   : {len(results)}")
    print(f"Success : {success}")
    print(f"Partial : {partial}")
    print(f"Failed  : {failed}")

    problems = [
        result
        for result in results
        if result.get("status") in {"FAILED", "PARTIAL"}
    ]

    if problems:
        print()
        print("URL yang perlu dicek ulang:")
        for result in problems:
            print(f"- {result['url']}")

    print()
    print("Selesai.")


if __name__ == "__main__":
    main()
