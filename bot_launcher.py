
import sys
import os
import subprocess
import threading
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


def run_worker_mode(mode: str) -> int:
    """
    Режим дочернего воркера бота.
    Важно для собранного exe: не требует установленного system python.
    """
    mode = (mode or os.getenv("BOT_MODE", "linker")).strip().lower()
    if mode not in ("linker", "monitor"):
        mode = "linker"

    # На Windows CP1251 часто не умеет emoji/символы; не даем процессу
    # падать из-за UnicodeEncodeError в print/logging.
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="replace")
        except Exception:
            pass

    base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    try:
        os.chdir(str(base_dir))
    except Exception:
        pass

    os.environ["BOT_MODE"] = mode
    print(f"[worker] mode={mode}, cwd={os.getcwd()}", flush=True)
    write_to_logfile(f"[worker] mode={mode}, cwd={os.getcwd()}")

    if mode == "monitor":
        from telegram_bot.monitor_bot import main as bot_main
    else:
        from telegram_bot.main import main as bot_main

    bot_main()
    return 0


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
    def __init__(self, mode="monitor"):
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

            if getattr(sys, "frozen", False):
                # Критично: в собранном приложении запускаем worker через этот же exe,
                # чтобы не зависеть от установленного в системе python (ошибка 9009).
                exe_path = str(Path(sys.executable))
                cmd = [exe_path, "--worker", "--mode", self.mode]
                cwd = str(Path(sys.executable).parent)
            else:
                # Режим исходников: запускаем скрипт текущим интерпретатором.
                bot_script = Path(__file__).parent / "telegram_bot" / "main.py"
                if bot_script.exists():
                    cmd = [sys.executable, str(bot_script)]
                else:
                    cmd = [sys.executable, "-m", "telegram_bot.main"]
                if self.mode == "monitor":
                    cmd.append("--monitor")
                cwd = str(Path(__file__).parent)
            
            # Важно: устанавливаем переменную окружения для режима
            env = os.environ.copy()
            env["BOT_MODE"] = self.mode
            
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
            if self.mode == "linker":
                self._append_log("ℹ️ Linker mode: привязка email к Telegram. Уведомления мониторинга в этом режиме не отправляются.")
            else:
                self._append_log("ℹ️ Monitor mode: активен мониторинг нарушений и отправка уведомлений.")
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
    parser.add_argument('--monitor', action='store_true', help='Запустить Monitor Bot (24/7)')
    parser.add_argument('--linker', action='store_true', help='Запустить Linker Bot (привязка email -> chat_id)')
    parser.add_argument('--worker', action='store_true', help='Внутренний режим: запуск bot worker без GUI')
    parser.add_argument('--mode', choices=['linker', 'monitor'], help='Режим worker-процесса')
    args = parser.parse_args()

    env_mode = (os.getenv("BOT_MODE", "monitor") or "monitor").strip().lower()
    if env_mode not in ("linker", "monitor"):
        env_mode = "monitor"
    
    if args.worker:
        if args.mode:
            worker_mode = args.mode
        elif args.monitor:
            worker_mode = "monitor"
        elif args.linker:
            worker_mode = "linker"
        else:
            worker_mode = env_mode
        sys.exit(run_worker_mode(worker_mode))

    if args.monitor:
        mode = "monitor"
    elif args.linker:
        mode = "linker"
    else:
        # По умолчанию запускаем monitor, т.к. это режим уведомлений.
        mode = env_mode

    app = QApplication(sys.argv)
    win = BotLauncher(mode=mode)
    win.show()
    sys.exit(app.exec_())