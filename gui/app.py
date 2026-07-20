import os
import sys
import json
import logging
from typing import Optional, List, Dict

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox,
        QProgressBar, QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
        QHeaderView, QGroupBox, QSlider, QMessageBox, QCheckBox, QLineEdit,
        QFrame, QSplitter
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF
    from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False

from core.transcriber import WhisperTranscriber
from core.profanity_filter import ProfanityFilter
from core.audio_processor import AudioProcessor
from core.stats_manager import StatsManager
from core.export_manager import ExportManager
from core.watch_folder import WatchFolderMonitor


if HAS_PYQT6:
    class ProfanityHeatmapWidget(QWidget):
        """Виджет Матометра (гистограмма плотности мата по минутам)."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.density_data: List[Dict] = []
            self.setMinimumHeight(160)
            self.setToolTip("Матометр — плотность мата по минутам видео")

        def set_data(self, density_data: List[Dict]):
            self.density_data = density_data
            self.update()

        def paintEvent(self, event):
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                w = self.width()
                h = self.height()

                painter.fillRect(0, 0, w, h, QColor("#181824"))

                if not self.density_data:
                    painter.setPen(QColor("#888899"))
                    painter.setFont(QFont("Arial", 11))
                    painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "📊 Нет данных плотности мата (обработайте медиафайл)")
                    return

                max_val = max((d["count"] for d in self.density_data), default=1)
                max_val = max(1, max_val)

                num_bars = len(self.density_data)
                padding_left = 40
                padding_right = 20
                padding_top = 25
                padding_bottom = 30

                graph_w = w - padding_left - padding_right
                graph_h = h - padding_top - padding_bottom

                bar_w = max(2.0, (graph_w / num_bars) - 2.0)

                # Отрисовка сетки с явным приведением к int
                painter.setPen(QPen(QColor("#2d2d3f"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(padding_left), int(padding_top), int(w - padding_right), int(padding_top))
                painter.drawLine(int(padding_left), int(padding_top + graph_h / 2), int(w - padding_right), int(padding_top + graph_h / 2))
                painter.drawLine(int(padding_left), int(padding_top + graph_h), int(w - padding_right), int(padding_top + graph_h))

                # Подпись оси Y
                painter.setPen(QColor("#00ffcc"))
                painter.setFont(QFont("Arial", 9))
                painter.drawText(5, int(padding_top + 10), f"{max_val} матов")
                painter.drawText(10, int(padding_top + graph_h), "0")

                # Отрисовка столбцов гистограммы
                for i, item in enumerate(self.density_data):
                    cnt = item["count"]
                    bar_h = (cnt / max_val) * graph_h if max_val > 0 else 0

                    x = padding_left + i * (bar_w + 2.0)
                    y = padding_top + (graph_h - bar_h)

                    if cnt > 0:
                        intensity = min(1.0, cnt / max(3, max_val))
                        r_val = int(255)
                        g_val = int(255 * (1.0 - intensity * 0.8))
                        b_val = int(50 * (1.0 - intensity))
                        color = QColor(r_val, g_val, b_val)
                    else:
                        color = QColor("#2a2a3c")

                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 2, 2)

                # Подпись оси X (Время)
                painter.setPen(QColor("#aaaa88"))
                if num_bars > 0:
                    first_label = self.density_data[0]["label"].split(" - ")[0]
                    last_label = self.density_data[-1]["label"].split(" - ")[-1]
                    painter.drawText(int(padding_left), int(h - 8), first_label)
                    painter.drawText(int(w - padding_right - 50), int(h - 8), last_label)
            finally:
                painter.end()


class ProcessingThread(QThread if HAS_PYQT6 else object):
    """Фоновый поток обработки видео/аудио для GUI."""
    if HAS_PYQT6:
        progress_signal = pyqtSignal(float, str)
        finished_signal = pyqtSignal(bool, str, dict)
        log_signal = pyqtSignal(str)

    def __init__(self, media_path: str, output_path: str, config: dict):
        if HAS_PYQT6:
            super().__init__()
        self.media_path = media_path
        self.output_path = output_path
        self.config = config

    def run(self):
        try:
            self.emit_log(f"🎬 Начало обработки: {os.path.basename(self.media_path)}")
            
            processor = AudioProcessor()
            temp_wav = self.media_path + ".temp_input.wav"
            temp_out_wav = self.media_path + ".temp_censored.wav"
            
            self.emit_progress(0.05, "Извлечение/конвертация аудиодорожки...")
            duration_sec = processor.extract_audio(self.media_path, temp_wav)
            if duration_sec <= 0:
                duration_sec = processor.get_media_duration(self.media_path)

            self.emit_log(f"⏱ Длительность: {int(duration_sec // 3600):02d}:{int((duration_sec % 3600) // 60):02d}:{int(duration_sec % 60):02d}")

            self.emit_progress(0.10, "Загрузка модели Whisper и транскрибация...")
            transcriber = WhisperTranscriber(
                model_size=self.config.get("model_size", "antony66/whisper-large-v3-russian"),
                device=self.config.get("device", "auto"),
                compute_type=self.config.get("compute_type", "default")
            )
            
            def on_transcribe_progress(*args):
                if len(args) == 2:
                    prog, text = args[0], args[1]
                elif len(args) == 1:
                    if isinstance(args[0], (int, float)):
                        prog, text = args[0], "Распознавание речи..."
                    else:
                        prog, text = 0.10, str(args[0])
                else:
                    prog, text = 0.10, "Обработка..."

                scaled_prog = 0.10 + (float(prog) * 0.60)
                self.emit_progress(scaled_prog, str(text))

            segments = transcriber.transcribe(
                temp_wav,
                language=self.config.get("language", "ru"),
                progress_callback=on_transcribe_progress
            )

            self.emit_progress(0.75, "Анализ матерных слов и поиск корней...")
            p_filter = ProfanityFilter(
                custom_bad_words=self.config.get("custom_bad_words", []),
                custom_whitelist=self.config.get("whitelist_words", [])
            )
            
            root_only = self.config.get("root_only_muting", True)
            profane_words = p_filter.find_profanity_in_segments(segments, root_only=root_only)
            self.emit_log(f" Найдено нецензурных слов: {len(profane_words)}")

            export_mgr = ExportManager()
            density_data = export_mgr.get_profanity_density(profane_words, duration_sec)
            highlights = export_mgr.find_highlight_moments(profane_words)
            if highlights:
                self.emit_log("\n🔥 ТОП ЭМОЦИОНАЛЬНЫХ ПИКОВ СТРИМА (для YouTube Shorts / TikTok):")
                for idx, h in enumerate(highlights[:5], 1):
                    self.emit_log(f"   {idx}. ⏰ [{h['timestamp_str']}] — {h['swear_count']} матов за 30с")

            # Экспорт маркеров EDL (с 01h смещением) и CSV для DaVinci Resolve
            if self.config.get("export_davinci_markers", True):
                base_no_ext = os.path.splitext(self.output_path)[0]
                edl_path = f"{base_no_ext}_davinci_markers.edl"
                csv_path = f"{base_no_ext}_davinci_markers.csv"
                
                export_mgr.export_davinci_edl(profane_words, edl_path, clip_name=os.path.basename(self.media_path), start_hour_offset=1)
                export_mgr.export_davinci_csv(profane_words, csv_path, start_hour_offset=1)
                self.emit_log(f"📌 Маркеры DaVinci (.edl и .csv) сохранены: {os.path.basename(edl_path)}")

            self.emit_progress(0.85, "Применение глушения/запикивания на аудио...")
            processor.censor_audio_numpy(
                input_wav_path=temp_wav,
                output_wav_path=temp_out_wav,
                profane_timestamps=profane_words,
                censor_mode=self.config.get("censor_mode", "volume_ducking"),
                attenuation_db=self.config.get("attenuation_db", -24.0),
                beep_freq=self.config.get("beep_frequency", 1000),
                padding_start=self.config.get("padding_start_sec", 0.04),
                padding_end=self.config.get("padding_end_sec", 0.04),
                fade_duration=self.config.get("fade_duration_sec", 0.02)
            )

            self.emit_progress(0.92, "Экспорт итогового файла...")
            processor.export_final_media(self.media_path, temp_out_wav, self.output_path)

            for tmp in (temp_wav, temp_out_wav):
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

            stats_mgr = StatsManager()
            session_data = stats_mgr.add_processing_session(
                video_name=self.media_path,
                video_duration_sec=duration_sec,
                profane_words_detected=profane_words,
                censor_mode=self.config.get("censor_mode", "volume_ducking")
            )

            raw_segments_data = []
            for seg in segments:
                s_start = getattr(seg, 'start', 0.0) if hasattr(seg, 'start') else (seg.get('start', 0.0) if isinstance(seg, dict) else 0.0)
                s_end = getattr(seg, 'end', 0.0) if hasattr(seg, 'end') else (seg.get('end', 0.0) if isinstance(seg, dict) else 0.0)
                s_text = getattr(seg, 'text', '') if hasattr(seg, 'text') else (seg.get('text', '') if isinstance(seg, dict) else '')
                raw_segments_data.append({
                    "start": s_start,
                    "end": s_end,
                    "text": s_text
                })

            result_meta = {
                "session": session_data,
                "profane_words": profane_words,
                "density_data": density_data,
                "segments": raw_segments_data,
                "duration_sec": duration_sec
            }

            self.emit_progress(1.0, " Обработка успешно завершена!")
            self.emit_finished(True, f"Файл сохранен: {self.output_path}", result_meta)

        except Exception as e:
            logging.exception("Ошибка в фоновом потоке:")
            self.emit_finished(False, str(e), {})

    def emit_progress(self, val: float, text: str):
        if HAS_PYQT6:
            self.progress_signal.emit(val, text)

    def emit_log(self, text: str):
        if HAS_PYQT6:
            self.log_signal.emit(text)

    def emit_finished(self, success: bool, msg: str, data: dict):
        if HAS_PYQT6:
            self.finished_signal.emit(success, msg, data)


if HAS_PYQT6:
    class AutoCensGUI(QMainWindow):
        """Главное окно приложения AutoCens."""

        def __init__(self, config_path: str = "config.json"):
            super().__init__()
            self.config_path = config_path
            self.config = self.load_config()
            self.stats_mgr = StatsManager()
            self.watch_monitor = None
            self.current_segments: List[Dict] = []
            self.current_profane_words: List[Dict] = []
            
            self.setWindowTitle("AutoCens — Автоматическое запикивание мата (Видео и Аудио)")
            self.resize(1000, 750)
            self.setup_ui()
            self.apply_dark_theme()
            self.refresh_stats_view()

        def load_config(self) -> dict:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass
            return {
                "model_size": "antony66/whisper-large-v3-russian",
                "device": "auto",
                "censor_mode": "volume_ducking",
                "attenuation_db": -24.0,
                "beep_frequency": 1000,
                "padding_start_sec": 0.04,
                "padding_end_sec": 0.04,
                "root_only_muting": True,
                "export_davinci_markers": True,
                "watch_folder": "",
                "watch_folder_enabled": False,
                "custom_bad_words": [],
                "whitelist_words": []
            }

        def save_config(self):
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logging.error(f"Не удалось сохранить конфигурацию: {e}")

        def setup_ui(self):
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)

            main_layout = QVBoxLayout(central_widget)

            self.tabs = QTabWidget()
            main_layout.addWidget(self.tabs)

            self.tab_process = QWidget()
            self.setup_process_tab()
            self.tabs.addTab(self.tab_process, "🎬 Обработка видео / аудио")

            self.tab_transcript = QWidget()
            self.setup_transcript_tab()
            self.tabs.addTab(self.tab_transcript, "📝 Инспектор расшифровки речи")

            self.tab_watch = QWidget()
            self.setup_watch_tab()
            self.tabs.addTab(self.tab_watch, "📁 Авто-папка (Watch Folder)")

            self.tab_stats = QWidget()
            self.setup_stats_tab()
            self.tabs.addTab(self.tab_stats, "📊 Глобальная статистика мата")

            self.tab_settings = QWidget()
            self.setup_settings_tab()
            self.tabs.addTab(self.tab_settings, "⚙️ Настройки и GPU")

        def setup_process_tab(self):
            layout = QVBoxLayout(self.tab_process)

            file_box = QGroupBox("Выбор медиафайла (MP4, MOV, MKV, WAV, MP3, M4A, AAC, FLAC)")
            file_layout = QHBoxLayout(file_box)
            
            self.input_file_edit = QTextEdit()
            self.input_file_edit.setMaximumHeight(35)
            self.input_file_edit.setPlaceholderText("Выберите или перетащите видео или аудиофайл...")
            
            btn_browse = QPushButton("📁 Обзор...")
            btn_browse.setHeight = 35
            btn_browse.clicked.connect(self.browse_file)

            file_layout.addWidget(self.input_file_edit)
            file_layout.addWidget(btn_browse)
            layout.addWidget(file_box)

            params_box = QGroupBox("Параметры цензуры и Ускорения")
            params_layout = QHBoxLayout(params_box)

            lbl_mode = QLabel("Режим:")
            self.combo_mode = QComboBox()
            self.combo_mode.addItems([
                "Приглушение (Volume Ducking -24dB)",
                "Полное заглушение (Mute)",
                "Запикивание (Beep 1000Hz)"
            ])
            current_m = self.config.get("censor_mode", "volume_ducking")
            if current_m == "mute":
                self.combo_mode.setCurrentIndex(1)
            elif current_m == "beep":
                self.combo_mode.setCurrentIndex(2)

            lbl_model = QLabel("Модель Whisper:")
            self.combo_model = QComboBox()
            self.combo_model.addItems([
                "antony66/whisper-large-v3-russian (🇷🇺 Топ для русской речи)",
                "medium (рекомендуется баланс)",
                "large-v3 (оригинал OpenAI)",
                "small (быстро)",
                "base (очень быстро)"
            ])
            m_size = self.config.get("model_size", "antony66/whisper-large-v3-russian")
            if "antony66" in m_size or "ru" in m_size:
                self.combo_model.setCurrentIndex(0)
            elif "medium" in m_size:
                self.combo_model.setCurrentIndex(1)
            elif "large" in m_size:
                self.combo_model.setCurrentIndex(2)
            elif "small" in m_size:
                self.combo_model.setCurrentIndex(3)
            elif "base" in m_size:
                self.combo_model.setCurrentIndex(4)

            lbl_device = QLabel("Ускорение:")
            self.combo_device = QComboBox()
            self.combo_device.addItems(["Auto (Автовыбор GPU/CPU)", "NVIDIA CUDA (GPU)", "CPU (Процессор)"])
            cur_dev = self.config.get("device", "auto")
            if cur_dev == "cuda":
                self.combo_device.setCurrentIndex(1)
            elif cur_dev == "cpu":
                self.combo_device.setCurrentIndex(2)

            params_layout.addWidget(lbl_mode)
            params_layout.addWidget(self.combo_mode)
            params_layout.addWidget(lbl_model)
            params_layout.addWidget(self.combo_model)
            params_layout.addWidget(lbl_device)
            params_layout.addWidget(self.combo_device)
            layout.addWidget(params_box)

            options_box = QHBoxLayout()
            self.chk_root_only = QCheckBox("✂️ Глушить только корень слова (приставки 'за-', 'по-' остаются слышимыми)")
            self.chk_root_only.setChecked(self.config.get("root_only_muting", True))

            self.chk_davinci = QCheckBox("📌 Генерировать маркеры для DaVinci Resolve (.EDL, .CSV)")
            self.chk_davinci.setChecked(self.config.get("export_davinci_markers", True))

            options_box.addWidget(self.chk_root_only)
            options_box.addWidget(self.chk_davinci)
            layout.addLayout(options_box)

            # Матометр (Profanity Heatmap)
            heatmap_box = QGroupBox("📊 Матометр (График плотности мата по минутам)")
            heatmap_layout = QVBoxLayout(heatmap_box)
            self.heatmap_widget = ProfanityHeatmapWidget()
            heatmap_layout.addWidget(self.heatmap_widget)
            layout.addWidget(heatmap_box)

            has_gpu, gpu_desc = WhisperTranscriber.get_gpu_info()
            self.lbl_gpu_status = QLabel(f"⚡ Ускорение: {gpu_desc}")
            self.lbl_gpu_status.setStyleSheet("color: #00ffcc; font-weight: bold; padding: 2px;")
            layout.addWidget(self.lbl_gpu_status)

            self.btn_start = QPushButton("🚀 Запустить автоматическую цензуру")
            self.btn_start.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #0d6efd; color: white; padding: 10px; border-radius: 5px;")
            self.btn_start.clicked.connect(self.start_processing)
            layout.addWidget(self.btn_start)

            self.lbl_status = QLabel("Готов к работе")
            self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.lbl_status)

            self.progress_bar = QProgressBar()
            self.progress_bar.setValue(0)
            layout.addWidget(self.progress_bar)

            self.log_text = QTextEdit()
            self.log_text.setMaximumHeight(100)
            self.log_text.setReadOnly(True)
            layout.addWidget(self.log_text)

        def setup_transcript_tab(self):
            layout = QVBoxLayout(self.tab_transcript)

            top_box = QGroupBox("🔍 Поиск и проверка точности распознанных слов")
            top_layout = QHBoxLayout(top_box)

            self.txt_search_word = QLineEdit()
            self.txt_search_word.setPlaceholderText("Введите слово для поиска (например: 'сухую', 'сука', 'блять')...")
            self.txt_search_word.textChanged.connect(self.filter_transcript_view)

            self.lbl_search_count = QLabel("Найдено: 0 совпадений")
            self.lbl_search_count.setStyleSheet("font-weight: bold; color: #00ffcc; margin-left: 10px;")

            top_layout.addWidget(self.txt_search_word)
            top_layout.addWidget(self.lbl_search_count)
            layout.addWidget(top_box)

            self.transcript_display = QTextEdit()
            self.transcript_display.setReadOnly(True)
            self.transcript_display.setStyleSheet("background-color: #1a1a24; color: #e0e0e0; font-family: Consolas, monospace; font-size: 13px;")
            layout.addWidget(self.transcript_display)

        def render_transcript_html(self, filter_query: str = ""):
            if not self.current_segments:
                self.transcript_display.setHtml("<p style='color: #888899; text-align: center;'>Транскрибация отсутствует. Запустите обработку медиафайла.</p>")
                self.lbl_search_count.setText("Найдено: 0 совпадений")
                return

            p_filter = ProfanityFilter(
                custom_bad_words=self.config.get("custom_bad_words", []),
                custom_whitelist=self.config.get("whitelist_words", [])
            )

            filter_query = filter_query.strip().lower()
            html_lines = []
            match_count = 0

            for seg in self.current_segments:
                st = seg.get("start", 0.0) if isinstance(seg, dict) else (getattr(seg, 'start', 0.0) if hasattr(seg, 'start') else 0.0)
                tc_str = f"[{int(st // 3600):02d}:{int((st % 3600) // 60):02d}:{int(st % 60):02d}]"
                text = seg.get("text", "").strip() if isinstance(seg, dict) else (getattr(seg, 'text', '').strip() if hasattr(seg, 'text') else '')

                if not text:
                    continue

                if filter_query and filter_query not in text.lower():
                    continue

                if filter_query:
                    match_count += text.lower().count(filter_query)

                words = text.split()
                formatted_words = []
                for w in words:
                    clean_w = p_filter.clean_word(w)
                    is_bad = p_filter.is_profane(clean_w)
                    
                    if filter_query and filter_query in clean_w:
                        formatted_words.append(f"<span style='background-color: #ffaa00; color: black; font-weight: bold; padding: 2px 4px; border-radius: 3px;'>{w}</span>")
                    elif is_bad:
                        formatted_words.append(f"<span style='background-color: #990022; color: #ff99aa; font-weight: bold; padding: 2px 4px; border-radius: 3px;'>{w}</span>")
                    else:
                        formatted_words.append(w)

                line_html = f"<div style='margin-bottom: 6px;'><span style='color: #00ffcc; font-weight: bold;'>{tc_str}</span> {' '.join(formatted_words)}</div>"
                html_lines.append(line_html)

            self.transcript_display.setHtml("".join(html_lines))
            if filter_query:
                self.lbl_search_count.setText(f"Найдено: {match_count} совпадений")
            else:
                self.lbl_search_count.setText(f"Всего строк: {len(html_lines)}")

        def filter_transcript_view(self, text: str):
            self.render_transcript_html(text)

        def setup_watch_tab(self):
            layout = QVBoxLayout(self.tab_watch)

            grp_watch = QGroupBox("Автоматический мониторинг папки записи (OBS / Twitch)")
            vbox = QVBoxLayout(grp_watch)

            lbl_info = QLabel("Укажите папку, куда ваш OBS или софт записи сохраняет видео или аудиозаписи.\nКак только запись завершится, AutoCens автоматически запустит цензуру!")
            lbl_info.setWordWrap(True)
            vbox.addWidget(lbl_info)

            h_folder = QHBoxLayout()
            self.txt_watch_folder = QTextEdit()
            self.txt_watch_folder.setMaximumHeight(35)
            self.txt_watch_folder.setText(self.config.get("watch_folder", ""))
            self.txt_watch_folder.setPlaceholderText("Выберите папку для отслеживания...")
            
            btn_watch_browse = QPushButton("📁 Выбрать папку...")
            btn_watch_browse.clicked.connect(self.browse_watch_folder)

            h_folder.addWidget(self.txt_watch_folder)
            h_folder.addWidget(btn_watch_browse)
            vbox.addLayout(h_folder)

            self.chk_watch_toggle = QCheckBox("🟢 Включить фоновый мониторинг папки (Переключатель)")
            self.chk_watch_toggle.setChecked(self.config.get("watch_folder_enabled", False))
            self.chk_watch_toggle.setStyleSheet("font-size: 14px; font-weight: bold; color: #00ffcc;")
            self.chk_watch_toggle.toggled.connect(self.toggle_watch_folder)
            vbox.addWidget(self.chk_watch_toggle)

            self.lbl_watch_status = QLabel("Статус: Мониторинг отключен")
            self.lbl_watch_status.setStyleSheet("font-weight: bold; color: #ffcc00;")
            vbox.addWidget(self.lbl_watch_status)

            layout.addWidget(grp_watch)

        def setup_stats_tab(self):
            layout = QVBoxLayout(self.tab_stats)

            cards_layout = QHBoxLayout()

            self.card_total_profanities = QLabel("0\nВсего матов запикано")
            self.card_total_profanities.setStyleSheet("background-color: #1e1e2f; color: #00ffcc; font-size: 18px; font-weight: bold; padding: 15px; border-radius: 8px; text-align: center;")
            self.card_total_profanities.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.card_total_videos = QLabel("0\nОбработано файлов")
            self.card_total_videos.setStyleSheet("background-color: #1e1e2f; color: #ffcc00; font-size: 18px; font-weight: bold; padding: 15px; border-radius: 8px; text-align: center;")
            self.card_total_videos.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.card_total_hours = QLabel("0.0 ч\nСуммарная длительность")
            self.card_total_hours.setStyleSheet("background-color: #1e1e2f; color: #ff6699; font-size: 18px; font-weight: bold; padding: 15px; border-radius: 8px; text-align: center;")
            self.card_total_hours.setAlignment(Qt.AlignmentFlag.AlignCenter)

            cards_layout.addWidget(self.card_total_profanities)
            cards_layout.addWidget(self.card_total_videos)
            cards_layout.addWidget(self.card_total_hours)
            layout.addLayout(cards_layout)

            lbl_table = QLabel("📊 Частотный словарь использованных матерных слов:")
            lbl_table.setStyleSheet("font-weight: bold; margin-top: 10px;")
            layout.addWidget(lbl_table)

            self.stats_table = QTableWidget()
            self.stats_table.setColumnCount(3)
            self.stats_table.setHorizontalHeaderLabels(["Слово / Выражение", "Количество повторений", "Доля %"])
            self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            layout.addWidget(self.stats_table)

            btn_refresh = QPushButton("🔄 Обновить статистику")
            btn_refresh.clicked.connect(self.refresh_stats_view)
            layout.addWidget(btn_refresh)

        def setup_settings_tab(self):
            layout = QVBoxLayout(self.tab_settings)

            grp_pad = QGroupBox("Микро-отступы цензуры (для плавности звука)")
            pad_layout = QVBoxLayout(grp_pad)

            lbl_p1 = QLabel("Отступ ДО слова (сек):")
            self.spin_pad_start = QDoubleSpinBox()
            self.spin_pad_start.setRange(0.0, 0.5)
            self.spin_pad_start.setSingleStep(0.01)
            self.spin_pad_start.setValue(self.config.get("padding_start_sec", 0.04))

            lbl_p2 = QLabel("Отступ ПОСЛЕ слова (сек):")
            self.spin_pad_end = QDoubleSpinBox()
            self.spin_pad_end.setRange(0.0, 0.5)
            self.spin_pad_end.setSingleStep(0.01)
            self.spin_pad_end.setValue(self.config.get("padding_end_sec", 0.04))

            pad_layout.addWidget(lbl_p1)
            pad_layout.addWidget(self.spin_pad_start)
            pad_layout.addWidget(lbl_p2)
            pad_layout.addWidget(self.spin_pad_end)
            layout.addWidget(grp_pad)

            grp_dict = QGroupBox("Дополнительные матерные слова (по одного на строку)")
            dict_layout = QVBoxLayout(grp_dict)
            self.txt_custom_bad = QTextEdit()
            self.txt_custom_bad.setText("\n".join(self.config.get("custom_bad_words", [])))
            dict_layout.addWidget(self.txt_custom_bad)
            layout.addWidget(grp_dict)

            btn_save = QPushButton("💾 Сохранить настройки")
            btn_save.setStyleSheet("background-color: #198754; color: white; font-weight: bold; padding: 8px;")
            btn_save.clicked.connect(self.save_settings)
            layout.addWidget(btn_save)

        def browse_file(self):
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Выберите медиафайл", "", "Media Files (*.mp4 *.mov *.mkv *.avi *.wav *.mp3 *.m4a *.aac *.flac)"
            )
            if file_path:
                self.input_file_edit.setText(file_path)

        def browse_watch_folder(self):
            folder_path = QFileDialog.getExistingDirectory(self, "Выберите папку для отслеживания файлов")
            if folder_path:
                self.txt_watch_folder.setText(folder_path)
                self.config["watch_folder"] = folder_path
                self.save_config()

        def toggle_watch_folder(self, enabled: bool):
            folder = self.txt_watch_folder.toPlainText().strip()
            self.config["watch_folder_enabled"] = enabled
            self.config["watch_folder"] = folder
            self.save_config()

            if enabled:
                if not folder or not os.path.exists(folder):
                    QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите существующую папку для авто-нарезок!")
                    self.chk_watch_toggle.setChecked(False)
                    return

                def auto_process_file(file_path):
                    base, ext = os.path.splitext(file_path)
                    out = f"{base}_censored{ext}"
                    thread = ProcessingThread(file_path, out, self.config)
                    thread.run()

                self.watch_monitor = WatchFolderMonitor(folder, auto_process_file)
                self.watch_monitor.start()
                self.lbl_watch_status.setText(f"🟢 СТАТУС: Активен мониторинг папки: {folder}")
                self.lbl_watch_status.setStyleSheet("color: #00ffcc; font-weight: bold;")
            else:
                if self.watch_monitor:
                    self.watch_monitor.stop()
                    self.watch_monitor = None
                self.lbl_watch_status.setText("🔴 СТАТУС: Мониторинг папки отключен")
                self.lbl_watch_status.setStyleSheet("color: #ff4d4d; font-weight: bold;")

        def refresh_stats_view(self):
            summary = self.stats_mgr.get_summary()

            self.card_total_profanities.setText(f"{summary['total_profanities']}\nВсего матов запикано")
            self.card_total_videos.setText(f"{summary['total_videos']}\nОбработано файлов")
            
            total_sec = self.stats_mgr.stats.get("total_video_duration_seconds", 0.0)
            if total_sec >= 3600.0:
                hours_str = f"{total_sec / 3600.0:.1f} ч"
            elif total_sec >= 60.0:
                hours_str = f"{total_sec / 60.0:.1f} мин"
            else:
                hours_str = f"{int(total_sec)} сек"

            self.card_total_hours.setText(f"{hours_str}\nСуммарная длительность")

            top_words = summary['top_words']
            total_count = max(1, summary['total_profanities'])

            self.stats_table.setRowCount(len(top_words))
            for row, (word, count) in enumerate(top_words):
                pct = (count / total_count) * 100.0
                self.stats_table.setItem(row, 0, QTableWidgetItem(word))
                self.stats_table.setItem(row, 1, QTableWidgetItem(str(count)))
                self.stats_table.setItem(row, 2, QTableWidgetItem(f"{pct:.1f}%"))

        def save_settings(self):
            self.config["padding_start_sec"] = self.spin_pad_start.value()
            self.config["padding_end_sec"] = self.spin_pad_end.value()
            self.config["root_only_muting"] = self.chk_root_only.isChecked()
            self.config["export_davinci_markers"] = self.chk_davinci.isChecked()
            custom_bad = [line.strip() for line in self.txt_custom_bad.toPlainText().split("\n") if line.strip()]
            self.config["custom_bad_words"] = custom_bad
            self.save_config()
            QMessageBox.information(self, "Сохранено", "Настройки успешно сохранены!")

        def start_processing(self):
            media_path = self.input_file_edit.toPlainText().strip()
            if not media_path or not os.path.exists(media_path):
                QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите валидный медиафайл!")
                return

            base, ext = os.path.splitext(media_path)
            output_path = f"{base}_censored{ext}"

            mode_idx = self.combo_mode.currentIndex()
            censor_mode = "volume_ducking"
            if mode_idx == 1:
                censor_mode = "mute"
            elif mode_idx == 2:
                censor_mode = "beep"

            model_idx = self.combo_model.currentIndex()
            if model_idx == 0:
                model_size = "antony66/whisper-large-v3-russian"
            elif model_idx == 1:
                model_size = "medium"
            elif model_idx == 2:
                model_size = "large-v3"
            elif model_idx == 3:
                model_size = "small"
            else:
                model_size = "base"

            dev_map = ["auto", "cuda", "cpu"]
            device = dev_map[self.combo_device.currentIndex()]

            self.config["censor_mode"] = censor_mode
            self.config["model_size"] = model_size
            self.config["device"] = device
            self.config["root_only_muting"] = self.chk_root_only.isChecked()
            self.config["export_davinci_markers"] = self.chk_davinci.isChecked()

            self.btn_start.setEnabled(False)
            self.log_text.clear()
            self.progress_bar.setValue(0)

            self.thread = ProcessingThread(media_path, output_path, self.config)
            self.thread.progress_signal.connect(self.update_progress)
            self.thread.log_signal.connect(self.append_log)
            self.thread.finished_signal.connect(self.processing_finished)
            self.thread.start()

        def update_progress(self, val: float, text: str):
            self.progress_bar.setValue(int(val * 100))
            self.lbl_status.setText(text)

        def append_log(self, text: str):
            self.log_text.append(text)

        def processing_finished(self, success: bool, msg: str, data: dict):
            self.btn_start.setEnabled(True)
            if success:
                density_data = data.get("density_data", [])
                self.heatmap_widget.set_data(density_data)

                self.current_segments = data.get("segments", [])
                self.current_profane_words = data.get("profane_words", [])
                self.render_transcript_html()

                QMessageBox.information(self, "Успешно!", f"{msg}\nМатометр и расшифровка обновлены!")
                self.refresh_stats_view()
            else:
                QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при обработке:\n{msg}")

        def apply_dark_theme(self):
            dark_stylesheet = """
            QMainWindow, QDialog {
                background-color: #121212;
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #2d2d2d;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #b0b0b0;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #0d6efd;
                color: #ffffff;
                font-weight: bold;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #00bcd4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }
            QProgressBar {
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                text-align: center;
                color: white;
                background-color: #252526;
            }
            QProgressBar::chunk {
                background-color: #0d6efd;
                width: 10px;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                gridline-color: #333333;
                border: 1px solid #333333;
            }
            QHeaderView::section {
                background-color: #252526;
                color: #00bcd4;
                font-weight: bold;
                border: 1px solid #333333;
                padding: 4px;
            }
            """
            self.setStyleSheet(dark_stylesheet)


def launch_gui():
    if not HAS_PYQT6:
        print("PyQt6 не установлен. Установите с помощью: pip install PyQt6")
        return
    app = QApplication(sys.argv)
    window = AutoCensGUI()
    window.show()
    sys.exit(app.exec())
