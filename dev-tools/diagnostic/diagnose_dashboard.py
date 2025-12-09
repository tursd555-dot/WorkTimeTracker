#!/usr/bin/env python3
# coding: utf-8
"""
Диагностика Dashboard - почему "0 человек"?
"""
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_adapter import get_sheets_api
from admin_app.break_manager import BreakManager

print("=" * 80)
print("ДИАГНОСТИКА DASHBOARD")
print("=" * 80)
print()

# Инициализация
sheets = get_sheets_api()
break_mgr = BreakManager(sheets)

# Получаем нарушения за сегодня
today = date.today().isoformat()
print(f"Дата: {today}")
print()

violations = break_mgr.get_violations_report(
    date_from=today,
    date_to=today
)

print(f"Всего нарушений за сегодня: {len(violations)}")
print()

if violations:
    print("АНАЛИЗ НАРУШЕНИЙ:")
    print("-" * 80)
    
    # Группируем по типам
    by_type = {}
    for v in violations:
        vtype = v.get('ViolationType', 'Unknown')
        by_type[vtype] = by_type.get(vtype, 0) + 1
    
    print("По типам:")
    for vtype, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  {vtype}: {count}")
    
    print()
    print("-" * 80)
    
    # Проверяем CRITICAL нарушения
    print("CRITICAL НАРУШЕНИЯ (для Dashboard):")
    print("-" * 80)
    
    critical_violations = [v for v in violations 
                          if v.get('ViolationType') in ['OVER_LIMIT', 'QUOTA_EXCEEDED']]
    
    print(f"Найдено CRITICAL: {len(critical_violations)}")
    print()
    
    if critical_violations:
        print("Примеры:")
        for v in critical_violations[:5]:
            print(f"  - {v.get('Timestamp')}: {v.get('Email')} | {v.get('ViolationType')}")
        
        print()
        print("Уникальные email:")
        over_limit_emails = set(v.get('Email') for v in critical_violations if v.get('Email'))
        for email in over_limit_emails:
            count = len([v for v in critical_violations if v.get('Email') == email])
            print(f"  - {email}: {count} нарушений")
        
        print()
        print(f"Итого уникальных пользователей с CRITICAL: {len(over_limit_emails)}")
        print()
        print("=" * 80)
        print(f"DASHBOARD ДОЛЖЕН ПОКАЗАТЬ: {len(over_limit_emails)} человек")
        print("=" * 80)
    else:
        print("❌ Нет нарушений типа OVER_LIMIT или QUOTA_EXCEEDED")
        print()
        print("Возможные причины:")
        print("  1. Все нарушения имеют другой тип")
        print("  2. Поле ViolationType заполнено неправильно")
        print()
        print("Проверим первые 5 нарушений:")
        for v in violations[:5]:
            print(f"  ViolationType: '{v.get('ViolationType')}'")
            print(f"  Severity: '{v.get('Severity')}'")
            print(f"  Details: '{v.get('Details')}'")
            print()

else:
    print("❌ Нет нарушений за сегодня")

print()
print("=" * 80)
print("ВЫВОД:")
print("=" * 80)
print()
print("Если видишь 'DASHBOARD ДОЛЖЕН ПОКАЗАТЬ: X человек'")
print("но Dashboard показывает 0, значит:")
print()
print("1. Dashboard не обновился (подожди 30 сек)")
print("2. Или метод refresh_dashboard() не вызывается")
print("3. Или есть ошибка в логах (проверь logs/wtt-admin.log)")
print()