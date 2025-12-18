#!/bin/bash
# Скрипт для ежедневной архивации данных
# Добавьте в crontab: 0 2 * * * /path/to/scripts/archive_daily.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/archive_$(date +%Y%m%d).log"

cd "$PROJECT_DIR" || exit 1

# Создаем директорию для логов если её нет
mkdir -p "$(dirname "$LOG_FILE")"

# Запускаем архивацию
python3 "$PROJECT_DIR/run_archive.py" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date): Archive completed successfully" >> "$LOG_FILE"
else
    echo "$(date): Archive failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

exit $EXIT_CODE
