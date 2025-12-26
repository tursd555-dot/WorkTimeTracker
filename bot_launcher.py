
import sys
import os
import subprocess
import threading
import shutil
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor

# === Настройки логирования ===
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bot_launcher.log"


def write_to_logfile(message: str):
    """Запись строки в лог-файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


class LogReaderThread(QThread):
    """Фоновое чтение stdout/stderr бота"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, process: subprocess.Popen):
        super().__init__()
        self.process = process
        self._running = True

    def run(self):
        if not self.process or not self.process.stdout:
            return
        try:
            for line in self.process.stdout:
                if not self._running:
                    break
                line = line.strip()
                if line:
                    self.log_signal.emit(line)
                    write_to_logfile(line)
            code = self.process.wait()
            self.finished_signal.emit(code)
        except Exception as e:
            msg = f"⚠️ Ошибка чтения лога: {e}"
            self.log_signal.emit(msg)
            write_to_logfile(msg)

    def stop(self):
        self._running = False


class BotLauncher(QWidget):
    def __init__(self, mode="linker"):
        super().__init__()
        self.mode = mode  # "linker" или "monitor"
        mode_name = "Linker Bot" if mode == "linker" else "Monitor Bot (24/7)"
        self.setWindowTitle(f"WorkTimeTracker Bot — {mode_name}")
        self.resize(750, 450)
        self.process = None
        self.reader_thread = None
        self._init_ui()
        self._setup_timers()
        self.start_bot(auto=True)  # автозапуск при открытии

    # ---------- UI ----------
    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("⏳ Инициализация...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(
            "background-color: #111; color: #0f0; font-family: Consolas, monospace; font-size: 12px;"
        )

        btn_layout = QHBoxLayout()
        self.btn_restart = QPushButton("🔄 Перезапустить")
        self.btn_stop = QPushButton("🛑 Остановить")
        self.btn_clear = QPushButton("🧹 Очистить лог")

        btn_layout.addWidget(self.btn_restart)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_clear)

        layout.addWidget(self.status_label)
        layout.addWidget(self.log_box)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # Привязка кнопок
        self.btn_restart.clicked.connect(lambda: self.start_bot(auto=False))
        self.btn_stop.clicked.connect(self.stop_bot)
        self.btn_clear.clicked.connect(self.log_box.clear)

    # ---------- Логика ----------
    def _setup_timers(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._check_process)
        self.timer.start(2000)

    def _append_log(self, text: str):
        cursor = self.log_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text + "\n")
        self.log_box.setTextCursor(cursor)
        self.log_box.ensureCursorVisible()
        write_to_logfile(text)

    def start_bot(self, auto=False):
        """Запуск Telegram-бота"""
        if self.process:
            self._append_log("⚠️ Бот уже запущен.")
            return
        try:
            mode_text = "Linker Bot" if self.mode == "linker" else "Monitor Bot (24/7)"
            if auto:
                self._append_log(f"🚀 Автозапуск {mode_text}...")
            else:
                self._append_log(f"🔄 Перезапуск {mode_text}...")

            self.status_label.setText("🟡 Запуск бота...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold; font-size: 16px;")

            # --- Исправление: правильный запуск из exe ---
            if getattr(sys, "frozen", False):
                # Если запущен из собранного exe
                exe_dir = Path(sys.executable).parent
                _internal_dir = exe_dir / "_internal"
                
                # Проверяем, есть ли telegram_bot в _internal
                internal_bot = _internal_dir / "telegram_bot" / "main.py"
                
                if internal_bot.exists():
                    # Модуль найден в _internal - запускаем через python
                    # Ищем python в системе или используем тот, что был при сборке
                    system_python = shutil.which("python") or shutil.which("python3") or "python"
                    cmd = [system_python, str(internal_bot)]
                    cwd = str(_internal_dir.parent)  # Директория с exe
                else:
                    # Модуль не найден - пытаемся найти в исходниках проекта
                    # (если exe запущен из директории проекта)
                    project_root = Path(__file__).parent if hasattr(sys, '_MEIPASS') else Path.cwd()
                    bot_script = project_root / "telegram_bot" / "main.py"
                    
                    if bot_script.exists():
                        system_python = shutil.which("python") or shutil.which("python3") or "python"
                        cmd = [system_python, str(bot_script)]
                        cwd = str(project_root)
                    else:
                        # Последняя попытка - запустить через -m (если модуль в PYTHONPATH)
                        system_python = shutil.which("python") or shutil.which("python3") or "python"
                        cmd = [system_python, "-m", "telegram_bot.main"]
                        cwd = str(exe_dir)
            else:
                # Если запущен из исходников — используем текущий интерпретатор
                bot_script = Path(__file__).parent / "telegram_bot" / "main.py"
                cmd = [sys.executable, str(bot_script)]
                cwd = str(Path(__file__).parent)
            
            # Добавляем флаг режима
            if self.mode == "monitor":
                cmd.append("--monitor")
            
            # Важно: устанавливаем переменную окружения для режима
            env = os.environ.copy()
            env["BOT_MODE"] = self.mode
            
            # Добавляем путь к _internal в PYTHONPATH для exe
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).parent
                _internal_dir = exe_dir / "_internal"
                if _internal_dir.exists():
                    pythonpath = env.get("PYTHONPATH", "")
                    if pythonpath:
                        env["PYTHONPATH"] = f"{str(_internal_dir)}{os.pathsep}{pythonpath}"
                    else:
                        env["PYTHONPATH"] = str(_internal_dir)

            # важно: cwd = корень проекта, чтобы импортировался config.py
            self.process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            self.reader_thread = LogReaderThread(self.process)
            self.reader_thread.log_signal.connect(self._append_log)
            self.reader_thread.finished_signal.connect(self._on_bot_exit)
            self.reader_thread.start()

            self.status_label.setText("🟢 Бот запущен")
            self.status_label.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 16px;")
            self._append_log("✅ Бот успешно запущен.")
        except Exception as e:
            msg = f"❌ Ошибка запуска: {e}"
            self._append_log(msg)
            self.status_label.setText("❌ Ошибка запуска")
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 16px;")

    def _on_bot_exit(self, code: int):
        msg = f"⚠️ Бот завершил работу (код {code})."
        self._append_log(msg)
        self.status_label.setText("🔴 Бот остановлен")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 16px;")
        self.process = None
        self.reader_thread = None

    def stop_bot(self):
        if self.process:
            self._append_log("🛑 Остановка бота...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                self._append_log(f"⚠️ Ошибка при остановке: {e}")
            self.process = None
            self.status_label.setText("🔴 Бот остановлен")
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 16px;")
        else:
            self._append_log("⚠️ Бот не запущен.")

    def _check_process(self):
        if self.process and self.process.poll() is not None:
            self._append_log("⚠️ Процесс бота завершился.")
            self.status_label.setText("🔴 Бот завершился")
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 16px;")
            self.process = None
            self.reader_thread = None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='WorkTimeTracker Bot Launcher')
    parser.add_argument('--monitor', action='store_true', help='Запустить Monitor Bot (24/7) вместо Linker Bot')
    args = parser.parse_args()
    
    mode = "monitor" if args.monitor else "linker"
    
    app = QApplication(sys.argv)
    win = BotLauncher(mode=mode)
    win.show()
    sys.exit(app.exec_())