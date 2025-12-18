#!/bin/bash
# Скрипт для диагностики и исправления незавершенного merge

echo "=========================================="
echo "Диагностика незавершенного merge"
echo "=========================================="
echo ""

# Проверка статуса
echo "1. Статус репозитория:"
git status
echo ""

# Проверка MERGE_HEAD
if [ -f .git/MERGE_HEAD ]; then
    echo "2. MERGE_HEAD найден:"
    cat .git/MERGE_HEAD
    echo ""
    echo "3. Варианты решения:"
    echo "   a) Отменить merge: git merge --abort"
    echo "   b) Завершить merge: git commit (если нет конфликтов)"
    echo "   c) Разрешить конфликты и закоммитить: git add . && git commit"
else
    echo "2. MERGE_HEAD не найден - merge не активен"
fi

echo ""
echo "=========================================="
