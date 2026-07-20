import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple

class StatsManager:
    """
    Класс управления накопительной статистикой мата и логами вызовов.
    Сохраняет статистику в JSON файл между запусками приложения.
    """

    def __init__(self, stats_file_path: str = "data/stats.json"):
        self.stats_file_path = stats_file_path
        self.ensure_dir()
        self.stats = self.load_stats()

    def ensure_dir(self):
        """Создает директорию для хранения данных, если её нет."""
        dirname = os.path.dirname(self.stats_file_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

    def load_stats(self) -> Dict[str, Any]:
        """Загружает глобальную статистику из JSON-файла."""
        if not os.path.exists(self.stats_file_path):
            default_stats = {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_videos_processed": 0,
                "total_profanities_censored": 0,
                "total_video_duration_seconds": 0.0,
                "word_counts": {},
                "history": []
            }
            self.save_stats(default_stats)
            return default_stats

        try:
            with open(self.stats_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка чтения файла статистики {self.stats_file_path}: {e}")
            return {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_videos_processed": 0,
                "total_profanities_censored": 0,
                "total_video_duration_seconds": 0.0,
                "word_counts": {},
                "history": []
            }

    def save_stats(self, data: Dict[str, Any] = None):
        """Сохраняет текущее состояние статистики на диск."""
        if data is None:
            data = self.stats
        
        data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.stats_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f" Ошибка записи статистики в {self.stats_file_path}: {e}")

    def add_processing_session(
        self,
        video_name: str,
        video_duration_sec: float,
        profane_words_detected: List[Dict],
        censor_mode: str
    ) -> Dict[str, Any]:
        """
        Обновляет глобальную накопительную статистику после обработки видео.
        """
        session_word_counts = {}
        for item in profane_words_detected:
            word = item.get('clean_word', item.get('word', '')).lower()
            if not word:
                continue
            session_word_counts[word] = session_word_counts.get(word, 0) + 1
            self.stats["word_counts"][word] = self.stats["word_counts"].get(word, 0) + 1

        total_censored_in_session = len(profane_words_detected)
        self.stats["total_videos_processed"] += 1
        self.stats["total_profanities_censored"] += total_censored_in_session
        self.stats["total_video_duration_seconds"] += video_duration_sec

        session_record = {
            "timestamp": datetime.now().isoformat(),
            "video_name": os.path.basename(video_name),
            "duration_sec": video_duration_sec,
            "censored_count": total_censored_in_session,
            "censor_mode": censor_mode,
            "session_words": session_word_counts
        }

        self.stats["history"].append(session_record)
        self.save_stats()
        return session_record

    def get_summary(self) -> Dict[str, Any]:
        """Возвращает сводные данные статистики."""
        total_hours = self.stats.get("total_video_duration_seconds", 0.0) / 3600.0
        
        # Сортировка слов по частоте
        word_counts = self.stats.get("word_counts", {})
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_videos": self.stats.get("total_videos_processed", 0),
            "total_profanities": self.stats.get("total_profanities_censored", 0),
            "total_hours": round(total_hours, 2),
            "top_words": top_words,
            "unique_words_count": len(word_counts),
            "history": self.stats.get("history", [])
        }
