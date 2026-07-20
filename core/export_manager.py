import os
import csv
from typing import List, Dict

class ExportManager:
    """
    Класс для экспорта таймкодов и маркеров цензуры в форматы монтажных программ:
    - DaVinci Resolve (CSV маркеры с UTF-8 BOM для корректного отображения кириллицы)
    - Текстовый список хайлайтов / эмоциональных пиков
    """

    @staticmethod
    def time_to_timecode(seconds: float, fps: float = 30.0) -> str:
        """Преобразует секунды в формат таймкода HH:MM:SS:FF."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frames = int((seconds - int(seconds)) * fps)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

    def export_davinci_csv(self, profane_words: List[Dict], output_csv_path: str):
        """
        Экспортирует маркеры для DaVinci Resolve в формате CSV с UTF-8 BOM кодировкой (utf-8-sig).
        Это предотвращает "крякозябры" (РњР°С‚) в DaVinci и Excel.
        """
        headers = ["Source In", "Source Out", "Record In", "Record Out", "Name", "Comments", "Color"]
        
        rows = []
        for i, item in enumerate(profane_words, start=1):
            start_tc = self.time_to_timecode(item['start'])
            end_tc = self.time_to_timecode(item['end'])
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

        # Используем кодировку 'utf-8-sig' (UTF-8 с BOM меткой) для корректного распознавания кириллицы
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
