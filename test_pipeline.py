# -*- coding: utf-8 -*-
import os
import numpy as np
from scipy.io import wavfile
from core.audio_processor import AudioProcessor
from core.stats_manager import StatsManager
from core.profanity_filter import ProfanityFilter

def test_full_audio_pipeline():
    processor = AudioProcessor()
    
    # 1. Создаем 3-секундный тест аудио (44100 Hz, stereo)
    sample_rate = 44100
    t = np.linspace(0, 3.0, sample_rate * 3, dtype=np.float32)
    # Синус 440 Гц
    audio_data = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
    stereo_data = np.column_stack((audio_data, audio_data))

    input_wav = "test_synthetic_in.wav"
    output_wav = "test_synthetic_out.wav"
    wavfile.write(input_wav, sample_rate, stereo_data)

    # 2. Таймкоды нецензурного слова (1.0с - 1.5с)
    profane_timestamps = [
        {"word": "пиздец", "clean_word": "пиздец", "start": 1.0, "end": 1.5}
    ]

    # 3. Применяем volume ducking
    processor.censor_audio_numpy(
        input_wav_path=input_wav,
        output_wav_path=output_wav,
        profane_timestamps=profane_timestamps,
        censor_mode="volume_ducking",
        attenuation_db=-24.0,
        padding_start=0.05,
        padding_end=0.05
    )

    assert os.path.exists(output_wav)
    print("✅ Обработка синтетического аудио пройдена успешно!")

    # Удаляем временные файлы
    for f in (input_wav, output_wav):
        if os.path.exists(f):
            os.remove(f)

if __name__ == "__main__":
    test_full_audio_pipeline()
