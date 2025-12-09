#!/bin/bash

################################################################################
# WorkTimeTracker - Cleanup Credentials from Git History
################################################################################
#
# Этот скрипт полностью удаляет чувствительные файлы из истории Git,
# включая все коммиты, ветки и теги.
#
# ⚠️  ВНИМАНИЕ: Это необратимая операция!
#
# Что делает скрипт:
# 1. Создает backup текущего состояния
# 2. Удаляет credentials из всей истории Git
# 3. Очищает рефлоги и освобождает место
# 4. Опционально: force push изменений
#
# Использование:
#   chmod +x scripts/cleanup_credentials.sh
#   ./scripts/cleanup_credentials.sh
#
# После выполнения:
#   git push origin --force --all
#   git push origin --force --tags
#
# Автор: WorkTimeTracker Security Team
# Дата: 2025-11-24
#
################################################################################

set -e  # Остановиться при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# ФУНКЦИИ
################################################################################

print_header() {
    echo ""
    echo "================================================================================"
    echo "  $1"
    echo "================================================================================"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_git_repo() {
    if [ ! -d .git ]; then
        print_error "Not a Git repository!"
        print_info "Run this script from the root of your Git repository."
        exit 1
    fi
}

check_dependencies() {
    print_info "Checking dependencies..."
    
    # Проверка git
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed!"
        exit 1
    fi
    
    print_success "All dependencies OK"
}

create_backup() {
    print_info "Creating backup..."
    
    BACKUP_DIR="git_backup_$(date +%Y%m%d_%H%M%S)"
    
    # Создать backup
    mkdir -p "$BACKUP_DIR"
    
    # Копировать .git директорию
    cp -r .git "$BACKUP_DIR/.git"
    
    # Создать bundle (полная копия репозитория)
    git bundle create "$BACKUP_DIR/repo_backup.bundle" --all
    
    print_success "Backup created: $BACKUP_DIR"
    print_info "To restore: git clone $BACKUP_DIR/repo_backup.bundle restored_repo"
}

list_sensitive_files() {
    print_info "Searching for sensitive files in Git history..."
    echo ""
    
    # Список паттернов чувствительных файлов
    local patterns=(
        "service_account.json"
        "credentials/"
        "secret_creds/"
        ".env"
        "*.db"
        "*.log"
        "*.pem"
        "*.key"
    )
    
    local found=0
    
    for pattern in "${patterns[@]}"; do
        echo "Searching for: $pattern"
        
        # Поиск в истории
        if git log --all --pretty=format: --name-only --diff-filter=A | grep -q "$pattern"; then
            print_warning "Found: $pattern"
            found=1
        fi
    done
    
    echo ""
    
    if [ $found -eq 0 ]; then
        print_success "No sensitive files found in Git history"
        return 0
    else
        return 1
    fi
}

remove_file_from_history() {
    local file_pattern=$1
    
    print_info "Removing: $file_pattern"
    
    # Использовать git filter-branch для удаления файла
    git filter-branch --force --index-filter \
        "git rm --cached --ignore-unmatch $file_pattern" \
        --prune-empty --tag-name-filter cat -- --all
    
    print_success "Removed: $file_pattern"
}

cleanup_all_credentials() {
    print_header "Removing Credentials from Git History"
    
    # Список файлов/директорий для удаления
    local files_to_remove=(
        "service_account.json"
        "credentials/service_account.json"
        "credentials/secret_creds/service_account.json"
        "secret_creds.zip"
        "credentials/*.zip"
        ".env"
        "local_backup.db"
        "*.log"
        "logs/*.log"
        "diagnostics*.log"
        "diagnostics*.json"
        "*.pem"
        "*.key"
        "*.ppk"
    )
    
    for file in "${files_to_remove[@]}"; do
        remove_file_from_history "$file"
    done
    
    print_success "All credentials removed from history"
}

cleanup_git() {
    print_header "Cleaning Up Git Repository"
    
    print_info "Removing refs/original..."
    git for-each-ref --format="delete %(refname)" refs/original | git update-ref --stdin
    
    print_info "Expiring reflog..."
    git reflog expire --expire=now --all
    
    print_info "Running garbage collection..."
    git gc --prune=now --aggressive
    
    print_success "Git cleanup completed"
}

show_repo_size() {
    local size=$(du -sh .git | cut -f1)
    echo "Repository size: $size"
}

verify_cleanup() {
    print_header "Verifying Cleanup"
    
    print_info "Checking for remaining sensitive files..."
    
    if list_sensitive_files; then
        print_success "Verification passed! No sensitive files found."
        return 0
    else
        print_error "Verification failed! Some sensitive files still exist."
        print_info "You may need to manually review and remove them."
        return 1
    fi
}

prompt_force_push() {
    print_header "Next Steps"
    
    echo ""
    print_warning "⚠️  IMPORTANT: Changes are local only!"
    echo ""
    print_info "To apply changes to remote repository, you need to force push:"
    echo ""
    echo "  git push origin --force --all"
    echo "  git push origin --force --tags"
    echo ""
    print_warning "⚠️  WARNING: This will rewrite remote history!"
    print_warning "⚠️  All team members will need to re-clone the repository!"
    echo ""
    
    read -p "Do you want to force push now? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        print_info "Force pushing to remote..."
        
        git push origin --force --all
        git push origin --force --tags
        
        print_success "Force push completed!"
    else
        print_info "Skipping force push. You can do it manually later."
    fi
}

notify_team() {
    print_header "Team Notification"
    
    echo ""
    print_warning "⚠️  IMPORTANT: Notify your team!"
    echo ""
    print_info "All team members need to:"
    echo ""
    echo "  1. Backup their local changes"
    echo "  2. Delete their local repository"
    echo "  3. Clone the repository again:"
    echo ""
    echo "     git clone <repository_url>"
    echo ""
    print_warning "Working with old local copies will cause conflicts!"
    echo ""
}

################################################################################
# MAIN SCRIPT
################################################################################

main() {
    print_header "WorkTimeTracker - Cleanup Credentials Script"
    
    # Проверки
    check_git_repo
    check_dependencies
    
    # Показать текущий размер репозитория
    echo "Current repository state:"
    show_repo_size
    echo ""
    
    # Предупреждение
    print_warning "⚠️  WARNING: This script will REWRITE Git history!"
    print_warning "⚠️  This is an IRREVERSIBLE operation!"
    echo ""
    print_info "What this script will do:"
    echo "  1. Create a backup of your repository"
    echo "  2. Remove all credentials from Git history"
    echo "  3. Clean up Git repository"
    echo "  4. Verify the cleanup"
    echo ""
    
    read -p "Do you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled."
        exit 0
    fi
    
    echo ""
    
    # Создать backup
    create_backup
    
    # Показать чувствительные файлы
    if list_sensitive_files; then
        print_info "No cleanup needed."
        exit 0
    fi
    
    # Подтверждение удаления
    echo ""
    read -p "Remove these files from history? (yes/no): " confirm_remove
    
    if [ "$confirm_remove" != "yes" ]; then
        print_info "Operation cancelled."
        exit 0
    fi
    
    # Очистка credentials
    cleanup_all_credentials
    
    # Очистка Git
    cleanup_git
    
    # Показать новый размер
    echo ""
    echo "Repository after cleanup:"
    show_repo_size
    echo ""
    
    # Верификация
    verify_cleanup
    
    # Force push
    prompt_force_push
    
    # Уведомление команды
    notify_team
    
    # Финал
    print_header "Cleanup Completed Successfully!"
    
    print_success "All credentials have been removed from Git history! ✅"
    echo ""
    print_info "Next steps:"
    echo "  1. Verify changes: git log --all --oneline"
    echo "  2. Update .gitignore to prevent future commits"
    echo "  3. Rotate all compromised credentials"
    echo "  4. Notify your team about repository rewrite"
    echo ""
    print_info "Backup location: $BACKUP_DIR"
    echo ""
}

# Запуск
main "$@"
