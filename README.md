# YT-videoToMp3

INSTALASI:
# 1. Dependency project
sudo apt install python3-venv ffmpeg

# 2. Masuk project
cd ~/GIT/YT-videoToMp3

# 3. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Python dependencies
python -m pip install -U pip
python -m pip install -U yt-dlp

# 5S. Run
python main.py

