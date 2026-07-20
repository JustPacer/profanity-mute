import os
import csv
import xml.etree.ElementTree as ET
from typing import List, Dict

class ExportManager:
    """
    Класс экспорта таймкодов и маркеров цензуры в форматы монтажных программ:
    - DaVinci Resolve EDL (CMX3600 EDL со стартовым смещением 01:00:00:00 под дефолтный таймлайн DaVinci)
    - DaVinci Resolve CSV (с кодировкой UTF-8 BOM)
    - Детектор хайлайтов / горячих моментов
    - Расчёт 1-минутной плотности мата для Матометра (Profanity Heatmap)
    """

    @staticmethod
    def time_to_timecode(seconds: float, fps: float = 30.0, hour_offset: int = 1) -> str:
        """Преобразует секунды в формат таймкода HH:MM:SS:FF со смещением на 1 час (01:00:00:00)."""
        hours = int(seconds // 3600) + hour_offset
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds - int(seconds)) * fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

    def export_davinci_edl(self, profane_words: List[Dict], output_edl_path: str, clip_name: str = "STREAM", start_hour_offset: int = 1):
        """
        Экспортирует маркеры для DaVinci Resolve в формате CMX3600 EDL со смещением на 01:00:00:00.
        Импорт в DaVinci: ПКМ по Таймлайну в Media Pool ➔ Timelines ➔ Import ➔ Timeline Markers from EDL...
        """
        lines = [
            "TITLE: TIMELINE MARKERS",
            "FCM: NON-DROP FRAME",
            ""
        ]

        for i, item in enumerate(profane_words, start=1):
            start_sec = item.get('full_start', item['start'])
            end_sec = item.get('full_end', item['end'])

            start_tc = self.time_to_timecode(start_sec, hour_offset=start_hour_offset)
            end_tc = self.time_to_timecode(end_sec, hour_offset=start_hour_offset)
            word_str = item.get('word', 'profanity')

            entry_num = f"{i:03d}"
            lines.append(f"{entry_num}  BL       V     C        {start_tc} {end_tc} {start_tc} {end_tc}")
            lines.append(f"* LOC: {start_tc} RED   Censored #{i} - Мат: {word_str}")
            lines.append("")

        with open(output_edl_path, 'w', encoding='utf-8-sig') as f:
            f.write("\n".join(lines))

    def export_davinci_csv(self, profane_words: List[Dict], output_csv_path: str, start_hour_offset: int = 1):
        """
        Экспортирует маркеры для DaVinci Resolve в формате CSV с UTF-8 BOM.
        """
        headers = ["Source In", "Source Out", "Record In", "Record Out", "Name", "Comments", "Color"]
        
        rows = []
        for i, item in enumerate(profane_words, start=1):
            start_tc = self.time_to_timecode(item.get('full_start', item['start']), hour_offset=start_hour_offset)
            end_tc = self.time_to_timecode(item.get('full_end', item['end']), hour_offset=start_hour_offset)
            word_str = item.get('word', 'profanity')
            
            rows.append([
                start_tc,
                end_tc,
                start_tc,
                end_tc,
                f"Censored #{i}",
                f"Мат: {word_str}",
                "Red"
            ])

        with open(output_csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

    def find_highlight_moments(self, profane_words: List[Dict], window_sec: float = 30.0, min_swears: int = 3) -> List[Dict]:
        """
        Находит эмоциональные пики/хайлайты стрима (где за короткое время сказано много мата).
        """
        if not profane_words:
            return []

        highlights = []
        n = len(profane_words)

        for i in range(n):
            current_time = profane_words[i]['start']
            count = 0
            words_in_window = []
            
            for j in range(i, n):
                if profane_words[j]['start'] - current_time <= window_sec:
                    count += 1
                    words_in_window.append(profane_words[j].get('clean_word', ''))
                else:
                    break
            
            if count >= min_swears:
                highlights.append({
                    "start_sec": current_time,
                    "end_sec": current_time + window_sec,
                    "timestamp_str": f"{int(current_time // 3600):02d}:{int((current_time % 3600) // 60):02d}:{int(current_time % 60):02d}",
                    "swear_count": count,
                    "words": words_in_window
                })

        filtered_highlights = []
        last_end = -1.0
        for h in highlights:
            if h["start_sec"] > last_end:
                filtered_highlights.append(h)
                last_end = h["end_sec"]

        filtered_highlights.sort(key=lambda x: x["swear_count"], reverse=True)
        return filtered_highlights

    @staticmethod
    def get_profanity_density(profane_words: List[Dict], total_duration_sec: float, bucket_minutes: int = 1) -> List[Dict]:
        """
        Рассчитывает плотность мата по 1-минутным интервалам для строения Матометра.
        """
        if total_duration_sec <= 0:
            total_duration_sec = 60.0

        bucket_sec = bucket_minutes * 60.0
        num_buckets = max(1, int(total_duration_sec // bucket_sec) + 1)
        buckets = [0] * num_buckets

        for item in profane_words:
            st = item.get('start', 0.0)
            idx = int(st // bucket_sec)
            if 0 <= idx < num_buckets:
                buckets[idx] += 1

        result = []
        for i, count in enumerate(buckets):
            start_m = i * bucket_minutes
            end_m = (i + 1) * bucket_minutes
            result.append({
                "minute": start_m,
                "label": f"{start_m:02d}:00 - {end_m:02d}:00",
                "count": count
            })
        return result
