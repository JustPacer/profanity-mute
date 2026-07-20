import os
import sys
import logging
from typing import List, Dict, Callable, Optional, Tuple

def setup_cuda_dll_path():
    """Добавляет DLL библиотеки NVIDIA CUDA/cuDNN в путь поиска на Windows."""
    if sys.platform == "win32":
        try:
            import site
            site_dirs = site.getsitepackages()
            user_site = site.getusersitepackages()
            if isinstance(user_site, str):
                site_dirs.append(user_site)

            for sp in site_dirs:
                nvidia_dir = os.path.join(sp, "nvidia")
                if os.path.exists(nvidia_dir):
                    for sub in os.listdir(nvidia_dir):
                        for sub_folder in ("bin", "lib"):
                            target_dir = os.path.join(nvidia_dir, sub, sub_folder)
                            if os.path.exists(target_dir):
                                try:
                                    os.add_dll_directory(target_dir)
                                except Exception:
                                    pass
                                os.environ["PATH"] = target_dir + os.path.pathsep + os.environ["PATH"]
        except Exception as e:
            logging.debug(f"Ошибка регистрации CUDA DLL: {e}")

setup_cuda_dll_path()

class WhisperTranscriber:
    """
    Модуль распознавания речи с полной поддержкой NVIDIA CUDA GPU (RTX 4070 и др.).
    """

    def __init__(self, model_size: str = "medium", device: str = "auto", compute_type: str = "default"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    @staticmethod
    def get_gpu_info() -> Tuple[bool, str]:
        """Проверяет наличие GPU NVIDIA CUDA в системе."""
        setup_cuda_dll_path()

        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
                return True, f"NVIDIA CUDA: {device_name} ({vram_gb} GB VRAM)"
        except Exception:
            pass

        try:
            import ctranslate2
            if "cuda" in ctranslate2.get_supported_devices():
                return True, "NVIDIA CUDA GPU (CTranslate2)"
        except Exception:
            pass

        try:
            import subprocess
            res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                gpu_name = res.stdout.strip().split(',')[0]
                return True, f"NVIDIA CUDA: {gpu_name}"
        except Exception:
            pass

        return False, "CPU (Обработка на процессоре)"

    def load_model(self, progress_callback: Optional[Callable[[float, str], None]] = None):
        """Загрузка модели faster-whisper с GPU / CPU ускорением."""
        if self.model is not None:
            return

        setup_cuda_dll_path()
        has_gpu, gpu_desc = self.get_gpu_info()

        target_device = self.device
        if target_device == "auto":
            target_device = "cuda" if has_gpu else "cpu"
        elif target_device == "cuda" and not has_gpu:
            logging.warning("⚠️ Запрошен CUDA, но GPU не обнаружен. Переключение на CPU.")
            target_device = "cpu"

        compute_type = self.compute_type
        if compute_type == "default":
            compute_type = "float16" if target_device == "cuda" else "int8"

        if progress_callback:
            progress_callback(0.08, f"Инициализация модели Whisper ({self.model_size}) на {target_device.upper()} ({compute_type})...")

        try:
            from faster_whisper import WhisperModel

            logging.info(f"Инициализация Faster-Whisper: model={self.model_size}, device={target_device}, compute_type={compute_type}")
            self.model = WhisperModel(self.model_size, device=target_device, compute_type=compute_type)

            if progress_callback:
                progress_callback(0.12, f"Модель {self.model_size} успешно загружена на {target_device.upper()}!")

        except Exception as e:
            logging.error(f"Ошибка загрузки faster-whisper на {target_device}: {e}")
            if target_device == "cuda":
                logging.info("Попытка аварийного переключения на CPU...")
                from faster_whisper import WhisperModel
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                if progress_callback:
                    progress_callback(0.12, f"Загружена модель на CPU (Fallback).")
            else:
                raise RuntimeError(f"Не удалось загрузить модель: {e}")

    def transcribe(
        self,
        audio_path: str,
        language: str = "ru",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[Dict]:
        """
        Транскрибирует аудиофайл и возвращает сегменты со словарями слов и таймкодов.
        """
        if progress_callback:
            progress_callback(0.05, f"Подготовка весов модели {self.model_size}...")

        self.load_model(progress_callback=progress_callback)

        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")

        if progress_callback:
            progress_callback(0.15, "Запуск распознавания речи на GPU...")

        try:
            segments_generator, info = self.model.transcribe(
                audio_path,
                language=language,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
        except Exception as e:
            logging.warning(f"Ошибка транскрибации с VAD: {e}. Пробуем без VAD...")
            segments_generator, info = self.model.transcribe(
                audio_path,
                language=language,
                word_timestamps=True,
                vad_filter=False
            )

        total_duration = info.duration if info and info.duration else 1.0
        segments = []

        for segment in segments_generator:
            segments.append(segment)
            if progress_callback and total_duration > 0:
                progress = min(0.95, (segment.end / total_duration))
                cur_m, cur_s = int(segment.end // 60), int(segment.end % 60)
                tot_m, tot_s = int(total_duration // 60), int(total_duration % 60)
                progress_callback(progress, f"Расшифровка речи: {cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d}")

        if progress_callback:
            progress_callback(1.0, "Распознавание речи успешно завершено!")

        return segments
