# Простой скрипт для добавления метода get_active_session
# Использование: .\fix_supabase_api.ps1

$filePath = "supabase_api.py"

Write-Host "🔧 Проверка и добавление метода get_active_session..." -ForegroundColor Cyan

if (-not (Test-Path $filePath)) {
    Write-Host "❌ Файл $filePath не найден!" -ForegroundColor Red
    exit 1
}

# Читаем файл построчно
$lines = Get-Content $filePath -Encoding UTF8
$newLines = @()
$methodAdded = $false
$foundInsertPoint = $false

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    $newLines += $line
    
    # Проверяем, есть ли уже метод
    if ($line -match "def get_active_session\(self, email: str\)") {
        Write-Host "✅ Метод get_active_session уже существует!" -ForegroundColor Green
        $methodAdded = $true
        break
    }
    
    # Ищем место для вставки - после "return self.get_active_sessions()"
    if (-not $methodAdded -and $line -match "^\s+return self\.get_active_sessions\(\)\s*$") {
        # Проверяем, что это метод get_all_active_sessions
        $checkIndex = $i - 1
        while ($checkIndex -ge 0 -and $lines[$checkIndex] -match "^\s*(#|def|\"\"\"|$)") {
            if ($lines[$checkIndex] -match "def get_all_active_sessions") {
                $foundInsertPoint = $true
                Write-Host "✅ Найдено место для вставки на строке $($i + 1)" -ForegroundColor Green
                
                # Добавляем пустую строку и метод
                $newLines += ""
                $newLines += "    def get_active_session(self, email: str) -> Optional[Dict[str, str]]:"
                $newLines += "        `"`"`""
                $newLines += "        Получить активную сессию пользователя по email."
                $newLines += "        "
                $newLines += "        Args:"
                $newLines += "            email: Email пользователя"
                $newLines += "        "
                $newLines += "        Returns:"
                $newLines += "            Словарь с данными сессии или None если не найдена"
                $newLines += "        `"`"`""
                $newLines += "        try:"
                $newLines += "            email_lower = (email or `"`").strip().lower()"
                $newLines += "            "
                $newLines += "            response = self.client.table('active_sessions')\"
                $newLines += "                .select('*')\"
                $newLines += "                .eq('email', email_lower)\"
                $newLines += "                .eq('status', 'active')\"
                $newLines += "                .order('login_time', desc=True)\"
                $newLines += "                .limit(1)\"
                $newLines += "                .execute()"
                $newLines += "            "
                $newLines += "            if response.data:"
                $newLines += "                session = response.data[0]"
                $newLines += "                # Преобразуем в формат, совместимый с sheets_api"
                $newLines += "                return {"
                $newLines += "                    'Email': session.get('email', ''),"
                $newLines += "                    'Name': session.get('name', ''),"
                $newLines += "                    'SessionID': session.get('session_id', ''),"
                $newLines += "                    'LoginTime': session.get('login_time', ''),"
                $newLines += "                    'Status': session.get('status', 'active'),"
                $newLines += "                    'LogoutTime': session.get('logout_time', ''),"
                $newLines += "                    'LogoutReason': session.get('logout_reason', ''),"
                $newLines += "                    'RemoteCommand': session.get('remote_command', '')"
                $newLines += "                }"
                $newLines += "            "
                $newLines += "            return None"
                $newLines += "            "
                $newLines += "        except Exception as e:"
                $newLines += "            logger.error(f`"Failed to get active session for {email}: {e}`")"
                $newLines += "            return None"
                $newLines += ""
                $methodAdded = $true
                break
            }
            $checkIndex--
        }
    }
}

if (-not $methodAdded) {
    Write-Host "❌ Не удалось найти место для вставки автоматически" -ForegroundColor Red
    Write-Host "   Попробуйте добавить метод вручную" -ForegroundColor Yellow
    exit 1
}

# Создаем резервную копию
$backupPath = "$filePath.backup"
Copy-Item $filePath $backupPath -Force
Write-Host "📦 Создана резервная копия: $backupPath" -ForegroundColor Cyan

# Записываем обновленный файл
$newLines | Set-Content $filePath -Encoding UTF8

Write-Host "✅ Метод get_active_session успешно добавлен!" -ForegroundColor Green
Write-Host ""
Write-Host "Проверка:" -ForegroundColor Cyan
Select-String -Path $filePath -Pattern "def get_active_session"
