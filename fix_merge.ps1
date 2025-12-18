# PowerShell скрипт для диагностики и исправления незавершенного merge

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Диагностика незавершенного merge" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка статуса
Write-Host "1. Статус репозитория:" -ForegroundColor Yellow
git status
Write-Host ""

# Проверка MERGE_HEAD
$mergeHeadPath = ".git\MERGE_HEAD"
if (Test-Path $mergeHeadPath) {
    Write-Host "2. MERGE_HEAD найден:" -ForegroundColor Yellow
    Get-Content $mergeHeadPath
    Write-Host ""
    Write-Host "3. Варианты решения:" -ForegroundColor Yellow
    Write-Host "   a) Отменить merge: git merge --abort" -ForegroundColor Green
    Write-Host "   b) Завершить merge: git commit (если нет конфликтов)" -ForegroundColor Green
    Write-Host "   c) Разрешить конфликты и закоммитить: git add . ; git commit" -ForegroundColor Green
} else {
    Write-Host "2. MERGE_HEAD не найден - merge не активен" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
