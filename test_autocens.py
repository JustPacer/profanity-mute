# -*- coding: utf-8 -*-
import os
import sys
import json
from core.profanity_filter import ProfanityFilter
from core.stats_manager import StatsManager

def test_profanity_filter():
    pf = ProfanityFilter()

    # Сварливые/Матерные слова (Должны быть True)
    assert pf.is_profane("пиздец") == True, "пиздец should be profane"
    assert pf.is_profane("нахуй") == True, "нахуй should be profane"
    assert pf.is_profane("блять") == True, "блять should be profane"
    assert pf.is_profane("сука") == True, "сука should be profane"
    assert pf.is_profane("заебал") == True, "заебал should be profane"
    assert pf.is_profane("долбоеб") == True, "долбоеб should be profane"
    assert pf.is_profane("пидор") == True, "пидор should be profane"
    assert pf.is_profane("fuck") == True, "fuck should be profane"

    # Обычные/Очищенные слова (Должны быть False)
    assert pf.is_profane("хлеб") == False, "хлеб should NOT be profane"
    assert pf.is_profane("страховка") == False, "страховка should NOT be profane"
    assert pf.is_profane("оскорблять") == False, "оскорблять should NOT be profane"
    assert pf.is_profane("педаль") == False, "педаль should NOT be profane"
    assert pf.is_profane("привет") == False, "привет should NOT be profane"

    print("✅ Тесты фильтра мата успешно пройдены!")

def test_stats_manager(tmp_path):
    test_json = os.path.join(tmp_path, "test_stats.json")
    sm = StatsManager(stats_file_path=test_json)

    # Добавляем 1 сессию
    sm.add_processing_session(
        video_name="stream_part1.mp4",
        video_duration_sec=7200.0, # 2 часа
        profane_words_detected=[
            {"clean_word": "пиздец", "word": "пиздец"},
            {"clean_word": "пиздец", "word": "пиздец"},
            {"clean_word": "нахуй", "word": "нахуй"},
        ],
        censor_mode="volume_ducking"
    )

    summary1 = sm.get_summary()
    assert summary1["total_videos"] == 1
    assert summary1["total_profanities"] == 3
    assert summary1["top_words"][0] == ("пиздец", 2)
    assert summary1["top_words"][1] == ("нахуй", 1)

    # Добавляем 2 сессию (плюсуется!)
    sm.add_processing_session(
        video_name="stream_part2.mp4",
        video_duration_sec=3600.0, # 1 час
        profane_words_detected=[
            {"clean_word": "блять", "word": "блять"},
            {"clean_word": "нахуй", "word": "нахуй"},
        ],
        censor_mode="volume_ducking"
    )

    summary2 = sm.get_summary()
    assert summary2["total_videos"] == 2
    assert summary2["total_profanities"] == 5 # 3 + 2 = 5!
    assert summary2["top_words"][0] == ("пиздец", 2)
    assert summary2["top_words"][1] == ("нахуй", 2)

    print("✅ Тесты накопительной статистики успешно пройдены!")

if __name__ == "__main__":
    test_profanity_filter()
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        test_stats_manager(tmpdir)
    print("\n🎉 Все модульные тесты AutoCens пройдены!")
