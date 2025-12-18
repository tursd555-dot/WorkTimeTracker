"""
Тест настройки Keep-Alive для Supabase
======================================

Проверяет что все файлы созданы и настроены правильно
"""

import os
import sys

def check_file_exists(filepath, description):
    """Проверить существование файла"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} - НЕ НАЙДЕН!")
        return False

def check_file_executable(filepath, description):
    """Проверить что файл исполняемый"""
    if os.path.exists(filepath) and os.access(filepath, os.X_OK):
        print(f"✅ {description}: {filepath} - исполняемый")
        return True
    elif os.path.exists(filepath):
        print(f"⚠️  {description}: {filepath} - НЕ исполняемый (chmod +x)")
        return True
    else:
        print(f"❌ {description}: {filepath} - НЕ НАЙДЕН!")
        return False

def check_env_example():
    """Проверить .env.example"""
    filepath = ".env.example"
    if not os.path.exists(filepath):
        print(f"❌ .env.example не найден!")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'SUPABASE_URL' in content and 'SUPABASE_KEY' in content:
        print(f"✅ .env.example содержит настройки Supabase")
        return True
    else:
        print(f"❌ .env.example НЕ содержит настройки Supabase!")
        return False

def main():
    """Главная функция"""
    print("=" * 70)
    print("🔍 ПРОВЕРКА НАСТРОЙКИ SUPABASE KEEP-ALIVE")
    print("=" * 70)
    print()

    results = []

    # Проверка основного скрипта
    print("📄 Основной скрипт:")
    results.append(check_file_exists("supabase_keepalive.py", "Python скрипт"))
    print()

    # Проверка батников
    print("🪟 Windows скрипты:")
    results.append(check_file_exists("run_keepalive.bat", "Windows батник"))
    print()

    # Проверка shell скрипта
    print("🐧 Linux/Mac скрипты:")
    results.append(check_file_executable("run_keepalive.sh", "Shell скрипт"))
    print()

    # Проверка GitHub Actions
    print("🚀 GitHub Actions:")
    results.append(check_file_exists(".github/workflows/supabase-keepalive.yml", "Workflow файл"))
    print()

    # Проверка документации
    print("📚 Документация:")
    results.append(check_file_exists("SUPABASE_KEEPALIVE_GUIDE.md", "Руководство"))
    print()

    # Проверка .env.example
    print("⚙️  Конфигурация:")
    results.append(check_env_example())
    print()

    # Итого
    print("=" * 70)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ: {passed}/{total}")
        print()
        print("📋 СЛЕДУЮЩИЕ ШАГИ:")
        print("   1. Установите библиотеку: pip install supabase")
        print("   2. Настройте .env файл с SUPABASE_URL и SUPABASE_KEY")
        print("   3. Протестируйте: python supabase_keepalive.py")
        print("   4. Настройте автоматизацию (см. SUPABASE_KEEPALIVE_GUIDE.md)")
        print()
        return 0
    else:
        print(f"⚠️  НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ: {passed}/{total}")
        print()
        print("❌ Некоторые файлы отсутствуют или настроены неправильно!")
        print("   Проверьте вывод выше для деталей.")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())
