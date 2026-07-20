import os
import sys
import re
import subprocess
import shutil
import logging
import wave
import numpy as np
from typing import List, Dict, Callable, Optional, Tuple

class AudioProcessor:
    """
    Класс для быстрой обработки аудио и пересборки видео/аудио через FFmpeg (Stream Copy).
    Поддерживает видео (MP4, MOV, MKV) и аудиофайлы (WAV, MP3, M4A, AAC, FLAC).
    """

    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_exe = ffmpeg_path or self.find_ffmpeg()
        logging.info(f"Используемый FFmpeg: {self.ffmpeg_exe}")

    @staticmethod
    def find_ffmpeg() -> str:
        """Автоматический поиск ffmpeg.exe в системе и известных директориях."""
        if shutil.which("ffmpeg"):
            return "ffmpeg"

        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.exists(exe):
                return exe
        except Exception:
            pass

        possible_paths = [
            r"C:\Program Files\SteelSeries\GG\apps\moments\ffmpeg.exe",
            r"C:\Program Files\Streamlabs OBS\resources\app.asar.unpacked\node_modules\obs-studio-node\ffmpeg.exe",
            r"C:\Program Files (x86)\TwitchLink\_internal\resources\dependencies\windows\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            os.path.expanduser(r"~\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe")
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return "ffmpeg"

    def is_audio_file(self, file_path: str) -> bool:
        """Проверяет, является ли файл аудиофайлом (а не видео)."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.AUDIO_EXTENSIONS

    def get_media_duration(self, file_path: str) -> float:
        """Возвращает точную длительность медиафайла в секундах."""
        if not os.path.exists(file_path):
            return 0.0

        if file_path.endswith('.wav'):
            try:
                with wave.open(file_path, 'rb') as wf:
                    return wf.getnframes() / float(wf.getframerate())
            except Exception:
                pass

        try:
            cmd = [self.ffmpeg_exe, "-i", file_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
            match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', result.stderr)
            if match:
                hours, mins, secs = match.groups()
                return float(hours) * 3600.0 + float(mins) * 60.0 + float(secs)
        except Exception as e:
            logging.error(f"Не удалось определить длительность {file_path}: {e}")

        return 0.0

    def extract_audio(self, media_path: str, output_wav_path: str) -> float:
        """Извлекает/конвертирует 16-bit PCM WAV аудиодорожку из видео или аудиофайла."""
        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-i", media_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            output_wav_path
        ]
        
        logging.info(f"Извлечение/конвертация аудио из {media_path}...")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
        if result.returncode != 0:
            raise RuntimeError(f"Ошибка FFmpeg при извлечении аудио: {result.stderr}")

        return self.get_media_duration(output_wav_path)

    @staticmethod
    def merge_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Объединяет пересекающиеся интервалы времени."""
        if not intervals:
            return []
        
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged = [sorted_intervals[0]]

        for current in sorted_intervals[1:]:
            prev_start, prev_end = merged[-1]
            curr_start, curr_end = current
            
            if curr_start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, curr_end))
            else:
                merged.append(current)

        return merged

    def read_wav(self, wav_path: str) -> Tuple[int, np.ndarray, int]:
        """Считывает WAV файл с помощью scipy или wave."""
        try:
            from scipy.io import wavfile
            sample_rate, data = wavfile.read(wav_path)
            num_channels = 2 if len(data.shape) == 2 else 1
            return sample_rate, data, num_channels
        except Exception:
            with wave.open(wav_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)
                data = np.frombuffer(raw_bytes, dtype=np.int16)
                if n_channels > 1:
                    data = data.reshape(-1, n_channels)
                return sample_rate, data, n_channels

    def write_wav(self, wav_path: str, sample_rate: int, data: np.ndarray):
        """Записывает WAV файл."""
        try:
            from scipy.io import wavfile
            wavfile.write(wav_path, sample_rate, data)
        except Exception:
            with wave.open(wav_path, 'wb') as wf:
                n_channels = 1 if len(data.shape) == 1 else data.shape[1]
                wf.setnchannels(n_channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(data.tobytes())

    def censor_audio_numpy(
        self,
        input_wav_path: str,
        output_wav_path: str,
        profane_timestamps: List[Dict],
        censor_mode: str = "volume_ducking",
        attenuation_db: float = -24.0,
        beep_freq: int = 1000,
        padding_start: float = 0.06,
        padding_end: float = 0.06,
        fade_duration: float = 0.02
    ) -> None:
        """
        Применяет цензуру к WAV файлу через быстрое манипулирование массивом numpy.
        """
        sample_rate, data, num_channels = self.read_wav(input_wav_path)
        is_stereo = num_channels == 2
        audio_float = data.astype(np.float32)

        intervals = []
        duration = len(audio_float) / sample_rate

        for item in profane_timestamps:
            start = max(0.0, item['start'] - padding_start)
            end = min(duration, item['end'] + padding_end)
            intervals.append((start, end))

        merged_intervals = self.merge_intervals(intervals)
        duck_scale = 10.0 ** (attenuation_db / 20.0) if censor_mode == "volume_ducking" else 0.0
        fade_samples = int(fade_duration * sample_rate)

        for start_sec, end_sec in merged_intervals:
            start_idx = int(start_sec * sample_rate)
            end_idx = int(end_sec * sample_rate)

            start_idx = max(0, start_idx)
            end_idx = min(len(audio_float), end_idx)

            if start_idx >= end_idx:
                continue

            length = end_idx - start_idx

            if censor_mode in ("volume_ducking", "mute"):
                audio_float[start_idx:end_idx] *= duck_scale

                if fade_samples > 0:
                    f_start = max(0, start_idx - fade_samples)
                    f_len = start_idx - f_start
                    if f_len > 0:
                        fade_curve = np.linspace(1.0, duck_scale, f_len, dtype=np.float32)
                        if is_stereo:
                            audio_float[f_start:start_idx] *= fade_curve[:, np.newaxis]
                        else:
                            audio_float[f_start:start_idx] *= fade_curve

                    f_end = min(len(audio_float), end_idx + fade_samples)
                    f_len2 = f_end - end_idx
                    if f_len2 > 0:
                        fade_curve2 = np.linspace(duck_scale, 1.0, f_len2, dtype=np.float32)
                        if is_stereo:
                            audio_float[end_idx:f_end] *= fade_curve2[:, np.newaxis]
                        else:
                            audio_float[end_idx:f_end] *= fade_curve2

            elif censor_mode == "beep":
                t = np.linspace(0, length / sample_rate, length, endpoint=False, dtype=np.float32)
                beep_signal = (np.sin(2 * np.pi * beep_freq * t) * 16384.0).astype(np.float32)

                if is_stereo:
                    beep_signal = np.column_stack((beep_signal, beep_signal))

                audio_float[start_idx:end_idx] = beep_signal

        audio_int16 = np.clip(audio_float, -32768, 32767).astype(np.int16)
        self.write_wav(output_wav_path, sample_rate, audio_int16)

    def export_final_media(self, original_path: str, censored_wav_path: str, output_path: str) -> None:
        """
        Сохраняет итоговый файл: если вход был видео — пересобирает через Stream Copy,
        если был аудиофайлом — экспортирует в итоговый аудиоформат (.wav / .mp3 / .m4a).
        """
        if self.is_audio_file(original_path):
            # Если исходный файл аудио
            if output_path.endswith('.wav'):
                shutil.copyfile(censored_wav_path, output_path)
            else:
                cmd = [
                    self.ffmpeg_exe,
                    "-y",
                    "-i", censored_wav_path,
                    "-b:a", "192k",
                    output_path
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        else:
            # Если исходный файл видео — Stream Copy
            cmd = [
                self.ffmpeg_exe,
                "-y",
                "-i", original_path,
                "-i", censored_wav_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                raise RuntimeError(f"Ошибка FFmpeg при сборке видео: {result.stderr}")
