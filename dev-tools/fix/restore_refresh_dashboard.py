#!/usr/bin/env python3
# coding: utf-8
"""
Восстановление правильной структуры refresh_dashboard
"""
from pathlib import Path
import shutil
from datetime import datetime

file_path = Path("admin_app/break_analytics_tab.py")

print("=" * 80)
print("ВОССТАНОВЛЕНИЕ refresh_dashboard()")
print("=" * 80)
print()

# Backup
backup_path = file_path.with_suffix(f'.py.bak.restore_{datetime.now().strftime("%H%M%S")}')
shutil.copy2(file_path, backup_path)
print(f"✓ Backup: {backup_path.name}")
print()

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Правильная реализация метода
correct_method = '''    def refresh_dashboard(self):
        """Обновляет Dashboard"""
        try:
            # Получаем активные перерывы
            active_breaks = self._get_active_breaks()
            self.dashboard_active_breaks_label.setText(f"{len(active_breaks)} человек")
            
            # Нарушений сегодня
            today = date.today().isoformat()
            violations = self.break_mgr.get_violations_report(
                date_from=today,
                date_to=today
            )
            self.dashboard_today_violations_label.setText(str(len(violations)))
            
            # Кто превышает лимит (CRITICAL нарушения)
            critical_violations = [v for v in violations
                                  if v.get('ViolationType') in ['OVER_LIMIT', 'QUOTA_EXCEEDED']]
            over_limit_emails = set(v.get('Email') for v in critical_violations if v.get('Email'))
            self.dashboard_over_limit_label.setText(f"{len(over_limit_emails)} человек")
            
            # Топ нарушитель
            top_violator = self._get_top_violator(violations)
            if top_violator:
                self.dashboard_top_violator_label.setText(
                    f"{top_violator['email']}\\n({top_violator['count']} нарушений)"
                )
            else:
                self.dashboard_top_violator_label.setText("Нет данных")
            
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")
    '''

# Ищем начало и конец метода
start_marker = "    def refresh_dashboard(self):"
end_marker = "    def apply_filters(self):"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("❌ Не найдены маркеры метода")
    print()
    print(f"start_marker найден: {start_idx != -1}")
    print(f"end_marker найден: {end_idx != -1}")
    exit(1)

# Заменяем метод
new_content = content[:start_idx] + correct_method + "\n    " + content[end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ МЕТОД ВОССТАНОВЛЕН!")
print()
print("Структура метода:")
print("  - def refresh_dashboard(self):")
print("  - try:")
print("  -   ... код ...")
print("  - except Exception as e:")
print("  -   logger.error(...)")
print()
print("Перезапустите админку:")
print("  python admin_app/main_admin.py")
print()