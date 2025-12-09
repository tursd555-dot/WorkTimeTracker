#!/usr/bin/env python3
"""
Диагностический скрипт для анализа работы синхронизации WorkTimeTracker
Показывает полную картину: очередь, циклы, интернет, производительность
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import re
from collections import defaultdict

def print_header(text):
    print(f"\n{'=' * 80}")
    print(f"  {text}")
    print('=' * 80)

def print_section(text):
    print(f"\n{'-' * 80}")
    print(f"  {text}")
    print('-' * 80)

def analyze_database(db_path):
    """Анализ базы данных"""
    print_header("📊 АНАЛИЗ БАЗЫ ДАННЫХ")
    
    if not Path(db_path).exists():
        print(f"❌ База данных не найдена: {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Всего записей
    cursor.execute("SELECT COUNT(*) FROM actions")
    total = cursor.fetchone()[0]
    print(f"✅ Всего записей: {total}")
    
    # Несинхронизированные
    cursor.execute("SELECT COUNT(*) FROM actions WHERE synced = 0")
    unsynced = cursor.fetchone()[0]
    print(f"⚠️  Несинхронизированные: {unsynced}")
    
    if unsynced > 0:
        print(f"   📈 Процент несинхронизированных: {unsynced/total*100:.1f}%")
    
    # По пользователям
    print_section("Несинхронизированные по пользователям")
    cursor.execute("""
        SELECT email, COUNT(*) as cnt 
        FROM actions 
        WHERE synced = 0 
        GROUP BY email 
        ORDER BY cnt DESC 
        LIMIT 10
    """)
    
    for email, cnt in cursor.fetchall():
        print(f"   {email}: {cnt} записей")
    
    # По датам
    print_section("Несинхронизированные по дням")
    cursor.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as cnt 
        FROM actions 
        WHERE synced = 0 
        GROUP BY DATE(timestamp) 
        ORDER BY date DESC 
        LIMIT 7
    """)
    
    for date, cnt in cursor.fetchall():
        print(f"   {date}: {cnt} записей")
    
    # Старые несинхронизированные
    cursor.execute("""
        SELECT MIN(timestamp), MAX(timestamp) 
        FROM actions 
        WHERE synced = 0
    """)
    min_ts, max_ts = cursor.fetchone()
    
    if min_ts:
        print_section("Временной диапазон несинхронизированных")
        print(f"   Самая старая: {min_ts}")
        print(f"   Самая новая: {max_ts}")
        
        min_dt = datetime.fromisoformat(min_ts)
        max_dt = datetime.fromisoformat(max_ts)
        age = datetime.now() - min_dt
        print(f"   Возраст самой старой: {age.days} дней {age.seconds//3600} часов")
    
    conn.close()
    return unsynced

def analyze_logs(log_path):
    """Анализ логов"""
    print_header("📋 АНАЛИЗ ЛОГОВ")
    
    if not Path(log_path).exists():
        print(f"❌ Лог файл не найден: {log_path}")
        print(f"   Ожидаемый путь: {log_path}")
        print(f"   Проверьте: C:\\Users\\<user>\\AppData\\Roaming\\WorkTimeTracker\\logs\\wtt-user.log")
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"✅ Найдено строк: {len(lines)}")
    
    # Статистика по ключевым событиям
    print_section("Ключевые события")
    
    patterns = {
        'Запуск приложения': r'Logging initialized',
        'Запуск SyncManager': r'Сервис синхронизации запущен',
        'Циклы синхронизации': r'=== ЗАПУСК ЦИКЛА',
        'Начало цикла': r'=== НАЧАЛО ЦИКЛА СИНХРОНИЗАЦИИ',
        'Проверка интернета': r'Доступность интернета:',
        'Интернет вернулся': r'ИНТЕРНЕТ ВЕРНУЛСЯ',
        'Немедленная синхронизация': r'НЕМЕДЛЕННАЯ синхронизация',
        'Интервал изменился': r'Интервал изменился',
        'Offline режим': r'Нет интернета',
        'Синхронизация пакета': r'Начало синхронизации пакета',
        'Отправка действий': r'📤 Отправка.*действий',
        'Успешная отправка': r'✅ Результат отправки.*True',
    }
    
    stats = {name: 0 for name in patterns.keys()}
    
    for line in lines:
        for name, pattern in patterns.items():
            if re.search(pattern, line):
                stats[name] += 1
    
    for name, count in stats.items():
        print(f"   {name}: {count}")
    
    # Анализ циклов
    if stats['Циклы синхронизации'] > 0:
        print_section(f"Детали циклов синхронизации (найдено {stats['Циклы синхронизации']})")
        
        cycle_times = []
        cycle_intervals = []
        prev_time = None
        
        for line in lines:
            if '=== ЗАПУСК ЦИКЛА' in line:
                # Извлекаем время
                match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    time_str = match.group(1)
                    curr_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    cycle_times.append(curr_time)
                    
                    if prev_time:
                        interval = (curr_time - prev_time).total_seconds()
                        cycle_intervals.append(interval)
                    
                    prev_time = curr_time
        
        if cycle_times:
            print(f"   Первый цикл: {cycle_times[0]}")
            print(f"   Последний цикл: {cycle_times[-1]}")
            
            if cycle_intervals:
                avg_interval = sum(cycle_intervals) / len(cycle_intervals)
                print(f"   Средний интервал: {avg_interval:.1f} сек")
                print(f"   Мин интервал: {min(cycle_intervals):.1f} сек")
                print(f"   Макс интервал: {max(cycle_intervals):.1f} сек")
    
    # Анализ проверок интернета
    print_section("Проверки интернета")
    
    internet_checks = {'True': 0, 'False': 0}
    
    for line in lines:
        if 'Доступность интернета:' in line:
            if 'True' in line:
                internet_checks['True'] += 1
            else:
                internet_checks['False'] += 1
    
    total_checks = sum(internet_checks.values())
    if total_checks > 0:
        print(f"   Всего проверок: {total_checks}")
        print(f"   Online: {internet_checks['True']} ({internet_checks['True']/total_checks*100:.1f}%)")
        print(f"   Offline: {internet_checks['False']} ({internet_checks['False']/total_checks*100:.1f}%)")
    
    # Производительность синхронизации
    print_section("Производительность синхронизации")
    
    sync_batches = []
    
    for line in lines:
        match = re.search(r'Начало синхронизации пакета из (\d+) записей', line)
        if match:
            count = int(match.group(1))
            sync_batches.append(count)
    
    if sync_batches:
        print(f"   Пакетов отправлено: {len(sync_batches)}")
        print(f"   Всего записей: {sum(sync_batches)}")
        print(f"   Средний размер пакета: {sum(sync_batches)/len(sync_batches):.1f}")
        print(f"   Мин/Макс: {min(sync_batches)}/{max(sync_batches)}")
    
    # Ошибки
    print_section("Ошибки и предупреждения")
    
    error_types = defaultdict(int)
    
    for line in lines:
        if ' - ERROR - ' in line or ' - WARNING - ' in line:
            # Извлекаем тип ошибки
            match = re.search(r'(ERROR|WARNING) - (.+?)(?:\r?\n|$)', line)
            if match:
                error_type = match.group(2)[:80]  # Первые 80 символов
                error_types[error_type] += 1
    
    if error_types:
        for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   [{count}x] {error}")
    else:
        print("   ✅ Ошибок не найдено")

def analyze_offline_workflow():
    """Анализ offline workflow"""
    print_header("🔄 АНАЛИЗ OFFLINE WORKFLOW")
    
    print("""
Ожидаемое поведение:
1. ❌ Интернет пропадает
   → GUI показывает "Оффлайн режим"
   → Записи сохраняются локально
   → Фоновый цикл проверяет интернет каждые 5 сек
   
2. 💼 Пользователь работает
   → Меняет статусы
   → Оставляет комментарии
   → Начинает/завершает смену
   → ВСЕ работает локально
   
3. ✅ Интернет возвращается
   → Фоновый цикл детектирует (в течение 5 сек)
   → Логи: "🌐 ИНТЕРНЕТ ВЕРНУЛСЯ!"
   → Логи: "⚡ НЕМЕДЛЕННАЯ синхронизация X записей"
   → Интервал меняется на 1 сек
   → Логи: "⚡ Интервал изменился, прерываем ожидание"
   → Синхронизация начинается НЕМЕДЛЕННО
   
4. 🔄 Синхронизация
   → Отправляет пакетами по 50 записей
   → Интервал 2 сек между пакетами
   → Когда очередь < 10 → возврат к нормальному интервалу
    """)

def provide_recommendations(unsynced_count):
    """Рекомендации по исправлению"""
    print_header("💡 РЕКОМЕНДАЦИИ")
    
    if unsynced_count is None:
        print("❌ Не удалось проанализировать базу данных")
        return
    
    if unsynced_count == 0:
        print("✅ Все записи синхронизированы!")
        print("   Система работает корректно")
    elif unsynced_count < 50:
        print(f"⚠️  {unsynced_count} несинхронизированных записей")
        print("   Это нормально если недавно были offline")
        print("   Должны синхронизироваться в течение 1-2 минут")
    elif unsynced_count < 500:
        print(f"⚠️  {unsynced_count} несинхронизированных записей")
        print("   Возможные причины:")
        print("   1. Долгий период offline")
        print("   2. Большое количество пользователей")
        print("   3. Медленная синхронизация")
        print()
        print("   Рекомендации:")
        print("   - Дождаться завершения синхронизации (~10-30 мин)")
        print("   - Проверить логи на ошибки")
        print("   - Убедиться что интернет стабилен")
    else:
        print(f"❌ {unsynced_count} несинхронизированных записей!")
        print("   Критическая ситуация!")
        print()
        print("   Возможные причины:")
        print("   1. Фоновая синхронизация НЕ работает")
        print("   2. Постоянные ошибки при синхронизации")
        print("   3. Очень медленное подключение")
        print()
        print("   Срочные действия:")
        print("   - Проверить логи на повторяющиеся ошибки")
        print("   - Убедиться что фоновый цикл запускается")
        print("   - Проверить что интернет стабилен")
        print("   - Возможно нужно ручная синхронизация")

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   ДИАГНОСТИКА СИНХРОНИЗАЦИИ WorkTimeTracker                   ║
║                                                                                ║
║  Этот скрипт анализирует:                                                      ║
║  - Очередь несинхронизированных записей                                       ║
║  - Работу фоновых циклов синхронизации                                        ║
║  - Детекцию возвращения интернета                                             ║
║  - Производительность синхронизации                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Определяем пути
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "local_backup.db"
        # Также попробуем найти в стандартных местах
        possible_paths = [
            Path("local_backup.db"),
            Path("D:/proj vs code/WorkTimeTracker/local_backup.db"),
            Path("../local_backup.db"),
        ]
        
        for path in possible_paths:
            if path.exists():
                db_path = str(path)
                break
    
    if len(sys.argv) > 2:
        log_path = sys.argv[2]
    else:
        from pathlib import Path
        import os
        
        # Стандартный путь
        appdata = os.getenv('APPDATA')
        if appdata:
            log_path = Path(appdata) / "WorkTimeTracker" / "logs" / "wtt-user.log"
        else:
            log_path = Path("wtt-user.log")
    
    print(f"📁 База данных: {db_path}")
    print(f"📋 Лог файл: {log_path}")
    
    # Анализ
    unsynced = analyze_database(db_path)
    analyze_logs(log_path)
    analyze_offline_workflow()
    provide_recommendations(unsynced)
    
    print_header("✅ ДИАГНОСТИКА ЗАВЕРШЕНА")
    print()
    print("Для запуска с custom путями:")
    print(f"  python {sys.argv[0]} <путь_к_БД> <путь_к_логу>")
    print()

if __name__ == "__main__":
    main()
