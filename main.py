import os
import sys
import argparse
import logging
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

from core.transcriber import WhisperTranscriber
from core.profanity_filter import ProfanityFilter
from core.audio_processor import AudioProcessor
from core.stats_manager import StatsManager
from core.export_manager import ExportManager
from core.watch_folder import WatchFolderMonitor

def process_video_cli(
    media_path: str,
    output_path: str = None,
    censor_mode: str = "volume_ducking",
    attenuation_db: float = -24.0,
    model_size: str = "medium",
    language: str = "ru",
    device: str = "auto",
    root_only: bool = True
):
    """Консольная функция цензурирования видео/аудиофайла."""
    if not os.path.exists(media_path):
        print(f"❌ Ошибка: Входной файл {media_path} не существует!")
        sys.exit(1)

    if not output_path:
        base, ext = os.path.splitext(media_path)
        output_path = f"{base}_censored{ext}"

    has_gpu, gpu_desc = WhisperTranscriber.get_gpu_info()
    print(f"=== 🎬 AutoCens Processing ===")
    print(f"📁 Входной файл: {media_path}")
    print(f"💾 Выходной файл: {output_path}")
    print(f"⚙️ Режим цензуры: {censor_mode} ({attenuation_db} dB) | Глушить только корень: {root_only}")
    print(f"🧠 Модель Whisper: {model_size} | Ускорение: {gpu_desc}")

    temp_wav = media_path + ".temp_input.wav"
    temp_out_wav = media_path + ".temp_censored.wav"
    processor = AudioProcessor()
    
    print("\n[1/5] 🎵 Извлечение/конвертация аудиодорожки (FFmpeg)...")
    duration_sec = processor.extract_audio(media_path, temp_wav)
    if duration_sec <= 0:
        duration_sec = processor.get_media_duration(media_path)

    print(f"\n[2/5] 🎤 Расшифровка речи и таймкодов (faster-whisper {model_size})...")
    transcriber = WhisperTranscriber(model_size=model_size, device=device)

    def cli_progress(*args):
        if len(args) == 2:
            prog, msg = args[0], args[1]
        else:
            prog, msg = 0.1, str(args[0])
        pct = int(float(prog) * 100)
        sys.stdout.write(f"\r progress: [{pct:3d}%] {msg}")
        sys.stdout.flush()

    segments = transcriber.transcribe(temp_wav, language=language, progress_callback=cli_progress)
    print()

    print("\n[3/5] 🔍 Поиск нецензурных выражений, расчет корней и маркеров...")
    custom_bad = []
    whitelist = []
    if os.path.exists("config.json"):
        try:
            with open("config.json", 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                custom_bad = cfg.get("custom_bad_words", [])
                whitelist = cfg.get("whitelist_words", [])
        except Exception:
            pass

    p_filter = ProfanityFilter(custom_bad_words=custom_bad, custom_whitelist=whitelist)
    profane_words = p_filter.find_profanity_in_segments(segments, root_only=root_only)

    print(f" Найдено матерных слов: {len(profane_words)}")

    # Экспорт DaVinci маркеров (.edl со смещением 01:00:00:00 и .csv)
    export_mgr = ExportManager()
    base_no_ext = os.path.splitext(output_path)[0]
    edl_path = f"{base_no_ext}_davinci_markers.edl"
    csv_path = f"{base_no_ext}_davinci_markers.csv"
    
    export_mgr.export_davinci_edl(profane_words, edl_path, clip_name=os.path.basename(media_path), start_hour_offset=1)
    export_mgr.export_davinci_csv(profane_words, csv_path, start_hour_offset=1)
    print(f"📌 Маркеры для DaVinci (.edl и .csv) сохранены рядом с видео!")

    highlights = export_mgr.find_highlight_moments(profane_words)
    if highlights:
        print("\n🔥 ТОП ЭМОЦИОНАЛЬНЫХ ПИКОВ СТРИМА (для TikTok / Shorts):")
        for idx, h in enumerate(highlights[:5], 1):
            print(f"   {idx}. ⏰ [{h['timestamp_str']}] — {h['swear_count']} матов в секунду!")

    print(f"\n[4/5] 🔊 Обработка аудиодорожки (Режим: {censor_mode})...")
    processor.censor_audio_numpy(
        input_wav_path=temp_wav,
        output_wav_path=temp_out_wav,
        profane_timestamps=profane_words,
        censor_mode=censor_mode,
        attenuation_db=attenuation_db
    )

    print("\n[5/5] 🚀 Экспорт итогового медиафайла...")
    processor.export_final_media(media_path, temp_out_wav, output_path)

    for tmp in (temp_wav, temp_out_wav):
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

    stats_mgr = StatsManager()
    stats_mgr.add_processing_session(
        video_name=media_path,
        video_duration_sec=duration_sec,
        profane_words_detected=profane_words,
        censor_mode=censor_mode
    )

    summary = stats_mgr.get_summary()
    print("\n==========================================")
    print(f"✅ Готово! Файл сохранен: {output_path}")
    print(f"📊 Всего матов запикано за всё время: {summary['total_profanities']}")
    print(f"⏱ Суммарная длительность: {summary['total_hours']} ч")
    print("==========================================")

def print_stats_cli():
    """Выводит накапливаемую статистику в консоль."""
    stats_mgr = StatsManager()
    summary = stats_mgr.get_summary()

    print("==========================================")
    print("📊 НАКОПИТЕЛЬНАЯ СТАТИСТИКА МАТА (AutoCens)")
    print("==========================================")
    print(f"▶️ Обработано файлов: {summary['total_videos']}")
    print(f"🤬 Запикано матов за всё время: {summary['total_profanities']}")
    print(f"⏱ Суммарная длительность: {summary['total_hours']} часов")
    print(f"🔤 Уникальных матерных слов: {summary['unique_words_count']}")
    print("\n🔥 ТОП-15 матерных слов:")
    
    total = max(1, summary['total_profanities'])
    for word, count in summary['top_words'][:15]:
        pct = (count / total) * 100.0
        print(f"  • {word:<15} : {count:4d} раз ({pct:.1f}%)")
    print("==========================================")

def run_watch_cli(watch_folder: str, device: str, model_size: str, censor_mode: str):
    """Запуск монитора авто-папки из консоли."""
    print(f"👀 Запуск монитора авто-папки: {watch_folder}")
    print("Нажмите Ctrl+C для выхода.")
    
    def on_new_media(file_path):
        base, ext = os.path.splitext(file_path)
        out = f"{base}_censored{ext}"
        process_video_cli(
            media_path=file_path,
            output_path=out,
            censor_mode=censor_mode,
            model_size=model_size,
            device=device
        )

    monitor = WatchFolderMonitor(watch_folder, on_new_media)
    monitor.start()
    try:
        import time
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        monitor.stop()
        print("\nМониторинг остановлен.")

def main():
    parser = argparse.ArgumentParser(
        description="AutoCens — Автоматическое запикивание/приглушение мата в видео и аудиофайлах."
    )
    parser.add_argument("media", nargs="?", help="Путь к видео или аудиофайлу (.mp4, .mov, .mkv, .wav, .mp3, .m4a)")
    parser.add_argument("-o", "--output", help="Путь к выходному файлу")
    parser.add_argument("-m", "--mode", choices=["volume_ducking", "mute", "beep"], default="volume_ducking", help="Режим цензуры")
    parser.add_argument("--db", type=float, default=-24.0, help="Уровень приглушения в dB")
    parser.add_argument("--model", default="medium", choices=["tiny", "base", "small", "medium", "large-v3"], help="Модель Whisper")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"], help="Устройство (cuda или cpu)")
    parser.add_argument("--no-root-only", action="store_true", help="Глушить слово целиком вместо только корня")
    parser.add_argument("--watch-dir", help="Запустить фоновый мониторинг заданной папки")
    parser.add_argument("--gui", action="store_true", help="Запустить графический интерфейс (GUI)")
    parser.add_argument("--stats", action="store_true", help="Показать глобальную накопительную статистику")

    args = parser.parse_args()

    if args.stats:
        print_stats_cli()
        return

    if args.watch_dir:
        run_watch_cli(args.watch_dir, device=args.device, model_size=args.model, censor_mode=args.mode)
        return

    if args.gui or len(sys.argv) == 1 or not args.media:
        try:
            from gui.app import launch_gui
            launch_gui()
        except ImportError as e:
            print(f"Ошибка запуска GUI: {e}")
            print("Запуск с файлом через CLI: python main.py my_video.mp4")
        return

    process_video_cli(
        media_path=args.media,
        output_path=args.output,
        censor_mode=args.mode,
        attenuation_db=args.db,
        model_size=args.model,
        device=args.device,
        root_only=not args.no_root_only
    )

if __name__ == "__main__":
    main()
