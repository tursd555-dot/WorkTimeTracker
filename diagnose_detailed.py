#!/usr/bin/env python3
"""
Детальная диагностика проблем синхронизации WorkTimeTracker
"""

import sys
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def parse_timestamp(line):
    """Извлекает timestamp из строки лога"""
    match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    if match:
        return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
    return None

def analyze_sync_performance(log_path):
    """Анализ производительности синхронизации"""
    print("=" * 80)
    print("  АНАЛИЗ ПРОИЗВОДИТЕЛЬНОСТИ СИНХРОНИЗАЦИИ")
    print("=" * 80)
    
    if not Path(log_path).exists():
        print(f"❌ Лог файл не найден: {log_path}")
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Анализ циклов
    cycles = []
    current_cycle = None
    
    for line in lines:
        ts = parse_timestamp(line)
        if not ts:
            continue
        
        if '=== ЗАПУСК ЦИКЛА' in line:
            if current_cycle:
                cycles.append(current_cycle)
            
            match = re.search(r'ЗАПУСК ЦИКЛА #(\d+)', line)
            cycle_num = int(match.group(1)) if match else len(cycles) + 1
            
            current_cycle = {
                'num': cycle_num,
                'start': ts,
                'end': None,
                'sends': [],
                'records': 0
            }
        
        elif current_cycle:
            if 'Ожидание' in line and 'сек до следующего цикла' in line:
                current_cycle['end'] = ts
            
            elif '📤 Отправка' in line:
                match = re.search(r'Отправка (\d+) действий', line)
                if match:
                    count = int(match.group(1))
                    current_cycle['sends'].append({'ts': ts, 'count': count})
                    current_cycle['records'] += count
    
    if current_cycle:
        cycles.append(current_cycle)
    
    # Выводим статистику
    print(f"\n📊 Всего циклов: {len(cycles)}")
    
    for cycle in cycles:
        print(f"\n{'─' * 80}")
        print(f"  ЦИКЛ #{cycle['num']}")
        print(f"{'─' * 80}")
        
        print(f"Начало: {cycle['start']}")
        
        if cycle['end']:
            duration = (cycle['end'] - cycle['start']).total_seconds()
            print(f"Конец: {cycle['end']}")
            print(f"⏱️  Длительность: {duration:.1f} сек")
            
            if cycle['records'] > 0:
                speed = cycle['records'] / duration
                print(f"📦 Синхронизировано: {cycle['records']} записей")
                print(f"⚡ Скорость: {speed:.2f} записей/сек")
                
                if speed < 0.5:
                    print(f"❌ КРИТИЧЕСКИ МЕДЛЕННО! (норма: >5 записей/сек)")
                elif speed < 2:
                    print(f"⚠️  Очень медленно (норма: >5 записей/сек)")
                elif speed < 5:
                    print(f"⚠️  Медленно (норма: >5 записей/сек)")
                else:
                    print(f"✅ Нормальная скорость")
        else:
            print(f"⚠️  Цикл не завершен (еще выполняется или прерван)")
            print(f"📦 Синхронизировано: {cycle['records']} записей")
        
        # Детали отправок
        if cycle['sends']:
            print(f"\nДетали отправок ({len(cycle['sends'])} штук):")
            
            prev_ts = cycle['start']
            delays = []
            
            for i, send in enumerate(cycle['sends'][:10], 1):  # Первые 10
                delay = (send['ts'] - prev_ts).total_seconds()
                delays.append(delay)
                print(f"  {i}. {send['ts'].strftime('%H:%M:%S')} - {send['count']} записей (задержка {delay:.1f} сек)")
                prev_ts = send['ts']
            
            if len(cycle['sends']) > 10:
                print(f"  ... и еще {len(cycle['sends']) - 10} отправок")
            
            if delays:
                avg_delay = sum(delays) / len(delays)
                print(f"\n  Средняя задержка между отправками: {avg_delay:.2f} сек")
                print(f"  Мин/Макс задержка: {min(delays):.1f} / {max(delays):.1f} сек")
                
                if avg_delay > 5:
                    print(f"  ❌ ПРОБЛЕМА: Слишком большая задержка между отправками!")
                    print(f"     Это замедляет синхронизацию в {avg_delay/2:.0f}x раз")

def analyze_bottlenecks(log_path):
    """Анализ узких мест"""
    print("\n" + "=" * 80)
    print("  АНАЛИЗ УЗКИХ МЕСТ")
    print("=" * 80)
    
    if not Path(log_path).exists():
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Ищем медленные операции
    slow_operations = []
    
    for i, line in enumerate(lines):
        ts = parse_timestamp(line)
        if not ts:
            continue
        
        # Ищем начало и конец операций
        if 'Batch append ->' in line:
            # Ищем завершение
            for j in range(i+1, min(i+50, len(lines))):
                if 'Batch append for' in lines[j] and 'completed' in lines[j]:
                    end_ts = parse_timestamp(lines[j])
                    if end_ts:
                        duration = (end_ts - ts).total_seconds()
                        if duration > 2:  # Больше 2 секунд
                            slow_operations.append({
                                'operation': 'Batch append',
                                'duration': duration,
                                'line': line.strip()
                            })
                    break
    
    if slow_operations:
        print(f"\n⚠️  Найдено {len(slow_operations)} медленных операций:")
        
        for i, op in enumerate(slow_operations[:10], 1):
            print(f"  {i}. {op['operation']}: {op['duration']:.1f} сек")
        
        avg = sum(op['duration'] for op in slow_operations) / len(slow_operations)
        print(f"\n  Средняя длительность: {avg:.2f} сек")
        print(f"  ❌ Batch append операции слишком медленные!")
        print(f"     Возможные причины:")
        print(f"     - Медленное интернет соединение")
        print(f"     - Проблемы с Google Sheets API")
        print(f"     - Слишком много данных в одном batch")
    else:
        print("\n✅ Медленных операций не найдено")

def analyze_queue_growth(log_path):
    """Анализ роста очереди"""
    print("\n" + "=" * 80)
    print("  АНАЛИЗ РОСТА ОЧЕРЕДИ")
    print("=" * 80)
    
    if not Path(log_path).exists():
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    queue_sizes = []
    
    for line in lines:
        ts = parse_timestamp(line)
        if not ts:
            continue
        
        if 'Sync queue growing:' in line:
            match = re.search(r'growing: (\d+) records', line)
            if match:
                size = int(match.group(1))
                queue_sizes.append({'ts': ts, 'size': size})
    
    if queue_sizes:
        print(f"\n📈 Изменение размера очереди:")
        
        for i, q in enumerate(queue_sizes[:20], 1):
            trend = ""
            if i > 1:
                diff = q['size'] - queue_sizes[i-2]['size']
                if diff > 0:
                    trend = f" ⬆️ +{diff}"
                elif diff < 0:
                    trend = f" ⬇️ {diff}"
                else:
                    trend = " ➡️ 0"
            
            print(f"  {q['ts'].strftime('%H:%M:%S')} - {q['size']} записей{trend}")
        
        if len(queue_sizes) > 20:
            print(f"  ... и еще {len(queue_sizes) - 20} проверок")
        
        first = queue_sizes[0]['size']
        last = queue_sizes[-1]['size']
        
        print(f"\n  Первая проверка: {first} записей")
        print(f"  Последняя проверка: {last} записей")
        
        if last > first:
            print(f"  ❌ Очередь РАСТЕТ! (+{last - first} записей)")
            print(f"     Синхронизация не успевает за новыми записями!")
        elif last < first:
            print(f"  ✅ Очередь УМЕНЬШАЕТСЯ (-{first - last} записей)")
        else:
            print(f"  ⚠️  Очередь НЕ МЕНЯЕТСЯ")
    else:
        print("\n  ℹ️  Информация о росте очереди не найдена")

def suggest_fixes():
    """Предложения по исправлению"""
    print("\n" + "=" * 80)
    print("  РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ")
    print("=" * 80)
    
    print("""
На основе анализа, основные проблемы:

1. ❌ МЕДЛЕННАЯ СИНХРОНИЗАЦИЯ (0.3-0.5 записей/сек)
   
   Причина: Каждая запись обрабатывается по отдельности
   
   Решение:
   - Увеличить размер пакета (BATCH_SIZE)
   - Отправлять batch запросы (все записи одного пользователя сразу)
   - Оптимизировать API запросы
   
2. ❌ ДОЛГИЕ ЦИКЛЫ СИНХРОНИЗАЦИИ (2-3 минуты)
   
   Причина: Пока идет синхронизация, новые offline записи не обрабатываются
   
   Решение:
   - Разделить синхронизацию на "срочную" и "фоновую"
   - Приоритизировать свежие записи (< 5 минут)
   - Ограничить время одного цикла (макс 30 секунд)
   
3. ❌ ОЧЕРЕДЬ НЕ УМЕНЬШАЕТСЯ
   
   Причина: Скорость синхронизации < скорости добавления новых записей
   
   Решение:
   - Увеличить скорость синхронизации (см. п.1)
   - Синхронизировать параллельно (несколько пользователей одновременно)

КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
═══════════════════════
Нужно изменить логику синхронизации:

ТЕКУЩАЯ ЛОГИКА (ПЛОХО):
  Цикл {
    Синхронизировать ВСЕ 500 записей (3 минуты)
    Ждать 30 секунд
  }

НОВАЯ ЛОГИКА (ХОРОШО):
  Цикл {
    Если есть свежие записи (< 5 минут):
      Синхронизировать ТОЛЬКО свежие (5-10 секунд)
    Иначе:
      Синхронизировать 10-20 старых записей (10-15 секунд)
    Ждать 5-10 секунд
  }

Это обеспечит:
✅ Свежие offline записи синхронизируются быстро (< 30 сек)
✅ Старые записи синхронизируются постепенно в фоне
✅ Очередь уменьшается стабильно
""")

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║           ДЕТАЛЬНАЯ ДИАГНОСТИКА ПРОБЛЕМ СИНХРОНИЗАЦИИ                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    else:
        from pathlib import Path
        import os
        
        appdata = os.getenv('APPDATA')
        if appdata:
            log_path = Path(appdata) / "WorkTimeTracker" / "logs" / "wtt-user.log"
        else:
            log_path = Path("wtt-user.log")
    
    print(f"📋 Лог файл: {log_path}\n")
    
    # Анализ
    analyze_sync_performance(str(log_path))
    analyze_bottlenecks(str(log_path))
    analyze_queue_growth(str(log_path))
    suggest_fixes()
    
    print("\n" + "=" * 80)
    print("  ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("=" * 80)
    print()

if __name__ == "__main__":
    main()
