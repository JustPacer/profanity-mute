# 🔇 ProfanityMute (AutoCens)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FFmpeg](https://img.shields.io/badge/ffmpeg-stream--copy-green.svg)](https://ffmpeg.org/)
[![Faster-Whisper](https://img.shields.io/badge/whisper-faster--whisper-purple.svg)](https://github.com/SYSTRAN/faster-whisper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Русская версия документации (README_RU.md)](README_RU.md)

**ProfanityMute** (AutoCens) is a fast, AI-powered tool designed for content creators, video editors, and streamers to automatically detect and attenuate/bleep swear words in long videos (stream VODs, highlights) with millisecond accuracy — **without re-encoding the video stream**.

---

## ✨ Key Features

- **⚡ Lossless & Ultra Fast (FFmpeg Direct Stream Copy)**: Video tracks are not re-encoded. Only modified audio is replaced. Processing 2+ hour 1080p videos takes seconds after speech recognition completes.
- **🎯 Human-like Accuracy**: Uses `faster-whisper` for word-level timestamps, smooth volume crossfades (fade-in / fade-out), and micro-padding to avoid clicks and clipped words.
- **🚀 NVIDIA CUDA GPU Acceleration**: Up to 8x speedup using NVIDIA Tensor Cores (`RTX/GTX`) with automatic DLL loading on Windows.
- **📌 DaVinci Resolve Timeline Markers Export**: Automatically exports `*_davinci_markers.csv` with UTF-8 BOM encoding. Import directly into DaVinci Resolve timeline with one click.
- **🔥 Hype / Emotional Peak Detector**: Detects profanity density to highlight the most intense rage/clutch moments for YouTube Shorts & TikTok clips.
- **📁 Toggleable Watch Folder (Auto Monitoring)**: Automatically picks up new stream recordings from OBS/Streamlabs upon completion and censors them in the background.
- **📊 Cumulative Statistics & Word Frequency**: Persistent JSON database (`data/stats.json`) tracking overall censored profanity count and word usage stats across all runs.
- **🔊 Flexible Censor Modes**:
  - `Volume Ducking (-24dB)` *(Recommended for editing)*
  - `Full Mute (0dB)`
  - `Classic Beep Tone (1000Hz)`

---

## 🛠 Installation

### Prerequisites
- **OS**: Windows 10 / 11, Linux, or macOS.
- **Python**: Version 3.10 or 3.11.
- **FFmpeg**: Installed or available on system.

### 1. Clone repository & install dependencies

```bash
git clone https://github.com/JustPacer/profanity-mute.git
cd profanity-mute
pip install -r requirements.txt
```

### 2. Enable NVIDIA GPU Acceleration (Recommended for RTX/GTX users)

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

---

## 🚀 Quick Start

### Graphical User Interface (GUI)

Launch the PyQt6 dark-themed GUI:

```bash
python main.py
```
*(or `python main.py --gui`)*

Features in GUI:
- Drag-and-drop video files (`.mp4`, `.mov`, `.mkv`).
- Select attenuation level (dB), Whisper model accuracy (`base`, `small`, `medium`, `large-v3`), and GPU device (`Auto`, `CUDA`, `CPU`).
- View cumulative profanity stats and word frequency charts.
- Configure Watch Folder monitoring tab.

### Command Line Interface (CLI)

Censor a video file with volume ducking at -24 dB:

```bash
python main.py my_stream.mp4 --mode volume_ducking --db -24 --model medium
```

Show all-time cumulative profanity statistics:

```bash
python main.py --stats
```

Monitor a directory for new OBS stream recordings:

```bash
python main.py --watch-dir "C:\Streams\OBS"
```

---

## 🎬 DaVinci Resolve Markers Workflow

1. Process your video using ProfanityMute.
2. Next to your output video, a marker file named `<video>_davinci_markers.csv` is generated.
3. Open your project in **DaVinci Resolve**.
4. Go to **File ➔ Import ➔ Timeline Markers...** and select the `.csv` file.
5. Red markers with exact profanity labels appear directly on your timeline.

---

## 📁 Project Structure

```text
profanity-mute/
├── main.py                   # Entry point (GUI & CLI)
├── config.json               # Application configuration
├── requirements.txt         # Dependencies
├── INSTALLATION_GUIDE.md     # Step-by-step installation guide (RU)
├── README_RU.md              # Documentation in Russian
├── core/
│   ├── transcriber.py        # Faster-Whisper & CUDA acceleration
│   ├── profanity_filter.py   # Regex profanity detector & whitelist
│   ├── audio_processor.py    # NumPy audio ducking & FFmpeg stream copy
│   ├── stats_manager.py      # Cumulative statistics manager
│   ├── export_manager.py     # DaVinci markers & hype moment detector
│   └── watch_folder.py       # Background watch folder monitor
├── data/
│   └── stats.json            # Cumulative profanity statistics database
└── gui/
    └── app.py                # PyQt6 GUI application
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
