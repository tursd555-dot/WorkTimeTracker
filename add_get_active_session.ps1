# PowerShell скрипт для автоматического добавления метода get_active_session
# Использование: .\add_get_active_session.ps1

$ErrorActionPreference = "Stop"

$filePath = "supabase_api.py"

if (-not (Test-Path $filePath)) {
    Write-Host "❌ Файл $filePath не найден!" -ForegroundColor Red
    exit 1
}

Write-Host "🔧 Добавление метода get_active_session в $filePath..." -ForegroundColor Cyan
Write-Host ""

# Читаем файл
$content = Get-Content $filePath -Raw -Encoding UTF8

# Проверяем, есть ли уже метод
if ($content -match "def get_active_session\(self, email: str\)") {
    Write-Host "✅ Метод get_active_session уже существует в файле!" -ForegroundColor Green
    exit 0
}

# Код метода для вставки
$methodCode = @"
    def get_active_session(self, email: str) -> Optional[Dict[str, str]]:
        """
        Получить активную сессию пользователя по email.
        
        Args:
            email: Email пользователя
        
        Returns:
            Словарь с данными сессии или None если не найдена
        """
        try:
            email_lower = (email or "").strip().lower()
            
            response = self.client.table('active_sessions')\
                .select('*')\
                .eq('email', email_lower)\
                .eq('status', 'active')\
                .order('login_time', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                session = response.data[0]
                # Преобразуем в формат, совместимый с sheets_api
                return {
                    'Email': session.get('email', ''),
                    'Name': session.get('name', ''),
                    'SessionID': session.get('session_id', ''),
                    'LoginTime': session.get('login_time', ''),
                    'Status': session.get('status', 'active'),
                    'LogoutTime': session.get('logout_time', ''),
                    'LogoutReason': session.get('logout_reason', ''),
                    'RemoteCommand': session.get('remote_command', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active session for {email}: {e}")
            return None

"@

# Ищем место для вставки - после метода get_all_active_sessions
$pattern = '(def get_all_active_sessions\(self\) -> List\[Dict\]:[\s\S]*?return self\.get_active_sessions\(\)\s*\n\s*\n)'

if ($content -match $pattern) {
    $insertPos = $Matches[0].Length
    $newContent = $content.Substring(0, $insertPos) + $methodCode + $content.Substring($insertPos)
    Write-Host "✅ Найдено место для вставки метода" -ForegroundColor Green
} else {
    # Альтернативный поиск - ищем строку с return self.get_active_sessions()
    $pattern2 = '(return self\.get_active_sessions\(\)\s*\n\s*\n)'
    if ($content -match $pattern2) {
        $insertPos = $Matches[0].Length
        $matchIndex = $content.IndexOf($Matches[0])
        $newContent = $content.Substring(0, $matchIndex + $insertPos) + $methodCode + $content.Substring($matchIndex + $insertPos)
        Write-Host "✅ Найдено место для вставки метода (альтернативный поиск)" -ForegroundColor Green
    } else {
        # Последняя попытка - найти check_user_session_status и вставить перед ним
        $pattern3 = '(def check_user_session_status\(self, email: str, session_id: str\) -> str:)'
        if ($content -match $pattern3) {
            $matchIndex = $content.IndexOf($Matches[0])
            # Находим начало строки (после предыдущего \n)
            $lineStart = $content.LastIndexOf("`n", $matchIndex) + 1
            $newContent = $content.Substring(0, $lineStart) + $methodCode + $content.Substring($lineStart)
            Write-Host "✅ Найдено место для вставки метода (перед check_user_session_status)" -ForegroundColor Green
        } else {
            Write-Host "❌ Не удалось найти место для вставки метода!" -ForegroundColor Red
            Write-Host "   Попробуйте добавить метод вручную в VS Code" -ForegroundColor Yellow
            exit 1
        }
    }
}

# Создаем резервную копию
$backupPath = "$filePath.backup"
Copy-Item $filePath $backupPath
Write-Host "📦 Создана резервная копия: $backupPath" -ForegroundColor Cyan

# Записываем обновленный файл
$newContent | Set-Content $filePath -Encoding UTF8 -NoNewline

Write-Host "✅ Метод get_active_session успешно добавлен в $filePath" -ForegroundColor Green
Write-Host ""
Write-Host "✅ Готово! Теперь можно запустить приложение:" -ForegroundColor Green
Write-Host "   python user_app/main.py" -ForegroundColor Yellow
