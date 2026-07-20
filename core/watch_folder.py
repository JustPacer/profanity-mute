import os
import time
import logging
import threading
from typing import Callable, List, Set

class WatchFolderMonitor:
    """
    Монитор авто-папки: отслеживает появление новых видео и аудиофайлов (MP4, MOV, MKV, WAV, MP3, M4A, AAC, FLAC),
    ждёт завершения записи файла и запускает авто-обработку.
    """

    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.wav', '.mp3', '.m4a', '.aac', '.flac'}

    def __init__(self, watch_dir: str, process_callback: Callable[[str], None], check_interval_sec: float = 5.0):
        self.watch_dir = watch_dir
        self.process_callback = process_callback
        self.check_interval_sec = check_interval_sec
        self.processed_files: Set[str] = set()
        self.is_running = False
        self.thread = None

    def is_file_ready(self, file_path: str) -> bool:
        """Проверяет, завершена ли запись файла."""
        if not os.path.exists(file_path):
            return False

        try:
            initial_size = os.path.getsize(file_path)
            if initial_size == 0:
                return False

            time.sleep(1.0)
            second_size = os.path.getsize(file_path)
            
            if initial_size != second_size:
                return False

            with open(file_path, 'rb') as f:
                f.read(1024)
            return True
        except (OSError, IOError):
            return False

    def scan_folder(self):
        """Сканирует папку и отправляет новые файлы на обработку."""
        if not os.path.exists(self.watch_dir):
            return

        for root, _, files in os.walk(self.watch_dir):
            for file_name in files:
                if not self.is_running:
                    return

                if "_censored" in file_name:
                    continue

                ext = os.path.splitext(file_name)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    full_path = os.path.abspath(os.path.join(root, file_name))
                    
                    if full_path not in self.processed_files:
                        if self.is_file_ready(full_path):
                            logging.info(f"📁 Монитор папки обнаружил новый файл: {full_path}")
                            self.processed_files.add(full_path)
                            try:
                                self.process_callback(full_path)
                            except Exception as e:
                                logging.error(f"Ошибка авто-обработки файла {full_path}: {e}")

    def _loop(self):
        logging.info(f"👀 Запущен мониторинг авто-папки: {self.watch_dir}")
        while self.is_running:
            try:
                self.scan_folder()
            except Exception as e:
                logging.error(f"Ошибка в цикле авто-папки: {e}")

            time.sleep(self.check_interval_sec)

    def start(self):
        """Запуск фонового мониторинга."""
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Остановка мониторинга."""
        self.is_running = False
        logging.info("⏸ Мониторинг авто-папки остановлен.")
