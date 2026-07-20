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
        QHeaderView, QGroupBox, QSlider, QMessageBox, QCheckBox
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QFont, QColor
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False

from core.transcriber import WhisperTranscriber
from core.profanity_filter import ProfanityFilter
from core.audio_processor import AudioProcessor
from core.stats_manager import StatsManager
from core.export_manager import ExportManager
from core.watch_folder import WatchFolderMonitor

class ProcessingThread(QThread if HAS_PYQT6 else object):
    """Фоновый поток обработки видео для GUI."""
    if HAS_PYQT6:
        progress_signal = pyqtSignal(float, str)
        finished_signal = pyqtSignal(bool, str, dict)
        log_signal = pyqtSignal(str)

    def __init__(self, video_path: str, output_path: str, config: dict):
        if HAS_PYQT6:
            super().__init__()
        self.video_path = video_path
        self.output_path = output_path
        self.config = config

    def run(self):
        try:
            self.emit_log(f"🎬 Начало обработки файла: {os.path.basename(self.video_path)}")
            
            processor = AudioProcessor()
            temp_wav = self.video_path + ".temp_input.wav"
            temp_out_wav = self.video_path + ".temp_censored.wav"
            
            self.emit_progress(0.05, "Извлечение аудиодорожки...")
            video_duration_sec = processor.extract_audio(self.video_path, temp_wav)
            if video_duration_sec <= 0:
                video_duration_sec = processor.get_media_duration(self.video_path)

            self.emit_log(f"⏱ Длительность файла: {int(video_duration_sec // 3600):02d}:{int((video_duration_sec % 3600) // 60):02d}:{int(video_duration_sec % 60):02d}")

            self.emit_progress(0.10, "Загрузка модели Whisper и транскрибация...")
            transcriber = WhisperTranscriber(
                model_size=self.config.get("model_size", "medium"),
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

            self.emit_progress(0.75, "Анализ и поиск матерных слов...")
            p_filter = ProfanityFilter(
                custom_bad_words=self.config.get("custom_bad_words", []),
                custom_whitelist=self.config.get("whitelist_words", [])
            )
            profane_words = p_filter.find_profanity_in_segments(segments)
            self.emit_log(f" Найдено нецензурных слов: {len(profane_words)}")

            export_mgr = ExportManager()
            highlights = export_mgr.find_highlight_moments(profane_words)
            if highlights:
                self.emit_log("\n🔥 ТОП ЭМОЦИОНАЛЬНЫХ ПИКОВ СТРИМА (для YouTube Shorts / TikTok):")
                for idx, h in enumerate(highlights[:5], 1):
                    self.emit_log(f"   {idx}. ⏰ [{h['timestamp_str']}] — {h['swear_count']} матов за 30с")

            if self.config.get("export_davinci_markers", True):
                base_no_ext = os.path.splitext(self.output_path)[0]
                csv_path = f"{base_no_ext}_davinci_markers.csv"
                export_mgr.export_davinci_csv(profane_words, csv_path)
                self.emit_log(f"📌 Маркеры для DaVinci Resolve сохранены: {os.path.basename(csv_path)}")

            self.emit_progress(0.85, "Применение глушения/запикивания на аудио...")
            processor.censor_audio_numpy(
                input_wav_path=temp_wav,
                output_wav_path=temp_out_wav,
                profane_timestamps=profane_words,
                censor_mode=self.config.get("censor_mode", "volume_ducking"),
                attenuation_db=self.config.get("attenuation_db", -24.0),
                beep_freq=self.config.get("beep_frequency", 1000),
                padding_start=self.config.get("padding_start_sec", 0.06),
                padding_end=self.config.get("padding_end_sec", 0.06),
                fade_duration=self.config.get("fade_duration_sec", 0.02)
            )

            self.emit_progress(0.92, "Мультиплексирование видео (FFmpeg Stream Copy)...")
            processor.mux_video(self.video_path, temp_out_wav, self.output_path)

            for tmp in (temp_wav, temp_out_wav):
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

            stats_mgr = StatsManager()
            session_data = stats_mgr.add_processing_session(
                video_name=self.video_path,
                video_duration_sec=video_duration_sec,
                profane_words_detected=profane_words,
                censor_mode=self.config.get("censor_mode", "volume_ducking")
            )

            self.emit_progress(1.0, " Обработка успешно завершена!")
            self.emit_finished(True, f"Файл сохранен: {self.output_path}", session_data)

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
            
            self.setWindowTitle("AutoCens — Автоматическое запикивание мата в видео (Stream Copy)")
            self.resize(950, 720)
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
                "model_size": "medium",
                "device": "auto",
                "censor_mode": "volume_ducking",
                "attenuation_db": -24.0,
                "beep_frequency": 1000,
                "padding_start_sec": 0.06,
                "padding_end_sec": 0.06,
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
            self.tabs.addTab(self.tab_process, "🎬 Обработка видео")

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

            file_box = QGroupBox("Выбор медиафайла (MP4, MOV, MKV, AVI)")
            file_layout = QHBoxLayout(file_box)
            
            self.input_file_edit = QTextEdit()
            self.input_file_edit.setMaximumHeight(35)
            self.input_file_edit.setPlaceholderText("Выберите или перетащите файл...")
            
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
            self.combo_model.addItems(["base (очень быстро)", "small (быстро)", "medium (рекомендуется)", "large-v3 (макс. точность)"])
            m_size = self.config.get("model_size", "medium")
            for i, name in enumerate(["base", "small", "medium", "large"]):
                if name in m_size:
                    self.combo_model.setCurrentIndex(i)

            lbl_device = QLabel("Ускорение:")
            self.combo_device = QComboBox()
            self.combo_device.addItems(["Auto (Автовыбор GPU/CPU)", "NVIDIA CUDA (GPU)", "CPU (Процессор)"])
            cur_dev = self.config.get("device", "auto")
            if cur_dev == "cuda":
                self.combo_device.setCurrentIndex(1)
            elif cur_dev == "cpu":
                self.combo_device.setCurrentIndex(2)
            else:
                self.combo_device.setCurrentIndex(0)

            params_layout.addWidget(lbl_mode)
            params_layout.addWidget(self.combo_mode)
            params_layout.addWidget(lbl_model)
            params_layout.addWidget(self.combo_model)
            params_layout.addWidget(lbl_device)
            params_layout.addWidget(self.combo_device)
            layout.addWidget(params_box)

            has_gpu, gpu_desc = WhisperTranscriber.get_gpu_info()
            self.lbl_gpu_status = QLabel(f"⚡ Ускорение: {gpu_desc}")
            self.lbl_gpu_status.setStyleSheet("color: #00ffcc; font-weight: bold; padding: 2px;")
            layout.addWidget(self.lbl_gpu_status)

            self.chk_davinci = QCheckBox("📌 Автоматически генерировать файл маркеров для DaVinci Resolve (.csv)")
            self.chk_davinci.setChecked(self.config.get("export_davinci_markers", True))
            layout.addWidget(self.chk_davinci)

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
            self.log_text.setReadOnly(True)
            layout.addWidget(self.log_text)

        def setup_watch_tab(self):
            layout = QVBoxLayout(self.tab_watch)

            grp_watch = QGroupBox("Автоматический мониторинг папки записи (OBS / Twitch)")
            vbox = QVBoxLayout(grp_watch)

            lbl_info = QLabel("Укажите папку, куда ваш OBS или софт записи сохраняет видеозаписи.\nКак только запись стрима завершится, AutoCens автоматически запустит цензуру и приготовит маркеры!")
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

            self.card_total_videos = QLabel("0\nОбработано видео")
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
            self.spin_pad_start.setValue(self.config.get("padding_start_sec", 0.06))

            lbl_p2 = QLabel("Отступ ПОСЛЕ слова (сек):")
            self.spin_pad_end = QDoubleSpinBox()
            self.spin_pad_end.setRange(0.0, 0.5)
            self.spin_pad_end.setSingleStep(0.01)
            self.spin_pad_end.setValue(self.config.get("padding_end_sec", 0.06))

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
                self, "Выберите видеофайл", "", "Video Files (*.mp4 *.mov *.mkv *.avi)"
            )
            if file_path:
                self.input_file_edit.setText(file_path)

        def browse_watch_folder(self):
            folder_path = QFileDialog.getExistingDirectory(self, "Выберите папку для отслеживания видео")
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
            self.card_total_videos.setText(f"{summary['total_videos']}\nОбработано видео")
            
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
            self.config["export_davinci_markers"] = self.chk_davinci.isChecked()
            custom_bad = [line.strip() for line in self.txt_custom_bad.toPlainText().split("\n") if line.strip()]
            self.config["custom_bad_words"] = custom_bad
            self.save_config()
            QMessageBox.information(self, "Сохранено", "Настройки успешно сохранены!")

        def start_processing(self):
            video_path = self.input_file_edit.toPlainText().strip()
            if not video_path or not os.path.exists(video_path):
                QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите валидный видеофайл!")
                return

            base, ext = os.path.splitext(video_path)
            output_path = f"{base}_censored{ext}"

            mode_idx = self.combo_mode.currentIndex()
            censor_mode = "volume_ducking"
            if mode_idx == 1:
                censor_mode = "mute"
            elif mode_idx == 2:
                censor_mode = "beep"

            model_size_map = ["base", "small", "medium", "large-v3"]
            model_size = model_size_map[self.combo_model.currentIndex()]

            dev_map = ["auto", "cuda", "cpu"]
            device = dev_map[self.combo_device.currentIndex()]

            self.config["censor_mode"] = censor_mode
            self.config["model_size"] = model_size
            self.config["device"] = device
            self.config["export_davinci_markers"] = self.chk_davinci.isChecked()

            self.btn_start.setEnabled(False)
            self.log_text.clear()
            self.progress_bar.setValue(0)

            self.thread = ProcessingThread(video_path, output_path, self.config)
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
                QMessageBox.information(self, "Успешно!", f"{msg}\nСтатистика обновлена!")
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
            QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
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
