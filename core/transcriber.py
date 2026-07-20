import os
import sys
import logging
from typing import List, Dict, Tuple, Optional, Callable

class WhisperTranscriber:
    """
    Класс-обертка для быстрого распознавания речи с использованием библиотеки faster-whisper.
    Поддерживает конвертированную CTranslate2 версию лучшей русской модели: bzikst/faster-whisper-large-v3-russian.
    """

    MODEL_ALIASES = {
        "antony66/whisper-large-v3-russian": "bzikst/faster-whisper-large-v3-russian",
        "ru-large": "bzikst/faster-whisper-large-v3-russian",
        "russian": "bzikst/faster-whisper-large-v3-russian",
    }

    def __init__(
        self,
        model_size: str = "bzikst/faster-whisper-large-v3-russian",
        device: str = "auto",
        compute_type: str = "default",
        download_root: Optional[str] = None
    ):
        self.raw_model_name = model_size
        self.model_size_or_path = self.MODEL_ALIASES.get(model_size, model_size)
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root

        self.setup_cuda_dll_path()
        self.model = None

    @staticmethod
    def setup_cuda_dll_path():
        """Автоматическая настройка путей к DLL динамических библиотек NVIDIA CUDA под Windows."""
        if sys.platform == "win32":
            import site
            site_packages = site.getsitepackages()
            nvidia_paths = []

            for sp in site_packages:
                nv_dir = os.path.join(sp, "nvidia")
                if os.path.exists(nv_dir):
                    for sub in os.listdir(nv_dir):
                        for sub_dir in ["bin", "lib"]:
                            target_dir = os.path.join(nv_dir, sub, sub_dir)
                            if os.path.exists(target_dir):
                                nvidia_paths.append(target_dir)

            for path in nvidia_paths:
                if path not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = path + os.path.pathsep + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(path)
                    except Exception:
                        pass

    @staticmethod
    def get_gpu_info() -> Tuple[bool, str]:
        """Проверяет наличие GPU от NVIDIA и доступность системы CUDA."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                return True, f"NVIDIA CUDA ({gpu_name})"
        except Exception:
            pass

        if sys.platform == "win32":
            try:
                import ctype_util
            except ImportError:
                pass
            
            for dll in ["cublas64_12.dll", "cublas64_11.dll"]:
                try:
                    import ctypes
                    ctypes.CDLL(dll)
                    return True, "NVIDIA CUDA (Обнаружен через DLL)"
                except Exception:
                    pass

        return False, "CPU (Процессор)"

    def load_model(self):
        """Загружает модель faster-whisper с выбором безопасных путей и авто-фолбеком."""
        if self.model is not None:
            return

        from faster_whisper import WhisperModel

        target_device = self.device
        if target_device == "auto":
            has_gpu, _ = self.get_gpu_info()
            target_device = "cuda" if has_gpu else "cpu"

        target_compute = self.compute_type
        if target_compute == "default":
            target_compute = "float16" if target_device == "cuda" else "int8"

        logging.info(f"Загрузка модели Whisper '{self.model_size_or_path}' на устройстве '{target_device}' ({target_compute})...")

        try:
            self.model = WhisperModel(
                self.model_size_or_path,
                device=target_device,
                compute_type=target_compute,
                download_root=self.download_root
            )
            logging.info("Модель Whisper успешно загружена!")
        except Exception as e:
            logging.warning(f"Ошибка загрузки модели {self.model_size_or_path}: {e}")
            if self.model_size_or_path != "medium":
                logging.info("Переключение на стандартную модель 'medium'...")
                self.model_size_or_path = "medium"
                try:
                    self.model = WhisperModel(
                        "medium",
                        device=target_device,
                        compute_type=target_compute,
                        download_root=self.download_root
                    )
                    return
                except Exception:
                    pass

            if target_device == "cuda":
                logging.warning("Ошибка на CUDA. Авто-переключение на CPU (int8)...")
                self.model = WhisperModel(
                    "medium",
                    device="cpu",
                    compute_type="int8",
                    download_root=self.download_root
                )

    def transcribe(
        self,
        audio_path: str,
        language: str = "ru",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> List[Dict]:
        """
        Транскрибирует аудиофайл и возвращает сегменты с пословными таймкодами.
        """
        self.load_model()

        logging.info(f"Начало распознавания речи для {audio_path}...")
        
        segments_gen, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        total_duration = info.duration if info and info.duration else 1.0
        result_segments = []

        for segment in segments_gen:
            result_segments.append(segment)
            if progress_callback and total_duration > 0:
                progress = min(1.0, segment.end / total_duration)
                progress_callback(progress, f"Распознавание: {int(progress * 100)}% ({segment.text[:30]}...)")

        if progress_callback:
            progress_callback(1.0, "Распознавание завершено!")

        return result_segments
