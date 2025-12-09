#!/usr/bin/env python3
"""
Проверка логов user app на предмет работы таймера проверки kick
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

def find_log_file():
    """Находит файл логов user app"""

    # Возможные пути к логам
    possible_paths = [
        Path.home() / "AppData" / "Roaming" / "WorkTimeTracker" / "logs",  # Windows
        Path.home() / ".local" / "share" / "WorkTimeTracker" / "logs",      # Linux
        Path.home() / "Library" / "Application Support" / "WorkTimeTracker" / "logs",  # macOS
        Path("logs"),  # Локальная папка
    ]

    for log_dir in possible_paths:
        if log_dir.exists():
            # Ищем последний лог файл
            log_files = list(log_dir.glob("*.log"))
            if log_files:
                # Сортируем по времени модификации
                latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                return latest_log

    return None

def check_timer_logs(log_file, minutes=10):
    """Проверяет логи на наличие записей о работе таймера"""

    print("=" * 80)
    print(f"ПРОВЕРКА ЛОГОВ: {log_file.name}")
    print("=" * 80)

    if not log_file.exists():
        print(f"❌ Файл логов не найден: {log_file}")
        return False

    print(f"📁 Путь: {log_file}")
    print(f"📅 Последнее изменение: {datetime.fromtimestamp(log_file.stat().st_mtime)}")
    print(f"📊 Размер: {log_file.stat().st_size / 1024:.1f} KB\n")

    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Ищем записи за последние N минут
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        # Ключевые слова для поиска
        timer_keywords = [
            "AUTO_LOGOUT_DETECT",
            "ACTIVESESSIONS",
            "_auto_check_shift_ended",
            "_is_session_finished_remote",
            "shift_check_timer",
            "ADMIN_LOGOUT",
            "force_logout_by_admin"
        ]

        print(f"Ищем записи за последние {minutes} минут...\n")

        relevant_lines = []
        for line in lines:
            # Проверяем по ключевым словам
            if any(keyword in line for keyword in timer_keywords):
                relevant_lines.append(line.strip())

        if not relevant_lines:
            print(f"❌ Не найдено записей о работе таймера проверки")
            print(f"\nВозможные причины:")
            print(f"  1. User app не запущен")
            print(f"  2. Таймер не запускается (ошибка в коде)")
            print(f"  3. Логирование отключено")
            print(f"\nПоследние 10 строк лога:")
            for line in lines[-10:]:
                print(f"  {line.strip()}")
            return False

        print(f"✅ Найдено {len(relevant_lines)} релевантных записей:\n")

        # Показываем последние 20 записей
        for line in relevant_lines[-20:]:
            # Раскрашиваем важные строки
            if "kicked" in line.lower() or "ADMIN_LOGOUT" in line:
                print(f"🔴 {line}")
            elif "AUTO_LOGOUT_DETECT" in line:
                print(f"🟢 {line}")
            elif "ACTIVESESSIONS" in line:
                print(f"🔵 {line}")
            else:
                print(f"   {line}")

        # Анализируем проблему
        print("\n" + "=" * 80)
        print("АНАЛИЗ")
        print("=" * 80)

        has_timer_work = any("AUTO_LOGOUT_DETECT" in line for line in relevant_lines)
        has_active_sessions = any("ACTIVESESSIONS" in line for line in relevant_lines)
        has_kicked = any("kicked" in line.lower() for line in relevant_lines)
        has_admin_logout = any("ADMIN_LOGOUT" in line for line in relevant_lines)

        if has_timer_work:
            print("✅ Таймер проверки работает (_auto_check_shift_ended вызывается)")
        else:
            print("❌ Таймер проверки НЕ РАБОТАЕТ")

        if has_active_sessions:
            print("✅ Проверка ActiveSessions выполняется")
        else:
            print("❌ Проверка ActiveSessions НЕ выполняется")

        if has_kicked:
            print("✅ Статус 'kicked' был обнаружен в логах")
        else:
            print("⚠️  Статус 'kicked' НЕ обнаружен (возможно не было kick)")

        if has_admin_logout:
            print("✅ Метод force_logout_by_admin был вызван")
        else:
            print("❌ Метод force_logout_by_admin НЕ был вызван")

        # Выводы
        print("\nВЫВОДЫ:")
        if not has_timer_work:
            print("  → Проблема: Таймер shift_check_timer не запускается")
            print("  → Решение: Проверьте инициализацию таймера в gui.py:315-318")
        elif not has_active_sessions:
            print("  → Проблема: Метод _is_session_finished_remote не вызывается")
            print("  → Решение: Проверьте логику в _auto_check_shift_ended (gui.py:355-375)")
        elif has_kicked and not has_admin_logout:
            print("  → Проблема: Kick обнаружен, но force_logout_by_admin не вызван")
            print("  → Решение: Проверьте условие в gui.py:371-375")
        elif not has_kicked:
            print("  → Проблема: Статус 'kicked' не обнаружен в базе данных")
            print("  → Решение: Запустите test_kick_realtime.py для kick активной сессии")

        return True

    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    log_file = find_log_file()

    if not log_file:
        print("❌ Файл логов не найден")
        print("\nВозможные причины:")
        print("  1. User app ещё не запускался")
        print("  2. Логирование не настроено")
        print("\nПопробуйте:")
        print("  1. Запустите: python user_app/main.py")
        print("  2. Войдите в систему")
        print("  3. Запустите этот скрипт снова")
        sys.exit(1)

    check_timer_logs(log_file, minutes=30)
