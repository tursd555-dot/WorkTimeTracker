#!/bin/bash
# Stage 2: Remove duplicates and optimize structure

echo "=== WorkTimeTracker Cleanup Stage 2 ==="
echo ""

# === STEP 1: Безопасное удаление sync_queue.py ===
echo "🗑️  Step 1: Removing old sync_queue.py..."
if [ -f "sync/sync_queue.py" ]; then
    # Создаем бэкап на всякий случай
    mv sync/sync_queue.py dev-tools/diagnostic/sync_queue.py.removed
    echo "  ✓ Moved sync/sync_queue.py to dev-tools (removed from production)"
else
    echo "  ℹ️  sync/sync_queue.py already removed"
fi

# === STEP 2: Переместить config_secure.py в dev-tools ===
echo "📦 Step 2: Moving config_secure.py to dev-tools..."
if [ -f "config_secure.py" ]; then
    mv config_secure.py dev-tools/config_secure.py.reference
    echo "  ✓ Moved config_secure.py to dev-tools (reference copy)"
    echo "     Note: config.py содержит все необходимые функции"
else
    echo "  ℹ️  config_secure.py already moved"
fi

# === STEP 3: Проверка db_migrations ===
echo "🔍 Step 3: Analyzing db_migrations files..."
echo "  Found:"
echo "    - db_migrations_improved.py (root) - 758 lines"
echo "    - user_app/db_migrations.py - checking..."
wc -l user_app/db_migrations.py 2>/dev/null || echo "    (не найден)"

# === STEP 4: Cleanup analyze script ===
echo "📦 Step 4: Moving analysis script..."
mv analyze_duplicates.py dev-tools/analyze_duplicates.py 2>/dev/null

echo ""
echo "✅ Cleanup Stage 2 completed!"
echo ""

# Подсчет файлов
echo "📊 Final count:"
find . -name "*.py" -type f ! -path "./dev-tools/*" ! -path "./tools/*" | wc -l | xargs echo "  - Production Python files:"
du -sh . | awk '{print "  - Total size: " $1}'
