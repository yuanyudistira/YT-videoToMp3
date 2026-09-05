import shutil
import sys

import yt_dlp


def check_dependencies():
    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg tidak ditemukan.")
        print("Install ffmpeg terlebih dahulu dan pastikan tersedia di PATH.")
        sys.exit(1)


def download_playlist(url: str):
    ydl_opts = {
        # Download audio stream terbaik yang tersedia dari YouTube
        "format": "bestaudio/best",

        # Folder:
        # downloads/
        #   Playlist Name/
        #       001 - Song.mp3
        #       002 - Song.mp3
        "outtmpl": (
            "downloads/"
            "%(playlist_title)s/"
            "%(playlist_index)03d - %(title)s.%(ext)s"
        ),

        # Pastikan seluruh playlist diproses
        "noplaylist": False,

        # Jangan berhenti total jika satu video gagal / unavailable
        "ignoreerrors": True,

        # Convert audio menjadi MP3 320 kbps
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            },
            {
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        print("\nDownload selesai.")
        print("File tersimpan di folder: downloads/")

    except yt_dlp.utils.DownloadError as e:
        print(f"\nDownload gagal:\n{e}")

    except KeyboardInterrupt:
        print("\nDownload dihentikan oleh user.")

    except Exception as e:
        print(f"\nUnexpected error:\n{e}")


def main():
    check_dependencies()

    print("=" * 50)
    print("YouTube Playlist -> MP3 Downloader")
    print("=" * 50)

    url = input("\nMasukkan URL YouTube Playlist: ").strip()

    if not url:
        print("URL tidak boleh kosong.")
        sys.exit(1)

    if "youtube.com" not in url and "youtu.be" not in url:
        print("URL tampaknya bukan URL YouTube.")
        sys.exit(1)

    print("\nMemulai download...\n")

    download_playlist(url)


if __name__ == "__main__":
    main()