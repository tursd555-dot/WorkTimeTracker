#!/usr/bin/env python3
# coding: utf-8
"""
Проверка метода refresh_dashboard в break_analytics_tab.py
"""
from pathlib import Path

file_path = Path("admin_app/break_analytics_tab.py")

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Ищем метод refresh_dashboard
start = content.find("def refresh_dashboard(self):")
if start == -1:
    print("❌ Метод refresh_dashboard не найден!")
    exit(1)

# Ищем конец метода (следующий def или конец файла)
end = content.find("\n    def ", start + 1)
if end == -1:
    end = len(content)

method_code = content[start:end]

print("=" * 80)
print("МЕТОД refresh_dashboard():")
print("=" * 80)
print(method_code)
print("=" * 80)
print()

# Проверяем наличие исправления
if "critical_violations" in method_code:
    print("✅ Исправление ПРИМЕНЕНО!")
    print("   Метод использует critical_violations для подсчёта")
elif "over_limit = [b for b in active_breaks" in method_code:
    print("❌ Исправление НЕ ПРИМЕНЕНО!")
    print("   Метод всё ещё использует старую логику")
    print()
    print("ТРЕБУЕТСЯ РУЧНОЕ ИСПРАВЛЕНИЕ:")
    print()
    print("Найди в файле admin_app/break_analytics_tab.py строки:")
    print()
    print("    over_limit = [b for b in active_breaks if b.get('is_over_limit', False)]")
    print("    self.dashboard_over_limit_label.setText(f\"{len(over_limit)} человек\")")
    print()
    print("Замени на:")
    print()
    print("    critical_violations = [v for v in violations")
    print("                          if v.get('ViolationType') in ['OVER_LIMIT', 'QUOTA_EXCEEDED']]")
    print("    over_limit_emails = set(v.get('Email') for v in critical_violations if v.get('Email'))")
    print("    self.dashboard_over_limit_label.setText(f\"{len(over_limit_emails)} человек\")")
else:
    print("⚠️ Неизвестное состояние метода")