# ProfanityMute (AutoCens)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FFmpeg](https://img.shields.io/badge/ffmpeg-stream--copy-green.svg)](https://ffmpeg.org/)
[![Faster-Whisper](https://img.shields.io/badge/whisper-faster--whisper-purple.svg)](https://github.com/SYSTRAN/faster-whisper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Русская версия документации (README_RU.md)](README_RU.md) | [Инструкция по установке (INSTALLATION_GUIDE.md)](INSTALLATION_GUIDE.md)

ProfanityMute is a Python utility designed for streamers, video editors, and content creators who edit long stream VODs and highlights. It automates speech recognition, detects profanity with word-level timestamps, attenuates or mutes swear words, and exports timeline markers directly for video editing software like DaVinci Resolve.

Unlike traditional tools that force full video re-encoding, ProfanityMute utilizes FFmpeg Direct Stream Copy. Video tracks remain untouched, processing a 2+ hour 1080p stream recording in seconds after transcription completes.

---

## Key Features

* **FFmpeg Direct Stream Copy**: Video streams are copied without re-encoding. Only the audio track is extracted, modified, and remuxed back into the container (.mp4, .mov, .mkv).
* **Stem-Level (Root-Only) Muting**: Instead of muting an entire word (e.g. *"za-e-bal-sya"*), the algorithm calculates the exact time boundaries of the profanity root (*"za...sya"*). Prefixes and endings remain audible, producing natural, hand-edited audio suitable for YouTube monetization.
* **DaVinci Resolve Timeline Markers**: Automatically exports `.edl` (with `01:00:00:00` start timecode offset) and `.csv` marker files. Markers import directly onto your active timeline with exact timestamps and word labels.
* **Fine-Tuned Russian Speech Model**: Supports `antony66/whisper-large-v3-russian` (via CTranslate2 `bzikst/faster-whisper-large-v3-russian`) for higher recognition accuracy on Russian gaming speech, slang, and fast stream chatter.
* **Standalone Audio & Video Support**: Accepts video containers (`.mp4`, `.mov`, `.mkv`, `.avi`) as well as isolated audio tracks (`.wav`, `.mp3`, `.m4a`, `.flac`, `.aac`).
* **Profanity Heatmap & Transcript Inspector**: Built-in dark GUI tab featuring a per-minute profanity density graph and a searchable speech transcript viewer with highlighted profanity to verify timestamp accuracy.
* **GPU Acceleration**: Native NVIDIA CUDA acceleration on Windows (`RTX/GTX`) with automatic DLL registration.
* **Watch Folder Monitoring**: Background monitor for OBS/Streamlabs recording directories that automatically processes new stream recordings upon completion.

---

## Installation

### Requirements
* **OS**: Windows 10 / 11, Linux, or macOS.
* **Python**: 3.10 or 3.11.
* **FFmpeg**: Installed and available on system PATH.

### 1. Clone repository & install dependencies

```bash
git clone https://github.com/JustPacer/profanity-mute.git
cd profanity-mute
pip install -r requirements.txt
```

### 2. Enable NVIDIA GPU Acceleration (Optional for RTX/GTX users)

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

---

## Quick Start

### Graphical User Interface (GUI)

Launch the PyQt6 interface:

```bash
python main.py
```

GUI capabilities:
* Drag-and-drop media files (`.mp4`, `.mov`, `.wav`, `.mp3`).
* Toggle root-only muting and DaVinci markers export.
* Select attenuation mode (Volume Ducking -24dB, Mute, or Beep tone).
* View profanity heatmap and search full speech transcript.
* Configure Watch Folder background directory monitoring.

### Command Line Interface (CLI)

Process a video file with volume ducking at -24 dB:

```bash
python main.py my_stream.mp4 --mode volume_ducking --db -24 --model antony66/whisper-large-v3-russian
```

Display cumulative profanity statistics across all processed files:

```bash
python main.py --stats
```

Run background directory monitoring for OBS recordings:

```bash
python main.py --watch-dir "C:\Streams\OBS"
```

---

## Importing Markers into DaVinci Resolve

1. Process your video or audio file in ProfanityMute.
2. Open your project and target timeline in **DaVinci Resolve**.
3. In the **Media Pool** panel (top-left), right-click on your **Timeline** icon.
4. Navigate to **Timelines ➔ Import ➔ Timeline Markers from EDL...**.
5. Select the generated `*_davinci_markers.edl` file.
6. Red markers with profanity labels will populate directly on your active timeline.

---

## Project Structure

```text
profanity-mute/
├── main.py                   # Main entry point (GUI & CLI)
├── config.json               # Application configuration
├── requirements.txt         # Dependencies
├── INSTALLATION_GUIDE.md     # Installation & user guide (RU)
├── README.md                 # Technical documentation (EN)
├── README_RU.md              # Technical documentation (RU)
├── LICENSE                   # MIT License
├── core/
│   ├── transcriber.py        # Faster-Whisper wrapper & CUDA setup
│   ├── profanity_filter.py   # Regex detector, root calculator & whitelist
│   ├── audio_processor.py    # NumPy audio ducking & FFmpeg stream copy
│   ├── stats_manager.py      # Cumulative statistics manager
│   ├── export_manager.py     # DaVinci markers (EDL/CSV) & heatmap calculator
│   └── watch_folder.py       # Background directory monitor
├── data/
│   └── stats.json            # Cumulative profanity statistics storage
└── gui/
    └── app.py                # PyQt6 GUI application
```

---

## License

This project is released under the [MIT License](LICENSE).
