#!/usr/bin/env python3
"""
Анализ дублирующихся модулей в WorkTimeTracker
Этап 1.2
"""

import os
from pathlib import Path

def analyze_duplicates():
    """Анализирует дублирующиеся модули и их использование"""
    
    print("="*70)
    print("Анализ дублирующихся модулей - Этап 1.2")
    print("="*70)
    print()
    
    results = {
        'can_remove': [],
        'need_merge': [],
        'need_analysis': []
    }
    
    # === 1. config.py vs config_secure.py ===
    print("📋 1. Анализ: config.py vs config_secure.py")
    print("-" * 60)
    
    config_imports = []
    config_secure_imports = []
    
    for root, dirs, files in os.walk('.'):
        # Игнорируем dev-tools
        if 'dev-tools' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'from config import' in content or 'import config' in content:
                            if filepath not in config_imports:
                                config_imports.append(filepath)
                        if 'from config_secure import' in content or 'import config_secure' in content:
                            if filepath not in config_secure_imports:
                                config_secure_imports.append(filepath)
                except Exception as e:
                    pass
    
    print(f"  config.py используется в: {len(config_imports)} файлах")
    for f in config_imports[:5]:
        print(f"    - {f}")
    if len(config_imports) > 5:
        print(f"    ... и еще {len(config_imports) - 5}")
    
    print()
    print(f"  config_secure.py используется в: {len(config_secure_imports)} файлах")
    for f in config_secure_imports[:5]:
        print(f"    - {f}")
    
    print()
    
    if len(config_secure_imports) == 0 or (len(config_secure_imports) == 1 and 'config_secure.py' in config_secure_imports[0]):
        print("  ✅ РЕШЕНИЕ: config_secure.py не используется (кроме себя)")
        print("     → Можно безопасно удалить или переместить в dev-tools/")
        results['can_remove'].append('config_secure.py')
    else:
        print("  ⚠️  РЕШЕНИЕ: config_secure.py используется")
        print("     → Нужно объединить с config.py или оставить оба")
        results['need_merge'].append(('config.py', 'config_secure.py'))
    
    print()
    print()
    
    # === 2. sync_queue.py vs sync_queue_improved.py ===
    print("📋 2. Анализ: sync/sync_queue.py vs sync/sync_queue_improved.py")
    print("-" * 60)
    
    sync_queue_imports = []
    sync_queue_improved_imports = []
    
    for root, dirs, files in os.walk('.'):
        if 'dev-tools' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'from sync.sync_queue import' in content or 'from sync import sync_queue' in content:
                            if filepath not in sync_queue_imports:
                                sync_queue_imports.append(filepath)
                        if 'sync_queue_improved' in content:
                            if filepath not in sync_queue_improved_imports:
                                sync_queue_improved_imports.append(filepath)
                except Exception as e:
                    pass
    
    print(f"  sync_queue.py используется в: {len(sync_queue_imports)} файлах")
    for f in sync_queue_imports[:5]:
        print(f"    - {f}")
    
    print()
    print(f"  sync_queue_improved.py используется в: {len(sync_queue_improved_imports)} файлах")
    for f in sync_queue_improved_imports[:5]:
        print(f"    - {f}")
    
    print()
    
    # Читаем размеры
    sq_size = Path('sync/sync_queue.py').stat().st_size // 1024
    sqi_size = Path('sync/sync_queue_improved.py').stat().st_size // 1024
    
    print(f"  Размер sync_queue.py: {sq_size} KB")
    print(f"  Размер sync_queue_improved.py: {sqi_size} KB (в 2.25 раза больше)")
    print()
    print(f"  sync_queue_improved.py содержит:")
    print(f"    - Exponential backoff с jitter")
    print(f"    - Batch операции (для 200 пользователей критично!)")
    print(f"    - Приоритеты синхронизации")
    print(f"    - Conflict resolution")
    print(f"    - Детальная телеметрия")
    print()
    
    if len(sync_queue_imports) == 0 and len(sync_queue_improved_imports) == 0:
        print("  ✅ РЕШЕНИЕ: Ни один модуль не используется напрямую")
        print("     → Оставить sync_queue_improved.py (более продвинутый)")
        print("     → Удалить sync_queue.py")
        results['can_remove'].append('sync/sync_queue.py')
    elif len(sync_queue_improved_imports) > 0:
        print("  ✅ РЕШЕНИЕ: sync_queue_improved.py активно используется")
        print("     → Удалить старый sync_queue.py")
        results['can_remove'].append('sync/sync_queue.py')
    else:
        print("  ⚠️  РЕШЕНИЕ: Используется старый sync_queue.py")
        print("     → Нужно мигрировать на improved версию")
        results['need_analysis'].append('sync/sync_queue.py')
    
    print()
    print()
    
    # === 3. Другие потенциальные дубликаты ===
    print("📋 3. Поиск других дубликатов...")
    print("-" * 60)
    
    # Ищем похожие имена файлов
    all_py_files = []
    for root, dirs, files in os.walk('.'):
        if 'dev-tools' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py') and not file.startswith('test_'):
                all_py_files.append((root, file))
    
    # Группируем по похожим именам
    base_names = {}
    for root, file in all_py_files:
        base = file.replace('_improved', '').replace('_v2', '').replace('_new', '')
        if base not in base_names:
            base_names[base] = []
        base_names[base].append(os.path.join(root, file))
    
    duplicates_found = []
    for base, files in base_names.items():
        if len(files) > 1:
            duplicates_found.append((base, files))
    
    if duplicates_found:
        for base, files in duplicates_found:
            print(f"  ⚠️  Найдены похожие файлы ({base}):")
            for f in files:
                print(f"     - {f}")
            print()
    else:
        print("  ✅ Других дубликатов не найдено")
    
    print()
    print()
    
    # === Итоговый отчет ===
    print("="*70)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("="*70)
    print()
    
    print("✅ Можно безопасно удалить:")
    if results['can_remove']:
        for item in results['can_remove']:
            print(f"   - {item}")
    else:
        print("   (нет)")
    print()
    
    print("⚠️  Требуется объединение:")
    if results['need_merge']:
        for pair in results['need_merge']:
            print(f"   - {pair[0]} + {pair[1]}")
    else:
        print("   (нет)")
    print()
    
    print("🔍 Требуется дополнительный анализ:")
    if results['need_analysis']:
        for item in results['need_analysis']:
            print(f"   - {item}")
    else:
        print("   (нет)")
    print()
    
    return results

if __name__ == '__main__':
    os.chdir('/home/claude/WorkTimeTracker')
    analyze_duplicates()
